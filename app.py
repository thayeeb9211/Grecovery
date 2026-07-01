import os
import sys
import re
import json
import subprocess
import webbrowser
import urllib.request
from flask import Flask, request, jsonify, render_template

if getattr(sys, 'frozen', False):
    BASE_DIR     = os.path.dirname(sys.executable)
    TEMPLATE_DIR = os.path.join(sys._MEIPASS, 'templates')
else:
    BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
    TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')

app = Flask(__name__, template_folder=TEMPLATE_DIR)
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
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

@app.route('/api/version', methods=['GET'])
def check_version():
    local_ver = "1.0.0"
    try:
        ver_file = os.path.join(BASE_DIR, 'version.txt')
        with open(ver_file, 'r') as f:
            local_ver = f.read().strip()
    except Exception:
        pass
    try:
        url = "https://raw.githubusercontent.com/thayeeb9211/Grecovery/main/version.txt"
        with urllib.request.urlopen(url, timeout=5) as r:
            remote_ver = r.read().decode().strip()
        update_available = remote_ver != local_ver
        return jsonify({"local": local_ver, "remote": remote_ver, "update_available": update_available})
    except Exception:
        return jsonify({"local": local_ver, "remote": local_ver, "update_available": False})

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
