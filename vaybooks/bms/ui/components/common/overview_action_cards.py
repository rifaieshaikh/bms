"""Reusable action-queue cards for module Overview pages."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import streamlit as st

from vaybooks.bms.ui.styles import render_card_grid, status_badge

Row = dict[str, Any]
StrFn = Callable[[Row], str]
BadgeFn = Callable[[Row], tuple[str, str] | None]
OpenFn = Callable[[Row], None]


def overview_action_cards(
    title: str,
    rows: Sequence[Row],
    key_prefix: str,
    *,
    accent: str = "blue",
    title_fn: StrFn,
    subtitle_fn: StrFn | None = None,
    meta_fn: StrFn | None = None,
    badge_fn: BadgeFn | None = None,
    on_open: OpenFn | None = None,
    empty_msg: str = "All clear.",
    max_cards: int = 8,
) -> None:
    """Render a titled queue of action cards with optional Open buttons.

    ``badge_fn`` returns ``(label, color)`` or ``None``.
    ``on_open`` is called when the Open button is clicked for a row.
    """
    total = len(rows)
    st.markdown(f"#### {title} &nbsp; :{accent}[{total}]")

    if not rows:
        st.caption(empty_msg)
        st.divider()
        return

    shown = list(rows[:max_cards])

    def _render(row: Row, index: int) -> None:
        with st.container(border=True):
            st.markdown(f"**{title_fn(row)}**")
            if subtitle_fn is not None:
                subtitle = subtitle_fn(row)
                if subtitle:
                    st.caption(subtitle)
            if badge_fn is not None:
                badge = badge_fn(row)
                if badge:
                    label, color = badge
                    st.markdown(status_badge(label, color), unsafe_allow_html=True)
            if meta_fn is not None:
                meta = meta_fn(row)
                if meta:
                    st.write(meta)
            if on_open is not None:
                row_key = row.get("id") or row.get("account_id") or "row"
                if st.button(
                    "Open →",
                    key=f"{key_prefix}_open_{row_key}_{index}",
                    use_container_width=True,
                ):
                    on_open(row)

    render_card_grid(shown, _render, suffix=key_prefix)

    if total > max_cards:
        st.caption(f"+ {total - max_cards} more")
    st.divider()
