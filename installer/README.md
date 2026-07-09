# VayBooks-BMS Installer Build Guide

## Prerequisites

### Windows
- Python 3.11+
- [Inno Setup 6](https://jrsoftware.org/isinfo.php)
- Internet access (downloads Python embeddable, NSSM, MongoDB MSI)

### All platforms
- Git
- pip

## Quick Build (Windows)

```powershell
cd installer

# Install build tools
pip install -r requirements-installer.txt
pip install -r ../requirements.txt
pip install -r ../requirements-desktop.txt

# Stage application payload
python shared/build_app.py --output dist/staging

# Compile installer (requires Inno Setup)
& "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" windows/inno/VayBooks-BMS.iss

# Generate checksum
python shared/generate_checksum.py dist/VayBooks-BMS-Setup-1.0.0.exe
```

Output: `installer/dist/VayBooks-BMS-Setup-{version}.exe`

## Version Management

```powershell
# Sync version from git tag
python shared/generate_version.py --version 1.0.1

# Or from latest git tag
python shared/generate_version.py
```

Updates `bms/vaybooks/bms/__init__.py` and Inno `#define MyAppVersion`.

## Publish version.json

```powershell
python shared/publish_release.py `
  --download-url "https://github.com/rifaieshaikh/bms/releases/download/v1.0.0/VayBooks-BMS-Setup-1.0.0.exe" `
  --sha256 "<hex>" `
  --release-notes "## 1.0.0`n- Initial release" `
  --output dist/version.json
```

## Staging Layout

```
dist/staging/
  python/          # Embedded Python + site-packages
  app/             # BMS application
  tools/           # nssm.exe, VayBooks-Launcher.exe
  service/         # Batch wrappers
  scripts/         # Install/upgrade PowerShell scripts
  nssm/            # Service registration scripts
  downloads/       # MongoDB MSI (not shipped in app dir)
```

## macOS / Linux Packages

```bash
# macOS tarball
BUILD_ONLY=1 bash macos/install.sh

# Linux tarball
BUILD_ONLY=1 bash linux/install.sh
```

## CI/CD

Push a tag `v*.*.*` to trigger `.github/workflows/release.yml`:
- Builds Windows installer + version.json
- Builds macOS and Linux tarballs
- Creates GitHub Release with all artifacts

## Code Signing (Optional)

For production distribution, sign the installer with an Authenticode certificate:

```powershell
signtool sign /f certificate.pfx /p password /tr http://timestamp.digicert.com /td sha256 /fd sha256 dist/VayBooks-BMS-Setup-1.0.0.exe
```

Unsigned installers work but may trigger SmartScreen warnings.

## Directory Structure

```
installer/
  windows/inno/       # Inno Setup scripts
  windows/nssm/       # Service install/uninstall
  windows/scripts/    # Launcher, pre/post install
  macos/              # install.sh, launchd plist
  linux/              # install.sh, systemd unit
  shared/             # build_app.py, version, checksum
  assets/             # icon, license
  dist/               # Build output (gitignored)
```
