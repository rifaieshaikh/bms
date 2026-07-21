"""Application settings with desktop TOML, env var, and Streamlit secrets fallback."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from vaybooks.bms.version import __version__
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

_SEED_FLAG_KEYS = (
    "SEED_CONFIG",
    "SEED_QA_FIXTURES",
    "PURGE_BUSINESS_DATA",
    "SEED_BUSINESS",
    "SEED_CUSTOMERS",
    "SEED_VENDORS",
    "SEED_CATEGORIES",
    "SEED_PRODUCTS",
)
_SEED_BUSINESS_KEYS = (
    "SEED_BUSINESS_REGISTRATION",
    "SEED_BUSINESS_STATE",
    "SEED_BUSINESS_GSTIN",
    "SEED_BUSINESS_PAN",
    "SEED_COMPOSITION_RATE",
    "SEED_BUSINESS_LEGAL_NAME",
    "SEED_BUSINESS_TRADE_NAME",
)
_SEED_SETTING_KEYS = _SEED_FLAG_KEYS + _SEED_BUSINESS_KEYS
logger = logging.getLogger("vaybooks.bms.config")


def _coerce_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return default


def _coerce_float(value: Any, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_str(value: Any, default: str) -> str:
    if value is None:
        return default
    return str(value).strip() or default


def _seed_flags_from_mapping(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "seed_config": _coerce_bool(raw.get("SEED_CONFIG"), True),
        "seed_qa_fixtures": _coerce_bool(raw.get("SEED_QA_FIXTURES"), False),
        "purge_business_data": _coerce_bool(raw.get("PURGE_BUSINESS_DATA"), False),
        "seed_business": _coerce_bool(raw.get("SEED_BUSINESS"), False),
        "seed_customers": _coerce_bool(raw.get("SEED_CUSTOMERS"), False),
        "seed_vendors": _coerce_bool(raw.get("SEED_VENDORS"), False),
        "seed_categories": _coerce_bool(raw.get("SEED_CATEGORIES"), False),
        "seed_products": _coerce_bool(raw.get("SEED_PRODUCTS"), False),
        "seed_business_registration": _coerce_str(
            raw.get("SEED_BUSINESS_REGISTRATION"), "Unregistered"
        ),
        "seed_business_state": _coerce_str(raw.get("SEED_BUSINESS_STATE"), "27"),
        "seed_business_gstin": _coerce_str(raw.get("SEED_BUSINESS_GSTIN"), ""),
        "seed_business_pan": _coerce_str(raw.get("SEED_BUSINESS_PAN"), ""),
        "seed_composition_rate": _coerce_float(raw.get("SEED_COMPOSITION_RATE"), 1.0),
        "seed_business_legal_name": _coerce_str(
            raw.get("SEED_BUSINESS_LEGAL_NAME"), "Seed Demo Business"
        ),
        "seed_business_trade_name": _coerce_str(
            raw.get("SEED_BUSINESS_TRADE_NAME"), "Seed Demo"
        ),
    }


def _seed_flags_from_env() -> dict[str, Any]:
    env_raw: dict[str, Any] = {}
    for key in _SEED_SETTING_KEYS:
        if key in os.environ:
            env_raw[key] = os.environ[key]
    return _seed_flags_from_mapping(env_raw)


def _find_streamlit_secrets_path() -> Path | None:
    path = Path.cwd() / ".streamlit" / "secrets.toml"
    return path if path.exists() else None


def _load_streamlit_secrets_file() -> dict[str, Any]:
    path = _find_streamlit_secrets_path()
    if not path:
        return {}
    return _parse_toml(path.read_text(encoding="utf-8"))


def _resolve_seed_flags() -> dict[str, Any]:
    """Resolve seed flags for cloud/local Streamlit deployments."""
    file_raw = _load_streamlit_secrets_file()
    if any(key in file_raw for key in _SEED_SETTING_KEYS):
        return _seed_flags_from_mapping(file_raw)

    try:
        import streamlit as st

        if any(key in st.secrets for key in _SEED_SETTING_KEYS):
            return _seed_flags_from_mapping({key: st.secrets[key] for key in st.secrets})
    except Exception:
        pass

    return _seed_flags_from_env()


def _apply_seed_flags(settings: AppSettings) -> AppSettings:
    if is_desktop():
        return settings
    seed_flags = _resolve_seed_flags()
    return replace(settings, **seed_flags)


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
    seed_config: bool = True
    seed_qa_fixtures: bool = False
    purge_business_data: bool = False
    seed_business: bool = False
    seed_customers: bool = False
    seed_vendors: bool = False
    seed_categories: bool = False
    seed_products: bool = False
    seed_business_registration: str = "Unregistered"
    seed_business_state: str = "27"
    seed_business_gstin: str = ""
    seed_business_pan: str = ""
    seed_composition_rate: float = 1.0
    seed_business_legal_name: str = "Seed Demo Business"
    seed_business_trade_name: str = "Seed Demo"
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
            elif isinstance(value, float):
                lines.append(f"{key} = {value}")
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
    seed_flags = _seed_flags_from_mapping(raw)
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
        **seed_flags,
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
    *_SEED_SETTING_KEYS,
}


def _load_env_settings() -> AppSettings | None:
    uri = os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URI")
    if not uri:
        return None
    seed_flags = _seed_flags_from_env()
    return AppSettings(
        mongo_uri=uri,
        db_name=os.environ.get(
            "MONGODB_DATABASE",
            os.environ.get("DB_NAME", "zahcci_customization"),
        ),
        app_port=int(os.environ.get("APP_PORT", "8501")),
        **seed_flags,
    )


def _load_streamlit_secrets() -> AppSettings | None:
    try:
        import streamlit as st

        if "MONGODB_URI" not in st.secrets:
            return None
        secrets = {key: st.secrets[key] for key in st.secrets}
        seed_flags = _seed_flags_from_mapping(secrets)
        return AppSettings(
            mongo_uri=str(st.secrets["MONGODB_URI"]),
            db_name=str(st.secrets.get("MONGODB_DATABASE", "zahcci_customization")),
            **seed_flags,
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
        _settings = _apply_seed_flags(env_settings)
        return _settings

    secrets_settings = _load_streamlit_secrets()
    if secrets_settings:
        _settings = _apply_seed_flags(secrets_settings)
        return _settings

    _settings = _apply_seed_flags(AppSettings())
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
        "SEED_CONFIG": settings.seed_config,
        "SEED_QA_FIXTURES": settings.seed_qa_fixtures,
        "PURGE_BUSINESS_DATA": settings.purge_business_data,
        "SEED_BUSINESS": settings.seed_business,
        "SEED_CUSTOMERS": settings.seed_customers,
        "SEED_VENDORS": settings.seed_vendors,
        "SEED_CATEGORIES": settings.seed_categories,
        "SEED_PRODUCTS": settings.seed_products,
        "SEED_BUSINESS_REGISTRATION": settings.seed_business_registration,
        "SEED_BUSINESS_STATE": settings.seed_business_state,
        "SEED_BUSINESS_GSTIN": settings.seed_business_gstin,
        "SEED_BUSINESS_PAN": settings.seed_business_pan,
        "SEED_COMPOSITION_RATE": settings.seed_composition_rate,
        "SEED_BUSINESS_LEGAL_NAME": settings.seed_business_legal_name,
        "SEED_BUSINESS_TRADE_NAME": settings.seed_business_trade_name,
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
