"""Tests for secret/env/seed.toml controlled seeding settings."""

import os

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
    flags = _seed_flags_from_mapping({})
    assert flags["seed_config"] is True
    assert flags["seed_qa_fixtures"] is False
    assert flags["purge_business_data"] is False
    assert flags["seed_business"] is False
    assert flags["seed_customers"] is False
    assert flags["seed_vendors"] is False
    assert flags["seed_categories"] is False
    assert flags["seed_products"] is False
    assert flags["seed_profile"] == "none"
    assert flags["seed_customer_count"] == 100
    assert flags["seed_business_registration"] == "Unregistered"
    assert flags["seed_business_state"] == "27"
    assert flags["seed_composition_rate"] == 1.0


def test_seed_flags_from_mapping_overrides():
    flags = _seed_flags_from_mapping(
        {
            "SEED_CONFIG": "false",
            "SEED_QA_FIXTURES": "true",
            "PURGE_BUSINESS_DATA": "yes",
            "SEED_BUSINESS": "true",
            "SEED_CUSTOMERS": 1,
            "SEED_VENDORS": "on",
            "SEED_CATEGORIES": "true",
            "SEED_PRODUCTS": "true",
            "SEED_PROFILE": "pharma,hardware",
            "SEED_CUSTOMER_COUNT": 50,
            "SEED_BUSINESS_REGISTRATION": "Composition",
            "SEED_BUSINESS_STATE": "29",
            "SEED_BUSINESS_GSTIN": "29AAAAA0000A1Z5",
            "SEED_COMPOSITION_RATE": "1.5",
        }
    )
    assert flags["seed_config"] is False
    assert flags["seed_qa_fixtures"] is True
    assert flags["purge_business_data"] is True
    assert flags["seed_business"] is True
    assert flags["seed_customers"] is True
    assert flags["seed_vendors"] is True
    assert flags["seed_categories"] is True
    assert flags["seed_products"] is True
    assert flags["seed_profile"] == "pharma,hardware"
    assert flags["seed_customer_count"] == 50
    assert flags["seed_business_registration"] == "Composition"
    assert flags["seed_business_state"] == "29"
    assert flags["seed_business_gstin"] == "29AAAAA0000A1Z5"
    assert flags["seed_composition_rate"] == 1.5


def test_seed_count_clamped():
    flags = _seed_flags_from_mapping({"SEED_PRODUCT_COUNT": 9999})
    assert flags["seed_product_count"] == 500
    flags = _seed_flags_from_mapping({"SEED_PRODUCT_COUNT": 0})
    assert flags["seed_product_count"] == 1


def test_seed_flags_from_env(monkeypatch):
    monkeypatch.setenv("SEED_CONFIG", "false")
    monkeypatch.setenv("SEED_QA_FIXTURES", "true")
    monkeypatch.setenv("PURGE_BUSINESS_DATA", "1")
    monkeypatch.setenv("SEED_CUSTOMERS", "true")
    monkeypatch.setenv("SEED_BUSINESS_REGISTRATION", "Registered")
    flags = _seed_flags_from_env()
    assert flags["seed_config"] is False
    assert flags["seed_qa_fixtures"] is True
    assert flags["purge_business_data"] is True
    assert flags["seed_customers"] is True
    assert flags["seed_business_registration"] == "Registered"


def test_env_settings_include_seed_flags(monkeypatch, tmp_path):
    monkeypatch.delenv("VAYBOOKS_DATA_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MONGODB_URI", "mongodb://localhost:27017")
    monkeypatch.setenv("SEED_QA_FIXTURES", "true")
    monkeypatch.setenv("SEED_PRODUCTS", "true")
    reload_settings()
    settings = get_settings()
    assert settings.seed_config is True
    assert settings.seed_qa_fixtures is True
    assert settings.purge_business_data is False
    assert settings.seed_products is True
    reload_settings()


def test_seed_flags_read_from_streamlit_secrets_file(monkeypatch, tmp_path):
    monkeypatch.delenv("VAYBOOKS_DATA_DIR", raising=False)
    monkeypatch.setenv("MONGODB_URI", "mongodb://localhost:27017")
    for key in (
        "SEED_QA_FIXTURES",
        "PURGE_BUSINESS_DATA",
        "SEED_BUSINESS",
        "SEED_CUSTOMERS",
        "SEED_VENDORS",
        "SEED_CATEGORIES",
        "SEED_PRODUCTS",
        "SEED_BUSINESS_REGISTRATION",
        "SEED_PROFILE",
    ):
        monkeypatch.delenv(key, raising=False)

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
                "SEED_BUSINESS = true",
                "SEED_CUSTOMERS = true",
                "SEED_VENDORS = true",
                "SEED_CATEGORIES = true",
                "SEED_PRODUCTS = true",
                'SEED_PROFILE = "pos"',
                'SEED_BUSINESS_REGISTRATION = "Registered"',
                'SEED_BUSINESS_STATE = "27"',
                "SEED_COMPOSITION_RATE = 1.0",
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
    assert settings.seed_business is True
    assert settings.seed_customers is True
    assert settings.seed_vendors is True
    assert settings.seed_categories is True
    assert settings.seed_products is True
    assert settings.seed_profile == "pos"
    assert settings.seed_business_registration == "Registered"
    assert _resolve_seed_flags()["purge_business_data"] is True
    reload_settings()


def test_secrets_beat_env_and_seed_toml(monkeypatch, tmp_path):
    monkeypatch.delenv("VAYBOOKS_DATA_DIR", raising=False)
    for key in ("SEED_PROFILE", "SEED_CUSTOMERS", "SEED_QA_FIXTURES"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("MONGODB_URI", "mongodb://localhost:27017")
    monkeypatch.setenv("SEED_PROFILE", "pharma")
    monkeypatch.setenv("SEED_CUSTOMERS", "false")
    monkeypatch.setattr(
        "vaybooks.bms.infrastructure.config.settings._st_secrets_as_dict",
        lambda: {},
    )

    (tmp_path / "seed.toml").write_text(
        'SEED_PROFILE = "groceries"\nSEED_CUSTOMERS = true\n',
        encoding="utf-8",
    )
    secrets_dir = tmp_path / ".streamlit"
    secrets_dir.mkdir()
    (secrets_dir / "secrets.toml").write_text(
        "\n".join(
            [
                'MONGODB_URI = "mongodb://localhost:27017"',
                'SEED_PROFILE = "hardware"',
                "SEED_CUSTOMERS = true",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    reload_settings()
    flags = _resolve_seed_flags()
    assert flags["seed_profile"] == "hardware"
    assert flags["seed_customers"] is True
    reload_settings()


def test_env_beats_seed_toml_when_no_secrets(monkeypatch, tmp_path):
    monkeypatch.delenv("VAYBOOKS_DATA_DIR", raising=False)
    monkeypatch.setenv("MONGODB_URI", "mongodb://localhost:27017")
    monkeypatch.setenv("SEED_PROFILE", "paint")
    for key in (
        "SEED_QA_FIXTURES",
        "PURGE_BUSINESS_DATA",
        "SEED_BUSINESS",
        "SEED_CUSTOMERS",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(
        "vaybooks.bms.infrastructure.config.settings._st_secrets_as_dict",
        lambda: {},
    )

    (tmp_path / "seed.toml").write_text(
        'SEED_PROFILE = "fancy"\nSEED_VENDORS = true\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    reload_settings()
    flags = _resolve_seed_flags()
    assert flags["seed_profile"] == "paint"
    assert flags["seed_vendors"] is True
    reload_settings()


def test_seed_toml_business_blocks(monkeypatch, tmp_path):
    monkeypatch.delenv("VAYBOOKS_DATA_DIR", raising=False)
    monkeypatch.setenv("MONGODB_URI", "mongodb://localhost:27017")
    for key in _seed_env_keys():
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(
        "vaybooks.bms.infrastructure.config.settings._st_secrets_as_dict",
        lambda: {},
    )

    (tmp_path / "seed.toml").write_text(
        "\n".join(
            [
                'SEED_PROFILE = "boutique"',
                "[business.boutique]",
                'legal_name = "Kochi Silk Boutique"',
                'state = "32"',
                "[business.multi]",
                'legal_name = "Multi Shop"',
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    reload_settings()
    flags = _resolve_seed_flags()
    assert flags["seed_business_blocks"]["boutique"]["legal_name"] == "Kochi Silk Boutique"
    assert flags["seed_business_blocks"]["multi"]["legal_name"] == "Multi Shop"
    reload_settings()


def _seed_env_keys():
    return (
        "SEED_QA_FIXTURES",
        "PURGE_BUSINESS_DATA",
        "SEED_BUSINESS",
        "SEED_CUSTOMERS",
        "SEED_VENDORS",
        "SEED_CATEGORIES",
        "SEED_PRODUCTS",
        "SEED_PROFILE",
        "SEED_BUSINESS_REGISTRATION",
        "SEED_BUSINESS_STATE",
        "SEED_BUSINESS_LEGAL_NAME",
    )
