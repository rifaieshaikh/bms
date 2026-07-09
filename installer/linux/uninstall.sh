#!/usr/bin/env bash
# VayBooks-BMS Linux uninstall script
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/vaybooks-bms}"
DATA_DIR="${DATA_DIR:-/var/lib/vaybooks-bms}"

read -r -p "Remove user data at $DATA_DIR? [y/N] " REMOVE_DATA

sudo systemctl stop vaybooks-bms 2>/dev/null || true
sudo systemctl disable vaybooks-bms 2>/dev/null || true
sudo rm -f /etc/systemd/system/vaybooks-bms.service
sudo systemctl daemon-reload
sudo rm -rf "$INSTALL_DIR"
rm -f "$HOME/.local/share/applications/vaybooks-bms.desktop"

if [[ "${REMOVE_DATA,,}" == "y" ]]; then
  sudo rm -rf "$DATA_DIR"
fi

echo "Uninstall complete."
