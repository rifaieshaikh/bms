"""Auto-update checker."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Protocol
from urllib.request import urlopen

from packaging.version import Version

from vaybooks.bms.version import __version__
from vaybooks.bms.infrastructure.config.settings import get_settings

logger = logging.getLogger("vaybooks.bms.updater")


@dataclass
class UpdateInfo:
    latest_version: str
    download_url: str
    sha256: str
    release_notes: str
    published_at: str = ""
    mandatory: bool = False

    @property
    def is_newer(self) -> bool:
        try:
            return Version(self.latest_version) > Version(__version__)
        except Exception:
            return self.latest_version != __version__


class UpdateStrategy(Protocol):
    def check(self) -> UpdateInfo | None: ...
    def download(self, info: UpdateInfo) -> str: ...
    def verify(self, path: str, expected_sha256: str) -> bool: ...
    def apply(self, path: str) -> None: ...


def fetch_update_info(url: str | None = None) -> UpdateInfo | None:
    check_url = url or get_settings().update_check_url
    try:
        with urlopen(check_url, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
        return UpdateInfo(
            latest_version=str(data.get("latest_version", "")),
            download_url=str(data.get("download_url", "")),
            sha256=str(data.get("sha256", "")),
            release_notes=str(data.get("release_notes", "")),
            published_at=str(data.get("published_at", "")),
            mandatory=bool(data.get("mandatory", False)),
        )
    except Exception as exc:
        logger.warning("Update check failed: %s", exc)
        return None
