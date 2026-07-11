"""Unique test data generators (avoid collisions on shared dev DB)."""

from __future__ import annotations

import time
import uuid


def unique_suffix() -> str:
    return uuid.uuid4().hex[:8]


def unique_phone(prefix: str = "9") -> str:
    """Return a 10-digit Indian mobile starting with 6-9."""
    tail = int(time.time() * 1000) % 10_000_000
    return f"{prefix}{tail:09d}"[-10:]


def unique_name(label: str) -> str:
    return f"E2E {label} {unique_suffix()}"


def unique_gstin_pan(state_code: str = "27") -> tuple[str, str]:
    """Return a valid GSTIN + embedded PAN pair (unique per call)."""
    tail = int(time.time() * 1000) % 10_000
    pan = f"AAAAA{tail:04d}A"
    gstin = f"{state_code}{pan}1Z5"
    return gstin, pan
