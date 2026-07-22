"""Shared Streamlit dialog session helpers."""

from __future__ import annotations

import streamlit as st


def ensure_selectbox_option(key: str, options: list[str]) -> None:
    """Drop stale session values that are no longer valid selectbox options."""
    if not options:
        st.session_state.pop(key, None)
        return
    current = st.session_state.get(key)
    if current is not None and current not in options:
        st.session_state.pop(key, None)


def reset_dialog_state(prefix: str) -> None:
    for key in list(st.session_state.keys()):
        if key.startswith(prefix):
            st.session_state.pop(key, None)


__all__ = [
    "ensure_selectbox_option",
    "reset_dialog_state",
]
