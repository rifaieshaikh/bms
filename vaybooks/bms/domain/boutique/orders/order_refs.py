"""Helpers for canonical order id/number formats used in Mongo and the UI."""

from __future__ import annotations

import re

_O_PREFIX = re.compile(r"^O(\d+)$", re.IGNORECASE)


def normalize_order_ref(ref: str) -> str:
    """Canonicalize order id/number (e.g. ``O1001`` -> ``O-1001``)."""
    text = (ref or "").strip()
    if not text:
        return text
    match = _O_PREFIX.match(text.upper())
    if match:
        return f"O-{match.group(1)}"
    return text


def compact_order_ref(ref: str) -> str:
    """Compact display/search form without hyphens (``O-1001`` -> ``O1001``)."""
    return (ref or "").replace("-", "")


def order_ref_search_variants(ref: str) -> list[str]:
    """Return distinct id/number forms to try for lookup or search."""
    text = (ref or "").strip()
    if not text:
        return []
    normalized = normalize_order_ref(text)
    compact = compact_order_ref(normalized)
    variants: list[str] = []
    for candidate in (text, normalized, compact):
        if candidate and candidate not in variants:
            variants.append(candidate)
    return variants
