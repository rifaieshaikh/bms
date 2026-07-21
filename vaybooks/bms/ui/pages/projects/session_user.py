"""Session identity helpers for Streamlit project UI."""

from __future__ import annotations

from typing import Optional

import streamlit as st

from vaybooks.bms.domain.projects.access import AppUser
from vaybooks.bms.domain.shared.enums import ProjectAppRole

SESSION_USER_ID = "project_session_user_id"
SESSION_USER_NAME = "project_session_user_name"
SESSION_VIEW_COST = "project_session_view_internal_cost"


def current_actor_name() -> str:
    return (st.session_state.get(SESSION_USER_NAME) or "system").strip() or "system"


def current_actor_id() -> str:
    return (st.session_state.get(SESSION_USER_ID) or "").strip()


def can_view_internal_cost(services: dict, project_id: str = "") -> bool:
    if SESSION_VIEW_COST in st.session_state:
        return bool(st.session_state[SESSION_VIEW_COST])
    policy = services.get("project_access")
    user = get_session_user(services)
    if policy is None:
        return True
    return policy.can_view_internal_cost(user, project_id)


def get_session_user(services: dict) -> Optional[AppUser]:
    policy = services.get("project_access")
    user_id = current_actor_id()
    if policy and user_id:
        return policy.get_user(user_id)
    return None


def ensure_default_session_user(services: dict) -> AppUser | None:
    """Bootstrap Owner user into session when access service is available."""
    policy = services.get("project_access")
    if policy is None:
        st.session_state.setdefault(SESSION_USER_NAME, "system")
        st.session_state.setdefault(SESSION_VIEW_COST, True)
        return None
    if current_actor_id():
        return get_session_user(services)
    try:
        user = policy.ensure_user(
            "admin",
            display_name="Administrator",
            roles=[ProjectAppRole.OWNER],
        )
    except Exception:
        st.session_state[SESSION_USER_NAME] = "system"
        st.session_state[SESSION_VIEW_COST] = True
        return None
    set_session_user(user, services, project_id="")
    return user


def set_session_user(user: AppUser, services: dict, project_id: str = "") -> None:
    st.session_state[SESSION_USER_ID] = user.id
    st.session_state[SESSION_USER_NAME] = user.display_name or user.username
    policy = services.get("project_access")
    if policy:
        st.session_state[SESSION_VIEW_COST] = policy.can_view_internal_cost(
            user, project_id
        )
    else:
        st.session_state[SESSION_VIEW_COST] = user.view_internal_cost
