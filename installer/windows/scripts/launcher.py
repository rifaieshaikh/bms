#!/usr/bin/env python3
"""VayBooks-BMS desktop launcher — ensure service is running and open browser."""

from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path


SERVICE_NAME = "VayBooksBMS"
DEFAULT_PORT = 8501


def _read_app_port() -> int:
    data_dir = os.environ.get("VAYBOOKS_DATA_DIR")
    if data_dir:
        config_path = Path(data_dir) / "config" / "config.toml"
        if config_path.exists():
            try:
                text = config_path.read_text(encoding="utf-8")
                for line in text.splitlines():
                    if line.strip().startswith("APP_PORT"):
                        return int(line.split("=", 1)[1].strip().strip('"'))
            except Exception:
                pass
    return int(os.environ.get("APP_PORT", DEFAULT_PORT))


def _service_running() -> bool:
    if sys.platform != "win32":
        return True
    result = subprocess.run(
        ["sc", "query", SERVICE_NAME],
        capture_output=True,
        text=True,
    )
    return "RUNNING" in result.stdout


def _start_service() -> None:
    if sys.platform != "win32":
        return
    subprocess.run(["net", "start", SERVICE_NAME], capture_output=True)


def _wait_for_app(port: int, timeout: float = 60.0) -> bool:
    url = f"http://127.0.0.1:{port}/_stcore/health"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError):
            time.sleep(1)
    return False


def main() -> int:
    port = _read_app_port()
    if sys.platform == "win32" and not _service_running():
        _start_service()
        if not _wait_for_app(port):
            print("Service did not become ready in time.", file=sys.stderr)
            return 1
    elif not _wait_for_app(port, timeout=5):
        print(f"Application not reachable on port {port}.", file=sys.stderr)
        return 1

    webbrowser.open(f"http://127.0.0.1:{port}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
