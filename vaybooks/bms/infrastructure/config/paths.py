import os
from pathlib import Path

from vaybooks.bms.infrastructure.config.runtime import is_desktop


def get_data_dir() -> Path | None:
    raw = os.environ.get("VAYBOOKS_DATA_DIR")
    if raw:
        return Path(raw)
    return None


def get_config_dir() -> Path | None:
    data = get_data_dir()
    return data / "config" if data else None


def get_config_path() -> Path | None:
    config_dir = get_config_dir()
    return config_dir / "config.toml" if config_dir else None


def get_secrets_path() -> Path | None:
    config_dir = get_config_dir()
    return config_dir / "secrets.enc" if config_dir else None


def get_logs_dir() -> Path | None:
    data = get_data_dir()
    return data / "logs" if data else None


def get_backups_dir() -> Path | None:
    data = get_data_dir()
    return data / "data" / "backups" if data else None


def get_uploads_dir() -> Path | None:
    data = get_data_dir()
    return data / "data" / "uploads" if data else None


def ensure_desktop_dirs() -> None:
    if not is_desktop():
        return
    data = get_data_dir()
    if not data:
        return
    for sub in (
        "config",
        "logs",
        "data/uploads",
        "data/backups",
        "migrations",
    ):
        (data / sub).mkdir(parents=True, exist_ok=True)
