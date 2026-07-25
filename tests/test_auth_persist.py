"""Persistent auth token issue / verify tests."""

from __future__ import annotations

import time

import pytest

from vaybooks.bms.ui.auth import persist as persist_mod


@pytest.fixture(autouse=True)
def _auth_secret(monkeypatch):
    monkeypatch.setenv("AUTH_SESSION_SECRET", "unit-test-secret")
    # Bypass st.secrets lookups in unit tests.
    monkeypatch.setattr(
        persist_mod,
        "_signing_secret",
        lambda: persist_mod.hashlib.sha256(b"unit-test-secret").digest(),
    )


def test_issue_and_verify_token_roundtrip():
    token = persist_mod.issue_token("user-abc", ttl_seconds=3600)
    assert persist_mod.verify_token(token) == "user-abc"


def test_verify_rejects_tampered_token():
    token = persist_mod.issue_token("user-abc", ttl_seconds=3600)
    parts = token.split(".")
    parts[0] = "other-user"
    assert persist_mod.verify_token(".".join(parts)) is None


def test_verify_rejects_expired_token(monkeypatch):
    past = time.time() - 100
    monkeypatch.setattr(persist_mod.time, "time", lambda: past)
    token = persist_mod.issue_token("user-abc", ttl_seconds=1)
    monkeypatch.setattr(persist_mod.time, "time", lambda: past + 100)
    assert persist_mod.verify_token(token) is None


def test_verify_rejects_garbage():
    assert persist_mod.verify_token("") is None
    assert persist_mod.verify_token("not.a.token.extra") is None
    assert persist_mod.verify_token("only-one-part") is None
