# VayBooks-BMS Installation Guide

## System Requirements

### Windows (recommended)
- Windows 10/11 or Windows Server 2019+
- 4 GB RAM minimum (8 GB recommended with local MongoDB)
- 2 GB free disk space (more if installing local MongoDB)

### macOS / Linux
- See platform scripts in `installer/macos/` and `installer/linux/`

## Windows Installation

### Interactive install

1. Download `VayBooks-BMS-Setup-{version}.exe` from [GitHub Releases](https://github.com/rifaieshaikh/bms/releases)
2. Run the installer and accept the license
3. Choose a MongoDB option:
   - **Existing connection** — enter your MongoDB URI and database name (e.g. Atlas)
   - **Local MongoDB** — installs MongoDB Community Server and uses `mongodb://localhost:27017`
4. Complete the wizard — the app opens automatically at `http://127.0.0.1:8501`

### Silent install

```powershell
# Remote MongoDB (Atlas)
VayBooks-BMS-Setup-1.0.0.exe /SILENT /MONGO=remote /MONGO_URI="mongodb+srv://..." /DB_NAME="zahcci_customization"

# Local MongoDB
VayBooks-BMS-Setup-1.0.0.exe /SILENT /MONGO=local
```

## What Gets Installed

| Location | Contents |
|----------|----------|
| `C:\Program Files\VayBooks-BMS\` | Python runtime, app, tools, service scripts |
| `C:\ProgramData\VayBooks-BMS\` | Config, logs, uploads, backups, MongoDB data (if local) |

## Shortcuts

- **Desktop:** `VayBooks-BMS` — starts the service if needed and opens the browser
- **Start Menu:** `VayBooks-BMS`

## Windows Service

VayBooks-BMS runs as Windows service `VayBooksBMS`:
- Starts automatically on boot
- Restarts on failure
- Logs to `C:\ProgramData\VayBooks-BMS\logs\service.log`

## macOS / Linux

```bash
# macOS
sudo bash installer/macos/install.sh

# Linux
sudo bash installer/linux/install.sh
```

## Uninstall

- **Windows:** Settings → Apps → VayBooks-BMS, or run the uninstaller from Start Menu
- Choose whether to keep user data in ProgramData

## Building from Source

See [installer/README.md](../installer/README.md).
