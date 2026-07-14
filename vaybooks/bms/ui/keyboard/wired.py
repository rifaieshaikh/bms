"""Track which shortcut actions are wired this run (Settings honesty)."""

from __future__ import annotations

import streamlit as st

_WIRED_KEY = "_kb_wired_actions"


def clear_wired() -> None:
    st.session_state[_WIRED_KEY] = set()


def mark_wired(*action_ids: str) -> None:
    wired = st.session_state.setdefault(_WIRED_KEY, set())
    for aid in action_ids:
        if aid:
            wired.add(aid)


def get_wired() -> set[str]:
    return set(st.session_state.get(_WIRED_KEY) or set())


def is_wired(action_id: str) -> bool:
    return action_id in get_wired()
