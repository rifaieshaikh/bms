"""Route/page permission guard helpers."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.ui.auth.session import can_permission, can_see_page, get_current_user


def require_page_access(services: dict, url_path: str) -> bool:
    """Return True if allowed; otherwise render access denied and return False."""
    if can_see_page(services, url_path):
        return True
    st.error("Access denied. You do not have permission to view this page.")
    user = get_current_user(services)
    if user:
        st.caption(f"Signed in as {user.display_name or user.username}")
    return False


def require_permission(services: dict, feature_key: str, *, project_id: str = "") -> bool:
    if can_permission(services, feature_key, project_id=project_id):
        return True
    st.error(f"Access denied ({feature_key}).")
    return False
