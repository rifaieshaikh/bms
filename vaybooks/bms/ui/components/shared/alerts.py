from __future__ import annotations

from typing import Literal

import streamlit as st

__all__ = ["alert", "empty_state", "toast"]

AlertKind = Literal["error", "warning", "success", "info"]

_ALERT_FN = {
    "error": st.error,
    "warning": st.warning,
    "success": st.success,
    "info": st.info,
}


def alert(kind: AlertKind, message: str, *, icon: str | None = None) -> None:
    """Render a status alert through one consistent call site."""
    _ALERT_FN[kind](message, icon=icon)


def toast(message: str, *, icon: str | None = None) -> None:
    """Render a transient toast notification."""
    st.toast(message, icon=icon)


def empty_state(message: str, *, icon: str = "📭") -> None:
    """Render a consistent 'no results' placeholder for empty lists/cards."""
    st.info(message, icon=icon)
