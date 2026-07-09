"""Tests for secret/env controlled seeding settings."""

import os
from pathlib import Path

from vaybooks.bms.infrastructure.config.settings import (
    _coerce_bool,
    _resolve_seed_flags,
    _seed_flags_from_env,
    _seed_flags_from_mapping,
    get_settings,
    reload_settings,
)


def test_coerce_bool_accepts_common_truthy_strings():
    assert _coerce_bool("true", False) is True
    assert _coerce_bool("YES", False) is True
    assert _coerce_bool("0", True) is False
    assert _coerce_bool(None, True) is True


def test_seed_flags_from_mapping_defaults():
    assert _seed_flags_from_mapping({}) == {
        "seed_config": True,
        "seed_qa_fixtures": False,
        "purge_business_data": False,
    }


def test_seed_flags_from_mapping_overrides():
    flags = _seed_flags_from_mapping(
        {
            "SEED_CONFIG": "false",
            "SEED_QA_FIXTURES": "true",
            "PURGE_BUSINESS_DATA": "yes",
        }
    )
    assert flags == {
        "seed_config": False,
        "seed_qa_fixtures": True,
        "purge_business_data": True,
    }


def test_seed_flags_from_env(monkeypatch):
    monkeypatch.setenv("SEED_CONFIG", "false")
    monkeypatch.setenv("SEED_QA_FIXTURES", "true")
    monkeypatch.setenv("PURGE_BUSINESS_DATA", "1")
    assert _seed_flags_from_env() == {
        "seed_config": False,
        "seed_qa_fixtures": True,
        "purge_business_data": True,
    }


def test_env_settings_include_seed_flags(monkeypatch, tmp_path):
    monkeypatch.delenv("VAYBOOKS_DATA_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MONGODB_URI", "mongodb://localhost:27017")
    monkeypatch.setenv("SEED_QA_FIXTURES", "true")
    reload_settings()
    settings = get_settings()
    assert settings.seed_config is True
    assert settings.seed_qa_fixtures is True
    assert settings.purge_business_data is False
    reload_settings()


def test_seed_flags_read_from_streamlit_secrets_file(monkeypatch, tmp_path):
    monkeypatch.delenv("VAYBOOKS_DATA_DIR", raising=False)
    monkeypatch.setenv("MONGODB_URI", "mongodb://localhost:27017")
    monkeypatch.delenv("SEED_QA_FIXTURES", raising=False)
    monkeypatch.delenv("PURGE_BUSINESS_DATA", raising=False)

    secrets_dir = tmp_path / ".streamlit"
    secrets_dir.mkdir()
    secrets_path = secrets_dir / "secrets.toml"
    secrets_path.write_text(
        "\n".join(
            [
                'MONGODB_URI = "mongodb://localhost:27017"',
                "SEED_CONFIG = true",
                "SEED_QA_FIXTURES = false",
                "PURGE_BUSINESS_DATA = true",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    reload_settings()
    settings = get_settings()
    assert settings.seed_config is True
    assert settings.seed_qa_fixtures is False
    assert settings.purge_business_data is True
    assert _resolve_seed_flags()["purge_business_data"] is True
    reload_settings()
