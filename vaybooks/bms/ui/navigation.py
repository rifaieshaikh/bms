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


def _detail_param_key(page_key: str, param: str) -> str:
    return f"_detail_param_{page_key}_{param}"


def go_to_detail(page_key: str, entity_id: str, **extra_params) -> None:
    """Navigate to a detail route with ``?id=`` visible in the address bar.

    Session fallbacks remain so mid-session state still resolves if the URL
    is missing params.
    """
    target = _pages.get(page_key)
    entity_id = str(entity_id)
    st.session_state[_detail_session_key(page_key)] = entity_id
    params: dict[str, str] = {"id": entity_id}
    for key, value in extra_params.items():
        if value is not None:
            params[key] = str(value)
            st.session_state[_detail_param_key(page_key, key)] = str(value)
    if target is not None:
        st.switch_page(target, query_params=params)


def current_detail_id(page_key: str) -> Optional[str]:
    """Resolve the active detail id from query param, else session fallback."""
    qid = st.query_params.get("id")
    if qid:
        return qid
    return st.session_state.get(_detail_session_key(page_key))


def current_detail_param(page_key: str, param: str) -> Optional[str]:
    """Resolve an extra detail param from query param, else session fallback."""
    value = st.query_params.get(param)
    if value:
        return value
    return st.session_state.get(_detail_param_key(page_key, param))


def _list_param_key(page_key: str, param: str) -> str:
    return f"_list_param_{page_key}_{param}"


def go_to_list(page_key: str, **params) -> None:
    """Navigate to a list route, optionally seeding query params (deep link).

    Params are passed via ``st.switch_page(..., query_params=...)`` so they
    appear in the address bar. Session fallbacks remain for ``consume_list_param``.
    """
    target = _pages.get(page_key)
    query: dict[str, str] = {}
    for key, value in params.items():
        if value is not None:
            query[key] = str(value)
            st.session_state[_list_param_key(page_key, key)] = str(value)
    if target is not None:
        st.switch_page(target, query_params=query)


def consume_list_param(page_key: str, param: str) -> Optional[str]:
    """One-shot read of a list deep-link param from query param or session
    fallback. Clears both so the deep link only applies once."""
    value = st.query_params.get(param)
    if not value:
        value = st.session_state.pop(_list_param_key(page_key, param), None)
    else:
        st.session_state.pop(_list_param_key(page_key, param), None)
    if param in st.query_params:
        del st.query_params[param]
    return value


def go_back_to_list(entity_key: str, list_page_key: str) -> None:
    """Back button: clear this entity's filters/sort/pagination, then leave."""
    clear_list_state(entity_key)
    st.session_state.pop(_detail_session_key(list_page_key), None)
    target = _pages.get(list_page_key)
    if target is not None:
        st.switch_page(target, query_params={})
