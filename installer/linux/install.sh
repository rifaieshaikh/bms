#!/usr/bin/env bash
# VayBooks-BMS Linux install script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
INSTALL_DIR="${INSTALL_DIR:-/opt/vaybooks-bms}"
DATA_DIR="${DATA_DIR:-/var/lib/vaybooks-bms}"
BUILD_ONLY="${BUILD_ONLY:-0}"

usage() {
  echo "Usage: $0 [--build-only] [--install-dir DIR] [--data-dir DIR]"
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --build-only) BUILD_ONLY=1; shift ;;
    --install-dir) INSTALL_DIR="$2"; shift 2 ;;
    --data-dir) DATA_DIR="$2"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "Unknown option: $1"; shift ;;
  esac
done

stage_app() {
  python3 "$REPO_ROOT/installer/shared/build_app.py" --output "$REPO_ROOT/installer/dist/staging" --skip-python
}

install_app() {
  sudo mkdir -p "$INSTALL_DIR" "$DATA_DIR"/{config,logs,data/uploads,data/backups,migrations}
  sudo cp -R "$REPO_ROOT/installer/dist/staging/"* "$INSTALL_DIR/"
  sudo cp "$SCRIPT_DIR/systemd/vaybooks-bms.service" /etc/systemd/system/
  sudo sed -i "s|__INSTALL_DIR__|$INSTALL_DIR|g" /etc/systemd/system/vaybooks-bms.service
  sudo sed -i "s|__DATA_DIR__|$DATA_DIR|g" /etc/systemd/system/vaybooks-bms.service
  sudo systemctl daemon-reload
  sudo systemctl enable vaybooks-bms
  sudo systemctl start vaybooks-bms

  DESKTOP_FILE="$HOME/.local/share/applications/vaybooks-bms.desktop"
  mkdir -p "$(dirname "$DESKTOP_FILE")"
  cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Name=VayBooks-BMS
Exec=xdg-open http://127.0.0.1:8501
Icon=applications-office
Type=Application
EOF
  echo "Installed to $INSTALL_DIR"
}

package_tarball() {
  VERSION=$(python3 -c "import sys; sys.path.insert(0,'$REPO_ROOT'); from vaybooks.bms import __version__; print(__version__)")
  OUT="$REPO_ROOT/installer/dist/VayBooks-BMS-${VERSION}-linux.tar.gz"
  tar -czf "$OUT" -C "$REPO_ROOT/installer/dist/staging" .
  echo "Package: $OUT"
}

stage_app
if [[ "$BUILD_ONLY" == "1" ]]; then
  package_tarball
else
  install_app
fi
