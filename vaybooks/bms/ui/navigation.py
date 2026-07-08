"""Route registry + navigation helpers for the multi-route UI.

``app.py`` builds every ``st.Page`` and registers it here by a stable key so
list/detail pages can navigate without importing each other.
"""

from __future__ import annotations

from typing import Optional

import streamlit as st

from vaybooks.bms.ui.session_keys import clear_list_state

# Registry populated by app.py: {page_key: st.Page}
_pages: dict[str, "st.Page"] = {}


def register(key: str, page: "st.Page") -> None:
    _pages[key] = page


def page(key: str) -> Optional["st.Page"]:
    return _pages.get(key)


def _detail_session_key(page_key: str) -> str:
    return f"_detail_id_{page_key}"


def go_to_detail(page_key: str, entity_id: str, **extra_params) -> None:
    """Navigate to a detail route, seeding ``?id=`` (with session fallback)."""
    target = _pages.get(page_key)
    st.session_state[_detail_session_key(page_key)] = str(entity_id)
    st.query_params.clear()
    st.query_params["id"] = str(entity_id)
    for key, value in extra_params.items():
        if value is not None:
            st.query_params[key] = str(value)
    if target is not None:
        st.switch_page(target)


def current_detail_id(page_key: str) -> Optional[str]:
    """Resolve the active detail id from query param, else session fallback."""
    qid = st.query_params.get("id")
    if qid:
        return qid
    return st.session_state.get(_detail_session_key(page_key))


def go_to_list(page_key: str, **params) -> None:
    """Navigate to a list route, optionally seeding query params (deep link)."""
    target = _pages.get(page_key)
    st.query_params.clear()
    for key, value in params.items():
        if value is not None:
            st.query_params[key] = str(value)
    if target is not None:
        st.switch_page(target)


def go_back_to_list(entity_key: str, list_page_key: str) -> None:
    """Back button: clear this entity's filters/sort/pagination, then leave."""
    clear_list_state(entity_key)
    st.session_state.pop(_detail_session_key(list_page_key), None)
    st.query_params.clear()
    target = _pages.get(list_page_key)
    if target is not None:
        st.switch_page(target)
