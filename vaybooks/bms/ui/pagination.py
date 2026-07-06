"""Shared client-side pagination for Streamlit list/card views."""

from __future__ import annotations

from typing import TypeVar

import streamlit as st

T = TypeVar("T")

# Default page sizes tuned to 3-column card grids unless noted.
CARD_PAGE_SIZE = 12
VOUCHER_PAGE_SIZE = 12
REPORT_PAGE_SIZE = 25
TRIAL_BALANCE_PAGE_SIZE = 20


def paginate_list(
    items: list[T],
    *,
    page_key: str,
    page_size: int = CARD_PAGE_SIZE,
    filter_key: str | None = None,
    filter_value: str | None = None,
) -> tuple[list[T], int, int]:
    """Return ``(page_slice, page_index, total_pages)``.

    Resets to page 0 when ``filter_key`` / ``filter_value`` changes.
    """
    if filter_key is not None:
        last_key = f"{page_key}_last_filter"
        if st.session_state.get(last_key) != filter_value:
            st.session_state[page_key] = 0
            st.session_state[last_key] = filter_value

    if not items:
        st.session_state[page_key] = 0
        return [], 0, 0

    total_pages = max(1, (len(items) + page_size - 1) // page_size)
    page = min(st.session_state.get(page_key, 0), total_pages - 1)
    st.session_state[page_key] = page
    start = page * page_size
    return items[start : start + page_size], page, total_pages


def render_page_controls(
    page: int,
    total_pages: int,
    total_count: int,
    *,
    page_key: str,
    prev_key: str,
    next_key: str,
    label: str = "items",
) -> None:
    """Render Prev / page indicator / Next when there is more than one page."""
    if total_pages <= 1:
        return
    prev_c, mid_c, next_c = st.columns([1, 2, 1])
    if prev_c.button("← Prev", disabled=page == 0, use_container_width=True, key=prev_key):
        st.session_state[page_key] = page - 1
        st.rerun()
    mid_c.markdown(
        f"<div style='text-align:center'>Page {page + 1} of {total_pages} "
        f"· {total_count} {label}</div>",
        unsafe_allow_html=True,
    )
    if next_c.button(
        "Next →",
        disabled=page >= total_pages - 1,
        use_container_width=True,
        key=next_key,
    ):
        st.session_state[page_key] = page + 1
        st.rerun()
