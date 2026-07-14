"""Dialog open + submit helpers for shortcut-driven Save/Create."""

from __future__ import annotations

from typing import Any, Optional

import streamlit as st

from vaybooks.bms.ui.dialog_utils import (
    clear_all_dialog_flags,
    register_armed_dialog,
)
from vaybooks.bms.ui.keyboard.context import get_submit_map


def open_dialog(
    flag_key: str,
    *,
    submit_key: str,
    value: Any = True,
    clear_others: bool = True,
) -> None:
    """Arm a dialog flag and record flag → submit_key for dialog.save."""
    if clear_others:
        clear_all_dialog_flags()
    st.session_state[flag_key] = value
    register_armed_dialog(flag_key)
    get_submit_map()[flag_key] = submit_key


def request_submit(submit_key: str) -> None:
    st.session_state[submit_key] = True


def consume_submit(submit_key: str) -> bool:
    return bool(st.session_state.pop(submit_key, False))


def armed_submit_key() -> Optional[str]:
    """Return submit key for the currently armed dialog, if any."""
    from vaybooks.bms.ui.dialog_utils import _ARMED_FLAGS  # noqa: SLF001

    submit_map = get_submit_map()
    for flag in st.session_state.get(_ARMED_FLAGS) or []:
        if flag in submit_map and st.session_state.get(flag):
            return submit_map[flag]
    # Fallback: any mapped flag that is presently truthy
    for flag, submit_key in list(submit_map.items()):
        if st.session_state.get(flag):
            return submit_key
    return None
