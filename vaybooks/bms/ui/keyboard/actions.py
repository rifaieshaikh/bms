"""Queue/consume action flags set by early shortcut resolve."""

from __future__ import annotations

import streamlit as st

_QUEUE_KEY = "_kb_action_queue"


def queue_action(action_id: str) -> None:
    q = st.session_state.setdefault(_QUEUE_KEY, {})
    q[action_id] = True


def peek_action(action_id: str) -> bool:
    q = st.session_state.get(_QUEUE_KEY) or {}
    return bool(q.get(action_id))


def consume_action(action_id: str) -> bool:
    q = st.session_state.get(_QUEUE_KEY) or {}
    if not q.pop(action_id, False):
        return False
    return True


def consume_any(*action_ids: str) -> str | None:
    for aid in action_ids:
        if consume_action(aid):
            return aid
    return None
