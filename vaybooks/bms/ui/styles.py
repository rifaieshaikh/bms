from __future__ import annotations

from typing import Callable, Sequence

import streamlit as st

from vaybooks.bms.ui.responsive import columns_for_width
from vaybooks.bms.ui.theme.icons import icon_font_link
from vaybooks.bms.ui.theme.loader import theme_css

CARD_GRID_PREFIX = "card_grid"


def inject_global_css() -> None:
    """Inject the design system's CSS (tokens + component styles) and the
    Tabler Icons webfont stylesheet.

    All styling lives in ``ui/theme/tokens.css`` (primitives) and
    ``ui/theme/theme.css`` (semantic tokens + component rules) — see
    ``theme_css()``. We deliberately do NOT override column layout here.
    Card grids use real Streamlit columns whose count is computed from the
    viewport width (see ``render_card_grid``), which keeps buttons inside
    their cards and lets each row fill the available width.

    The Tabler Icons webfont is loaded once here via a ``<link>`` tag (see
    ``vaybooks.bms.ui.theme.icons``) so HTML-rendered icons (``icon_html``/
    ``icon_caption``) have the font available on every page.
    """

    st.markdown(icon_font_link(), unsafe_allow_html=True)
    st.markdown(f"<style>\n{theme_css()}\n</style>", unsafe_allow_html=True)


def card_grid(suffix: str = "default"):
    """Return a uniquely-keyed container so scoped card CSS applies."""
    return st.container(key=f"{CARD_GRID_PREFIX}_{suffix}")


def panel(suffix: str = "default"):
    """Return a uniquely-keyed container for a single detail-page panel.

    Bordered containers rendered inside get the plum accent + elevation (via
    the ``st-key-zpanel`` CSS scope) without the hover-lift used for grid
    cards. Use for the header/summary sections on detail pages.
    """
    return st.container(key=f"zpanel_{suffix}")


def render_card_grid(
    items: Sequence,
    render_fn: Callable[[object, int], None],
    *,
    suffix: str,
    card_min_width: int = 240,
) -> None:
    """Render ``items`` as a responsive grid of native Streamlit columns.

    The number of columns is computed from the current viewport width so rows
    fill the available space and reflow per device. ``render_fn(item, index)``
    draws a single card (typically inside its own ``st.container(border=True)``).
    """
    if not items:
        return

    n_cols = max(1, columns_for_width(card_min=card_min_width))
    with card_grid(suffix):
        for row_start in range(0, len(items), n_cols):
            row = items[row_start : row_start + n_cols]
            cols = st.columns(n_cols)
            for offset, item in enumerate(row):
                with cols[offset]:
                    render_fn(item, row_start + offset)


def card_columns(n_items: int, max_cols: int | None = None):
    """Deprecated shim: return viewport-sized columns for legacy callers."""
    n_cols = max(1, columns_for_width())
    if max_cols is not None:
        n_cols = min(max_cols, n_cols)
    return st.columns(n_cols)


# Shared status -> badge color map (used by cards across pages).
STATUS_BADGE_COLORS = {
    "Draft": "gray",
    "In Progress": "blue",
    "Ready For Delivery": "orange",
    "Invoice Generated": "violet",
    "Completed": "green",
    "Delivered": "green",
    "Cancelled": "red",
    "Paid": "green",
    "Unpaid": "red",
    "Sent": "blue",
    "Accepted": "green",
    "Rejected": "red",
    "Expired": "orange",
    "Converted": "violet",
    "Confirmed": "blue",
    "Partially Delivered": "orange",
    "Closed": "gray",
}


def status_badge(label: str, color: str | None = None, *, compact: bool = False) -> str:
    """Return an HTML pill for a status/label. Render with st.markdown(..., True)."""
    tone = color or STATUS_BADGE_COLORS.get(label, "plum")
    extra = " z-compact" if compact else ""
    return f'<span class="z-badge {tone}{extra}">{label}</span>'


def metric_grid(
    metrics: Sequence[tuple],
    *,
    suffix: str,
    card_min_width: int = 220,
) -> None:
    """Render KPI metrics responsively (wraps on tablet/phone).

    ``metrics`` is a sequence of ``(label, value)`` or ``(label, value, help)``.
    """
    if not metrics:
        return
    n_cols = max(1, columns_for_width(card_min=card_min_width))
    with card_grid(f"metric_{suffix}"):
        for row_start in range(0, len(metrics), n_cols):
            row = metrics[row_start : row_start + n_cols]
            cols = st.columns(n_cols)
            for offset, metric in enumerate(row):
                label, value = metric[0], metric[1]
                helptext = metric[2] if len(metric) > 2 else None
                cols[offset].metric(label, value, help=helptext, border=True)
