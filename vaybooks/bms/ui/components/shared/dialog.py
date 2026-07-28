from __future__ import annotations

from typing import Callable

import streamlit as st

__all__ = ["dialog_footer", "dialog_header"]


def dialog_header(title: str) -> None:
    """Render a dialog section header (the recurring ``**Title**`` markdown)."""
    st.markdown(f"**{title}**")


def dialog_footer(
    on_save: Callable[[], None],
    on_cancel: Callable[[], None] | None = None,
    *,
    save_label: str = "Save",
    cancel_label: str = "Cancel",
    save_key: str,
    cancel_key: str,
    disabled: bool = False,
) -> None:
    """Render the Save/Cancel button row shared by every ``*_dialog.py``.

    Purely the footer markup — dialog open/close session-state bookkeeping
    stays on ``dialog_utils.clear_dialog_flags`` / ``make_dismiss_handler`` as
    it does today; call those from ``on_save``/``on_cancel``.
    """
    save_col, cancel_col = st.columns(2)
    if save_col.button(
        save_label,
        key=save_key,
        type="primary",
        use_container_width=True,
        disabled=disabled,
    ):
        on_save()
    if cancel_col.button(cancel_label, key=cancel_key, use_container_width=True):
        if on_cancel:
            on_cancel()
