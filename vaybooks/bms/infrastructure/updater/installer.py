"""Download, verify, and apply desktop installer updates."""

from __future__ import annotations

import hashlib
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.request import urlretrieve

from vaybooks.bms.infrastructure.updater.checker import UpdateInfo, UpdateStrategy

logger = logging.getLogger("vaybooks.bms.updater")


class DesktopUpdateStrategy:
    def check(self) -> UpdateInfo | None:
        from vaybooks.bms.infrastructure.updater.checker import fetch_update_info

        return fetch_update_info()

    def download(self, info: UpdateInfo) -> str:
        dest_dir = Path(tempfile.gettempdir()) / "VayBooks-BMS"
        dest_dir.mkdir(parents=True, exist_ok=True)
        filename = Path(info.download_url).name or "VayBooks-BMS-Setup.exe"
        dest = dest_dir / filename
        logger.info("Downloading update from %s", info.download_url)
        urlretrieve(info.download_url, dest)
        return str(dest)

    def verify(self, path: str, expected_sha256: str) -> bool:
        if not expected_sha256:
            logger.warning("No SHA256 provided; skipping verification")
            return True
        digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        ok = digest.lower() == expected_sha256.lower()
        if not ok:
            logger.error("Checksum mismatch: expected %s got %s", expected_sha256, digest)
        return ok

    def apply(self, path: str) -> None:
        if sys.platform != "win32":
            raise RuntimeError("Silent installer is only supported on Windows")
        logger.info("Launching installer: %s", path)
        subprocess.Popen(
            [path, "/SILENT"],
            shell=True,
            creationflags=subprocess.DETACHED_PROCESS if hasattr(subprocess, "DETACHED_PROCESS") else 0,
        )


def get_update_strategy() -> UpdateStrategy:
    return DesktopUpdateStrategy()


def download_and_install(info: UpdateInfo) -> tuple[bool, str]:
    strategy = get_update_strategy()
    try:
        path = strategy.download(info)
        if not strategy.verify(path, info.sha256):
            return False, "Checksum verification failed"
        strategy.apply(path)
        return True, f"Installer launched: {path}"
    except Exception as exc:
        logger.exception("Update failed")
        return False, str(exc)
