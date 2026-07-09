#!/usr/bin/env bash
# VayBooks-BMS macOS uninstall script
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/Applications/VayBooks-BMS}"
DATA_DIR="${DATA_DIR:-/Library/Application Support/VayBooks-BMS}"

read -r -p "Remove user data at $DATA_DIR? [y/N] " REMOVE_DATA

sudo launchctl unload /Library/LaunchDaemons/com.vaybooks.bms.plist 2>/dev/null || true
sudo rm -f /Library/LaunchDaemons/com.vaybooks.bms.plist
sudo rm -rf "$INSTALL_DIR"

if [[ "${REMOVE_DATA,,}" == "y" ]]; then
  sudo rm -rf "$DATA_DIR"
fi

echo "Uninstall complete."
