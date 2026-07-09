#!/usr/bin/env bash
# VayBooks-BMS macOS install script
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
INSTALL_DIR="${INSTALL_DIR:-/Applications/VayBooks-BMS}"
DATA_DIR="${DATA_DIR:-/Library/Application Support/VayBooks-BMS}"
BUILD_ONLY="${BUILD_ONLY:-0}"
PYTHON_VERSION="3.11.9"

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
    *) echo "Unknown option: $1"; usage ;;
  esac
done

stage_app() {
  python3 "$REPO_ROOT/installer/shared/build_app.py" --output "$REPO_ROOT/installer/dist/staging" --skip-python --skip-downloads
}

install_app() {
  sudo mkdir -p "$INSTALL_DIR" "$DATA_DIR"/{config,logs,data/uploads,data/backups,migrations}
  sudo cp -R "$REPO_ROOT/installer/dist/staging/"* "$INSTALL_DIR/"
  sudo cp "$SCRIPT_DIR/launchd/com.vaybooks.bms.plist" /Library/LaunchDaemons/
  sudo sed -i '' "s|__INSTALL_DIR__|$INSTALL_DIR|g" /Library/LaunchDaemons/com.vaybooks.bms.plist
  sudo sed -i '' "s|__DATA_DIR__|$DATA_DIR|g" /Library/LaunchDaemons/com.vaybooks.bms.plist
  sudo launchctl load /Library/LaunchDaemons/com.vaybooks.bms.plist
  echo "Installed to $INSTALL_DIR"
}

package_tarball() {
  VERSION=$(python3 -c "import sys; sys.path.insert(0,'$REPO_ROOT'); from vaybooks.bms.version import __version__; print(__version__)")
  OUT="$REPO_ROOT/installer/dist/VayBooks-BMS-${VERSION}-macos.tar.gz"
  tar -czf "$OUT" -C "$REPO_ROOT/installer/dist/staging" .
  echo "Package: $OUT"
}

stage_app
if [[ "$BUILD_ONLY" == "1" ]]; then
  package_tarball
else
  install_app
fi
