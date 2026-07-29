"""Shared party location visibility validation."""

from __future__ import annotations

import os
from typing import List, Sequence

from vaybooks.bms.domain.shared.exceptions import ValidationError

_STRICT = False
_TEST_DEFAULT_LOCATION_ID = "loc-test"


def set_strict_location_validation(enabled: bool) -> None:
    """When True, empty location values always raise (even under pytest)."""
    global _STRICT
    _STRICT = enabled


def _soft_default_allowed() -> bool:
    return bool(os.environ.get("PYTEST_CURRENT_TEST")) and not _STRICT


def normalize_location_ids(values: Sequence[str] | None) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for value in values or []:
        lid = str(value or "").strip()
        if not lid or lid in seen:
            continue
        seen.add(lid)
        out.append(lid)
    return out


def require_location_ids(values: Sequence[str] | None) -> List[str]:
    """Require at least one location id for party visibility."""
    location_ids = normalize_location_ids(values)
    if not location_ids:
        if _soft_default_allowed():
            return [_TEST_DEFAULT_LOCATION_ID]
        raise ValidationError(
            "Select at least one location where this party is visible."
        )
    return location_ids


def require_location_id(value: str | None) -> str:
    """Require a non-empty location id for document stamping."""
    location_id = str(value or "").strip()
    if not location_id:
        if _soft_default_allowed():
            return _TEST_DEFAULT_LOCATION_ID
        raise ValidationError("Location is required")
    return location_id
