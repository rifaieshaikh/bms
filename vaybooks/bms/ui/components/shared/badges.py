from __future__ import annotations

from typing import Sequence, Tuple, Union

import streamlit as st

from vaybooks.bms.ui.styles import status_badge

__all__ = ["BadgeItem", "badge", "badge_row"]

BadgeItem = Union[str, Tuple[str, "str | None"], None, "bool"]


def badge(label: str, tone: str | None = None, *, compact: bool = True) -> str:
    """Return one badge pill's HTML. Compose several with ``badge_row``."""
    return status_badge(label, tone, compact=compact)


def badge_row(items: Sequence[BadgeItem]) -> None:
    """Render a row of badges in a single markdown call.

    Each item is a label string (default tone from ``STATUS_BADGE_COLORS``), a
    ``(label, tone)`` tuple, or a falsy value. Falsy items are skipped, so
    callers can pass conditional badges inline without pre-filtering::

        badge_row([
            invoice.is_generated and ("Generated", "green"),
            invoice.is_cancellation and ("Cancellation", "orange"),
        ])
    """
    pills = []
    for item in items:
        if not item:
            continue
        label, tone = item if isinstance(item, tuple) else (item, None)
        if not label:
            continue
        pills.append(badge(label, tone))
    if pills:
        st.markdown(" ".join(pills), unsafe_allow_html=True)
