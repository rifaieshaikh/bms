"""Runtime context: current page, dialog armed, form editing, filters UI."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.ui.dialog_utils import _ARMED_FLAGS  # noqa: SLF001

_PAGE_KEY = "_kb_current_page"
_FORM_EDITING = "_kb_form_editing"
_FILTERS_UI = "_kb_filters_ui_open"
_SORT_UI = "_kb_sort_ui_open"
_SUBMIT_MAP = "_kb_dialog_submit_map"
_CARD_IDS = "_kb_card_ids"
_CARD_EDITABLE = "_kb_card_editable"


def set_current_page(page_key: str) -> None:
    st.session_state[_PAGE_KEY] = page_key


def get_current_page() -> str | None:
    return st.session_state.get(_PAGE_KEY)


def set_form_editing(active: bool) -> None:
    st.session_state[_FORM_EDITING] = bool(active)


def is_form_editing() -> bool:
    return bool(st.session_state.get(_FORM_EDITING))


def set_filters_ui_open(entity: str | None) -> None:
    st.session_state[_FILTERS_UI] = entity
    if entity:
        st.session_state[_SORT_UI] = None


def is_filters_ui_open(entity: str | None = None) -> bool:
    cur = st.session_state.get(_FILTERS_UI)
    if entity is None:
        return bool(cur)
    return cur == entity


def set_sort_ui_open(entity: str | None) -> None:
    st.session_state[_SORT_UI] = entity
    if entity:
        st.session_state[_FILTERS_UI] = None


def is_sort_ui_open(entity: str | None = None) -> bool:
    cur = st.session_state.get(_SORT_UI)
    if entity is None:
        return bool(cur)
    return cur == entity


def clear_list_panel_ui() -> None:
    st.session_state[_FILTERS_UI] = None
    st.session_state[_SORT_UI] = None


def is_dialog_armed() -> bool:
    armed = st.session_state.get(_ARMED_FLAGS) or []
    if armed:
        return True
    # Also any known dialog flags present
    from vaybooks.bms.ui.dialog_utils import DIALOG_FLAG_PREFIXES

    for key in st.session_state:
        if isinstance(key, str) and key.startswith(DIALOG_FLAG_PREFIXES):
            if st.session_state.get(key):
                return True
    return False


def get_submit_map() -> dict[str, str]:
    if _SUBMIT_MAP not in st.session_state:
        st.session_state[_SUBMIT_MAP] = {}
    return st.session_state[_SUBMIT_MAP]


def set_card_page(ids: list[str], *, editable: bool = True) -> None:
    st.session_state[_CARD_IDS] = list(ids)
    st.session_state[_CARD_EDITABLE] = editable


def get_card_page() -> tuple[list[str], bool]:
    return list(st.session_state.get(_CARD_IDS) or []), bool(
        st.session_state.get(_CARD_EDITABLE, True)
    )
