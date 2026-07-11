"""Product unit helpers."""

from __future__ import annotations

import re


def normalize_unit_code(code: str) -> str:
    return re.sub(r"\s+", "", (code or "").strip().lower())


def default_unit_label(code: str) -> str:
    code = normalize_unit_code(code)
    if not code:
        return ""
    return code.upper()
