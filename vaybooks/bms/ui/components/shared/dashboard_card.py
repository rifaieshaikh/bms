"""Reusable dashboard summary card — icon + title, big value with optional
growth indicator, and a clickable footer.

Used for the top-of-page KPI row on each module's dashboard/overview page
(see ``theme.css``'s "Dashboard summary cards" section for the styling this
renders into). Column count is viewport-aware, matching ``render_card_grid``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

import streamlit as st

from vaybooks.bms.ui.responsive import columns_for_width
from vaybooks.bms.ui.theme.icons import icon_html

__all__ = ["DashboardCardSpec", "dashboard_card_grid"]

# Callers may reuse whatever tone vocabulary they already compute (e.g. the
# "warn"/"good"/"danger"/"neutral" strings several *_overview.py pages pass
# to metric_grid) — normalize to the tone classes theme.css defines.
_TONE_ALIASES = {
    "warn": "warning",
    "warning": "warning",
    "bad": "danger",
    "danger": "danger",
    "good": "success",
    "success": "success",
    "neutral": "neutral",
    "info": "info",
    "primary": "primary",
}


@dataclass(frozen=True)
class DashboardCardSpec:
    """One dashboard summary card's content.

    ``growth_percent`` is optional — omit it when no period-over-period
    comparison is available rather than fabricating one. ``footer_text`` is
    the clickable footer's supporting text; the right-aligned arrow is added
    by CSS. ``on_click`` runs when the footer is clicked.
    """

    title: str
    value: str
    icon: str = "chart-bar"
    tone: str = "primary"
    growth_percent: float | None = None
    footer_text: str = "View details"
    on_click: Callable[[], None] | None = None
    key: str | None = None


def _tone(name: str | None) -> str:
    return _TONE_ALIASES.get(name or "primary", "primary")


def _growth_html(percent: float | None) -> str:
    if percent is None:
        return ""
    direction = "up" if percent >= 0 else "down"
    arrow = "↑" if direction == "up" else "↓"
    return f'<span class="z-dcard-growth {direction}">{arrow} {abs(percent):.2f}%</span>'


def _render_one(spec: DashboardCardSpec, index: int, suffix: str) -> None:
    tone = _tone(spec.tone)
    st.markdown(
        f'<div class="z-dcard-top">'
        f'<div class="z-dcard-icon {tone}">{icon_html(spec.icon, size=22)}</div>'
        f'<div class="z-dcard-title">{spec.title}</div>'
        f"</div>"
        f'<div class="z-dcard-middle">'
        f'<span class="z-dcard-value">{spec.value}</span>'
        f"{_growth_html(spec.growth_percent)}"
        f"</div>",
        unsafe_allow_html=True,
    )
    footer_key = spec.key or f"{suffix}_{index}"
    with st.container(key=f"dcard_footer_{footer_key}"):
        if st.button(
            spec.footer_text, key=f"dcard_footer_btn_{footer_key}", width="stretch"
        ):
            if spec.on_click:
                spec.on_click()


def dashboard_card_grid(
    cards: Sequence[DashboardCardSpec],
    *,
    suffix: str,
    card_min_width: int = 240,
) -> None:
    """Render ``cards`` as a responsive grid of dashboard summary cards."""
    if not cards:
        return
    n_cols = max(1, columns_for_width(card_min=card_min_width))
    with st.container(key=f"dcard_grid_{suffix}"):
        for row_start in range(0, len(cards), n_cols):
            row = cards[row_start : row_start + n_cols]
            cols = st.columns(n_cols)
            for offset, spec in enumerate(row):
                with cols[offset]:
                    with st.container(border=True):
                        _render_one(spec, row_start + offset, suffix)
