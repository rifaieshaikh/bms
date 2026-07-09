"""Application settings with desktop TOML, env var, and Streamlit secrets fallback."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from vaybooks.bms import __version__
from vaybooks.bms.infrastructure.config.paths import (
    ensure_desktop_dirs,
    get_config_path,
    get_secrets_path,
)
from vaybooks.bms.infrastructure.config.runtime import is_desktop
from vaybooks.bms.infrastructure.config.secrets import resolve_mongo_uri

DEFAULT_UPDATE_URL = (
    "https://github.com/rifaieshaikh/bms/releases/latest/download/version.json"
)


@dataclass
class AppSettings:
    app_version: str = __version__
    app_port: int = 8501
    mongo_uri: str = ""
    db_name: str = "zahcci_customization"
    mongo_mode: str = "remote"
    update_check_url: str = DEFAULT_UPDATE_URL
    backup_schedule: str = "off"
    backup_retention_days: int = 30
    auto_update_enabled: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def mongodb_uri(self) -> str:
        return self.mongo_uri

    @property
    def mongodb_database(self) -> str:
        return self.db_name


_settings: AppSettings | None = None


def _parse_toml(text: str) -> dict[str, Any]:
    try:
        import tomllib

        return tomllib.loads(text)
    except ImportError:
        import tomli

        return tomli.loads(text)


def _serialize_toml(data: dict[str, Any]) -> str:
    try:
        import tomli_w

        return tomli_w.dumps(data)
    except ImportError:
        lines = []
        for key, value in data.items():
            if isinstance(value, bool):
                lines.append(f"{key} = {'true' if value else 'false'}")
            elif isinstance(value, int):
                lines.append(f"{key} = {value}")
            else:
                lines.append(f'{key} = "{value}"')
        return "\n".join(lines) + "\n"


def _load_toml_settings() -> AppSettings:
    ensure_desktop_dirs()
    config_path = get_config_path()
    secrets_path = get_secrets_path()
    if not config_path or not config_path.exists():
        return AppSettings()
    raw = _parse_toml(config_path.read_text(encoding="utf-8"))
    mongo_uri = resolve_mongo_uri(
        str(raw.get("MONGO_URI", "")),
        secrets_path,
    )
    return AppSettings(
        app_version=str(raw.get("APP_VERSION", __version__)),
        app_port=int(raw.get("APP_PORT", 8501)),
        mongo_uri=mongo_uri,
        db_name=str(raw.get("DB_NAME", "zahcci_customization")),
        mongo_mode=str(raw.get("MONGO_MODE", "remote")),
        update_check_url=str(raw.get("UPDATE_CHECK_URL", DEFAULT_UPDATE_URL)),
        backup_schedule=str(raw.get("BACKUP_SCHEDULE", "off")),
        backup_retention_days=int(raw.get("BACKUP_RETENTION_DAYS", 30)),
        auto_update_enabled=bool(raw.get("AUTO_UPDATE_ENABLED", False)),
        extra={k: v for k, v in raw.items() if k not in _KNOWN_KEYS},
    )


_KNOWN_KEYS = {
    "APP_VERSION",
    "APP_PORT",
    "MONGO_URI",
    "DB_NAME",
    "MONGO_MODE",
    "UPDATE_CHECK_URL",
    "BACKUP_SCHEDULE",
    "BACKUP_RETENTION_DAYS",
    "AUTO_UPDATE_ENABLED",
}


def _load_env_settings() -> AppSettings | None:
    uri = os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URI")
    if not uri:
        return None
    return AppSettings(
        mongo_uri=uri,
        db_name=os.environ.get(
            "MONGODB_DATABASE",
            os.environ.get("DB_NAME", "zahcci_customization"),
        ),
        app_port=int(os.environ.get("APP_PORT", "8501")),
    )


def _load_streamlit_secrets() -> AppSettings | None:
    try:
        import streamlit as st

        if "MONGODB_URI" not in st.secrets:
            return None
        return AppSettings(
            mongo_uri=str(st.secrets["MONGODB_URI"]),
            db_name=str(st.secrets.get("MONGODB_DATABASE", "zahcci_customization")),
        )
    except Exception:
        return None


def get_settings() -> AppSettings:
    global _settings
    if _settings is not None:
        return _settings

    if is_desktop():
        _settings = _load_toml_settings()
        if _settings.mongo_uri:
            return _settings

    env_settings = _load_env_settings()
    if env_settings:
        _settings = env_settings
        return _settings

    secrets_settings = _load_streamlit_secrets()
    if secrets_settings:
        _settings = secrets_settings
        return _settings

    _settings = AppSettings()
    return _settings


def reload_settings() -> AppSettings:
    global _settings
    _settings = None
    return get_settings()


def save_settings(settings: AppSettings, encrypt_uri: bool = True) -> None:
    """Persist settings to desktop config.toml."""
    from vaybooks.bms.infrastructure.config.secrets import encrypt_mongo_uri

    ensure_desktop_dirs()
    config_path = get_config_path()
    secrets_path = get_secrets_path()
    if not config_path:
        raise RuntimeError("Desktop config path is not available")

    mongo_uri_value = settings.mongo_uri
    if encrypt_uri and secrets_path and settings.mongo_uri:
        mongo_uri_value = encrypt_mongo_uri(settings.mongo_uri, secrets_path)

    data = {
        "APP_VERSION": settings.app_version,
        "APP_PORT": settings.app_port,
        "MONGO_URI": mongo_uri_value,
        "DB_NAME": settings.db_name,
        "MONGO_MODE": settings.mongo_mode,
        "UPDATE_CHECK_URL": settings.update_check_url,
        "BACKUP_SCHEDULE": settings.backup_schedule,
        "BACKUP_RETENTION_DAYS": settings.backup_retention_days,
        "AUTO_UPDATE_ENABLED": settings.auto_update_enabled,
    }
    data.update(settings.extra)
    config_path.write_text(_serialize_toml(data), encoding="utf-8")
    reload_settings()


def validate_mongo_connection(uri: str, db_name: str) -> tuple[bool, str]:
    if not uri:
        return False, "MongoDB URI is required"
    try:
        from pymongo import MongoClient

        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
        client[db_name].list_collection_names()
        client.close()
        return True, "Connection successful"
    except Exception as exc:
        return False, str(exc)
