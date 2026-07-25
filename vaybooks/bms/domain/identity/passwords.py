"""Password hashing helpers (stdlib PBKDF2 — no extra dependency)."""

from __future__ import annotations

import hashlib
import hmac
import secrets

_SCHEME = "pbkdf2_sha256"
_ITERATIONS = 260_000
_SALT_BYTES = 16


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Password must not be empty")
    salt = secrets.token_hex(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        _ITERATIONS,
    ).hex()
    return f"{_SCHEME}${_ITERATIONS}${salt}${digest}"


def verify_password(password: str, password_hash: str) -> bool:
    if not password or not password_hash:
        return False
    parts = password_hash.split("$")
    if len(parts) != 4 or parts[0] != _SCHEME:
        return False
    try:
        iterations = int(parts[1])
    except ValueError:
        return False
    salt, expected = parts[2], parts[3]
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    ).hex()
    return hmac.compare_digest(digest, expected)
