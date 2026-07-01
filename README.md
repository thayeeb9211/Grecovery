# Grecovery
**Gateway Manual Recovery System** — an internal tool for recovering faulty Enphase gateways via SSH tunneling.

## Quick Start
1. Unzip the project
2. Double-click **`run.bat`**

That's it. The launcher handles everything automatically:
- Installs Python if not found
- Installs required packages
- Checks for updates from GitHub
- Opens the Grecovery web interface in your browser

## Requirements
- Windows 10 / 11
- Internet connection (for first-time setup and updates)

## How It Works
1. **🚧 Find Normal Gateway** *(Under Progress)* — automatic Enlighten gateway discovery is coming soon; for now enter the serial number manually
2. **Configure SSH** — paste the SSH tunnel commands for both the faulty and normal gateways
3. **Set Remote Path** — specify the file/directory path to recover
4. **Run Recovery Pipeline** — downloads from the normal gateway, uploads to the faulty one, and opens an SSH tunnel for verification
