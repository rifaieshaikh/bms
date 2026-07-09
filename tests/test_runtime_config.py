"""Tests for desktop/cloud runtime configuration."""

import os

from vaybooks.bms.infrastructure.config.runtime import get_deployment_mode, is_desktop


def test_cloud_mode_by_default(monkeypatch):
    monkeypatch.delenv("VAYBOOKS_DATA_DIR", raising=False)
    assert get_deployment_mode() == "cloud"
    assert is_desktop() is False


def test_desktop_mode_when_data_dir_set(monkeypatch):
    monkeypatch.setenv("VAYBOOKS_DATA_DIR", r"C:\ProgramData\VayBooks-BMS")
    assert get_deployment_mode() == "desktop"
    assert is_desktop() is True


def test_secrets_module_imports_on_all_platforms():
    from vaybooks.bms.infrastructure.config import secrets  # noqa: F401

    assert secrets.resolve_mongo_uri("mongodb://localhost:27017", None) == "mongodb://localhost:27017"
