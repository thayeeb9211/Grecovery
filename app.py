import os
import sys
import re
import json
import subprocess
import webbrowser
from flask import Flask, request, jsonify, render_template

app = Flask(__name__, template_folder='templates')

CONFIG_FILE = "config.json"
session_logs = []

def add_log(message, type="info"):
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    session_logs.append({
        "timestamp": timestamp,
        "message": message,
        "type": type
    })

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

import urllib.parse
import requests

def save_config(config):
    current = load_config()
    current.update(config)
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(current, f, indent=4)
    except Exception as e:
        add_log(f"Warning: Could not save config: {e}", "warning")

def parse_ssh_command(ssh_cmd):
    clean_cmd = ssh_cmd.strip().strip('"\'')
    
    j_match = re.search(r'-J\s+([^@\s]+)@([\d\.]+)', clean_cmd)
    if j_match:
        cs_user = j_match.group(1)
        cs_ip = j_match.group(2)
    else:
        j_match_no_user = re.search(r'-J\s+([\d\.]+)', clean_cmd)
        cs_user = "mshariff"
        cs_ip = j_match_no_user.group(1) if j_match_no_user else ""

    words = clean_cmd.split()
    gw_ip = ""
    if words:
        for word in reversed(words):
            if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', word):
                gw_ip = word
                break
    
    return cs_user, cs_ip, gw_ip

def launch_powershell_window(command):
    ps_command = f"{command}; Write-Host ''; Write-Host 'Command completed. Press Enter to close this window...' -ForegroundColor Green; Read-Host"
    try:
        subprocess.Popen(
            ["powershell", "-NoExit", "-Command", ps_command],
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        return True
    except Exception as e:
        add_log(f"Failed to launch PowerShell: {e}", "error")
        return False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/config', methods=['GET', 'POST'])
def handle_config():
    if request.method == 'GET':
        return jsonify(load_config())
    else:
        config = request.json
        save_config(config)
        return jsonify({"status": "success"})

@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    if request.method == 'GET':
        cfg = load_config()
        return jsonify({
            "enlighten_email": cfg.get("enlighten_email", ""),
            "has_password": bool(cfg.get("enlighten_password", ""))
        })
    else:
        data = request.json
        save_config({
            "enlighten_email": data.get("enlighten_email", ""),
            "enlighten_password": data.get("enlighten_password", "")
        })
        return jsonify({"status": "success"})

@app.route('/api/search-gateways', methods=['POST'])
def search_gateways():
    data = request.json
    envoy_url = data.get("envoy_url", "").strip()
    
    if not envoy_url:
        return jsonify({"status": "error", "message": "Envoy Summary URL is required"}), 400
        
    cfg = load_config()
    email = cfg.get("enlighten_email", "")
    password = cfg.get("enlighten_password", "")
    
    if not email or not password:
        return jsonify({"status": "error", "message": "Enlighten credentials are not configured. Click the Settings icon in the header."}), 400

    add_log(f"Starting Enlighten search. Target URL: {envoy_url}", "info")
    
    try:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
        add_log("Navigating to Enlighten login page...", "info")
        login_page_res = session.get("https://enlighten.enphaseenergy.com/login", timeout=15)
        
        csrf_token = ""
        token_match = re.search(r'name="authenticity_token"\s+type="hidden"\s+value="([^"]+)"', login_page_res.text)
        if not token_match:
            token_match = re.search(r'value="([^"]+)"\s+name="authenticity_token"', login_page_res.text)
        if token_match:
            csrf_token = token_match.group(1)
            
        add_log("Sending credentials to Authenticator...", "info")
        login_data = {
            "utf8": "✓",
            "authenticity_token": csrf_token,
            "user[email]": email,
            "user[password]": password,
            "secured_user": "true",
            "locale": "en",
            "commit": "Sign In"
        }
        
        login_post_res = session.post("https://enlighten.enphaseenergy.com/login/login", data=login_data, timeout=15)
        
        if "Invalid email or password" in login_post_res.text or login_post_res.status_code == 401:
            add_log("Authentication failed: Invalid Enlighten credentials.", "error")
            return jsonify({"status": "error", "message": "Invalid Enlighten credentials."}), 401
            
        # Rewrite the URL to target the summary page sub-path
        parsed_url = urllib.parse.urlparse(envoy_url)
        path = parsed_url.path.rstrip('/')
        if not path.endswith('/summary'):
            path = path + '/summary'
        envoy_summary_url = urllib.parse.urlunparse((
            parsed_url.scheme,
            parsed_url.netloc,
            path,
            '', '', ''
        ))
        
        add_log(f"Authenticated successfully. Fetching Envoy summary sub-path: {envoy_summary_url}", "info")
        envoy_res = session.get(envoy_summary_url, timeout=15)
        
        if envoy_res.status_code != 200:
            add_log(f"Failed to load Envoy page. Status code: {envoy_res.status_code}", "error")
            return jsonify({"status": "error", "message": f"Failed to load Envoy details (HTTP {envoy_res.status_code})."}), 500

        # Diagnostics: Check if redirected to login / MFA challenge page
        if "user[email]" in envoy_res.text or "Sign In" in envoy_res.text or "login" in envoy_res.url:
            add_log("Session validation failed: Session redirected to the Enlighten Login or MFA/SSO challenge gate.", "error")
            with open("debug_login_redirect.html", "w", encoding="utf-8") as f:
                f.write(envoy_res.text)
            add_log("Dumped redirect response page to 'debug_login_redirect.html' for troubleshooting.", "warning")
            return jsonify({"status": "error", "message": "Enlighten session redirected to login. Check credentials or MFA/2FA."}), 401

        add_log(f"Loaded Envoy page. Length: {len(envoy_res.text)} characters.", "info")

        part_num = ""
        pn_match = re.search(r'Part\s+Number.*?<td>\s*([^<]+)', envoy_res.text, re.IGNORECASE | re.DOTALL)
        if pn_match:
            part_num = pn_match.group(1).strip()
            if "(" in part_num:
                part_num = part_num.split("(")[0].strip()
        else:
            pn_match = re.search(r'800-\d{5}-r\d{2}', envoy_res.text)
            if pn_match:
                part_num = pn_match.group(0)
                
        sw_version = ""
        sw_match = re.search(r'(?:Software|SW)\s+Version.*?<td>\s*([^<]+)', envoy_res.text, re.IGNORECASE | re.DOTALL)
        if sw_match:
            sw_version = sw_match.group(1).strip()
        else:
            sw_match = re.search(r'D\d+\.\d+\.\d+\.[^\s<]+', envoy_res.text)
            if sw_match:
                sw_version = sw_match.group(0)

        if not part_num or not sw_version:
            add_log(f"Parse failure: Part: '{part_num}', SW Version: '{sw_version}'", "error")
            with open("debug_envoy_page.html", "w", encoding="utf-8") as f:
                f.write(envoy_res.text)
            add_log("Dumped Envoy page content to 'debug_envoy_page.html' for layout diagnostics.", "warning")
            return jsonify({"status": "error", "message": "Could not extract Part Number or Software Version from Envoy page. Debug file dumped."}), 500

        add_log(f"Successfully scraped: Part Number = {part_num}, SW Version = {sw_version}", "success")
        
        search_query = urllib.parse.urlencode({
            "device_type_id": "1",
            "part_num": part_num,
            "software_version": sw_version,
            "status": "active"
        })
        search_url = f"https://enlighten.enphaseenergy.com/admin/devices/search?{search_query}"
        
        add_log(f"Querying active gateways: {search_url}", "info")
        search_res = session.get(search_url, timeout=15)
        
        sns = re.findall(r'\b(12\d{10})\b', search_res.text)
        unique_sns = list(dict.fromkeys(sns))
        
        if not unique_sns:
            add_log("No active normal gateway serial numbers found matching parameters.", "error")
            return jsonify({"status": "error", "message": "No matching active gateway serial numbers found on Enlighten."}), 404
                
        top_5 = unique_sns[:5]
        add_log(f"Successfully discovered {len(top_5)} active normal gateways.", "success")
        return jsonify({
            "status": "success",
            "part_num": part_num,
            "software_version": sw_version,
            "gateways": top_5
        })
        
    except Exception as e:
        add_log(f"Enlighten scraper error: {e}", "error")
        return jsonify({"status": "error", "message": f"Scraper error: {str(e)}"}), 500

@app.route('/api/parse-ssh', methods=['POST'])
def handle_parse():
    data = request.json
    ssh_cmd = data.get("ssh_command", "")
    cs_user, cs_ip, gw_ip = parse_ssh_command(ssh_cmd)
    return jsonify({
        "cs_user": cs_user,
        "cs_ip": cs_ip,
        "gw_ip": gw_ip
    })

@app.route('/api/run-step', methods=['POST'])
def run_step():
    data = request.json
    step = data.get("step")
    params = data.get("params", {})

    
    # Save the updated configurations first
    save_config({
        "faulty_sn": params.get("faulty_sn"),
        "faulty_ssh": params.get("faulty_ssh"),
        "normal_sn": params.get("normal_sn"),
        "normal_ssh": params.get("normal_ssh"),
        "remote_path": params.get("remote_path")
    })

    remote_path = params.get("remote_path", "").strip()
    if not remote_path:
        return jsonify({"status": "error", "message": "Remote path is required"}), 400

    last_folder = os.path.basename(remote_path.rstrip('/'))
    parent_path = os.path.dirname(remote_path.rstrip('/'))
    if not parent_path:
        parent_path = "/"

    if step == "recover":
        n_user = params.get("n_user", "mshariff")
        n_cs_ip = params.get("n_cs_ip")
        n_gw_ip = params.get("n_gw_ip")
        
        f_user = params.get("f_user", "mshariff")
        f_cs_ip = params.get("f_cs_ip")
        f_gw_ip = params.get("f_gw_ip")

        # Commands
        precheck_cmd = f'ssh -J {n_user}@{n_cs_ip} root@{n_gw_ip} "ls -ld {remote_path}"'
        download_cmd = f'scp -r -p -J {n_user}@{n_cs_ip} root@{n_gw_ip}:{remote_path} .'
        upload_cmd = f'scp -r -p -J {f_user}@{f_cs_ip} {last_folder} root@{f_gw_ip}:{parent_path}'
        tunnel_cmd = f'ssh -L localhost:8088:localhost:80 -J {f_user}@{f_cs_ip} {f_gw_ip}'

        # Multi-stage PowerShell command execution
        ps_script = (
            f"Write-Host '=== Step 0: Verifying Remote Path on Normal Gateway ===' -ForegroundColor Yellow; "
            f"{precheck_cmd}; "
            f"if ($LASTEXITCODE -ne 0) {{ "
            f"  Write-Host 'Verification FAIL check on Normal gateway! Path might not exist.' -ForegroundColor Red; "
            f"}} else {{ "
            f"  Write-Host 'Verification SUCCESS. Path exists on Normal gateway.' -ForegroundColor Green; "
            f"}} "
            f"Write-Host ''; "
            f"Write-Host '=== Step 1: Downloading File/Directory from Normal Gateway ===' -ForegroundColor Cyan; "
            f"{download_cmd}; "
            f"if ($LASTEXITCODE -eq 0) {{ "
            f"  Write-Host 'Download completed successfully.' -ForegroundColor Green; "
            f"  Write-Host ''; "
            f"  Write-Host '=== Step 2: Uploading File/Directory to Faulty Gateway ===' -ForegroundColor Cyan; "
            f"{upload_cmd}; "
            f"  if ($LASTEXITCODE -eq 0) {{ "
            f"    Write-Host 'Upload completed successfully.' -ForegroundColor Green; "
            f"    Write-Host ''; "
            f"    Write-Host '=== Step 3: Tunneling into Faulty Gateway ===' -ForegroundColor Cyan; "
            f"    Write-Host 'Tunnel Active: localhost:8088 -> localhost:80' -ForegroundColor Green; "
            f"    Write-Host 'Once connected, you can verify files using: ls -l {remote_path}' -ForegroundColor Yellow; "
            f"    {tunnel_cmd}; "
            f"  }} else {{ "
            f"    Write-Host 'Upload failed.' -ForegroundColor Red; "
            f"  }} "
            f"}} else {{ "
            f"  Write-Host 'Download failed.' -ForegroundColor Red; "
            f"}}"
        )

        add_log(f"Initiating Unified Recovery Pipeline: Normal check -> Download -> Upload -> Faulty tunnel", "info")
        
        if launch_powershell_window(ps_script):
            add_log("Launched unified manual recovery sequence in terminal window.", "success")
            return jsonify({"status": "success", "command": f"Download -> Upload -> Tunnel Sequence"})
        else:
            return jsonify({"status": "error", "message": "Failed to launch terminal"}), 500

    return jsonify({"status": "error", "message": "Invalid step"}), 400

@app.route('/api/logs', methods=['GET'])
def get_logs():
    return jsonify(session_logs)

@app.route('/api/log-message', methods=['POST'])
def log_message():
    data = request.json
    msg = data.get("message", "")
    msg_type = data.get("type", "info")
    add_log(msg, msg_type)
    return jsonify({"status": "success"})

if __name__ == '__main__':
    add_log("Gateway recovery tool backend started.", "success")
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        webbrowser.open("http://localhost:5000")
    app.run(port=5000, debug=True)
else:
    add_log("Gateway recovery tool loaded.", "success")
