"""Viewport-aware helpers for responsive layouts.

Streamlit runs on the server and does not expose the browser viewport width, so
we read ``window.innerWidth`` once per session via ``streamlit-js-eval`` and use
it to pick a per-device page size. The value is cached in ``st.session_state``
so a single fetch drives every list page and headless tests fall back cleanly.
"""

from __future__ import annotations

import streamlit as st

_WIDTH_STATE = "_viewport_width"
_DEFAULT_WIDTH = 1200  # assume desktop until the browser reports its width

# Layout tuning.
MIN_PAGE_SIZE = 10          # floor per product requirement
DEFAULT_CARD_MIN_WIDTH = 240  # target minimum card width in px
ROWS_PER_PAGE = 4           # how many rows of cards to load per page
# Approximate width the content area loses to the sidebar + page padding, so the
# column math reflects the space cards actually get rather than the full window.
_CONTENT_CHROME = 340


def viewport_width() -> int:
    """Return the browser viewport width in pixels.

    Falls back to the last known width (or a desktop default) whenever the
    browser has not reported yet or JS evaluation is unavailable (e.g. tests).
    """
    last_known = st.session_state.get(_WIDTH_STATE, _DEFAULT_WIDTH)
    try:
        from streamlit_js_eval import streamlit_js_eval

        value = streamlit_js_eval(
            js_expressions="window.innerWidth",
            key="viewport_width_probe",
        )
    except Exception:
        return int(last_known)

    if value is None:
        return int(last_known)

    try:
        width = int(value)
    except (TypeError, ValueError):
        return int(last_known)

    if width <= 0:
        return int(last_known)

    st.session_state[_WIDTH_STATE] = width
    return width


def columns_for_width(
    width: int | None = None, card_min: int = DEFAULT_CARD_MIN_WIDTH
) -> int:
    """Number of card columns that fit the usable content width."""
    if width is None:
        width = viewport_width()
    usable = max(card_min, width - _CONTENT_CHROME)
    return max(1, usable // card_min)


def page_size_for_width(
    width: int | None = None, card_min: int = DEFAULT_CARD_MIN_WIDTH
) -> int:
    """Page size scaled to the device: columns x rows, never below the floor.

    Not capped, so wider screens load proportionally more cards.
    """
    if width is None:
        width = viewport_width()
    cols = columns_for_width(width, card_min)
    return max(MIN_PAGE_SIZE, cols * ROWS_PER_PAGE)
