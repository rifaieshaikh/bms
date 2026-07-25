"""Session identity helpers for Streamlit project UI (delegates to app auth)."""

from __future__ import annotations

from typing import Optional, Union

import streamlit as st

from vaybooks.bms.domain.identity.entities import User
from vaybooks.bms.domain.projects.access import AppUser
from vaybooks.bms.ui.auth import session as auth_session

SESSION_USER_ID = auth_session.LEGACY_USER_ID
SESSION_USER_NAME = auth_session.LEGACY_USER_NAME
SESSION_VIEW_COST = auth_session.LEGACY_VIEW_COST

UserLike = Union[User, AppUser, None]


def current_actor_name() -> str:
    return auth_session.current_user_name() or "system"


def current_actor_id() -> str:
    return auth_session.current_user_id()


def can_view_internal_cost(services: dict, project_id: str = "") -> bool:
    if SESSION_VIEW_COST in st.session_state:
        return bool(st.session_state[SESSION_VIEW_COST])
    return auth_session.can_permission(
        services, "projects.cost.view_internal", project_id=project_id
    )


def get_session_user(services: dict) -> Optional[User]:
    return auth_session.get_current_user(services)


def ensure_default_session_user(services: dict) -> User | None:
    """Return the logged-in user; do not auto-login."""
    return auth_session.get_current_user(services)


def set_session_user(user: UserLike, services: dict, project_id: str = "") -> None:
    if user is None:
        return
    if isinstance(user, User):
        auth_session.login_user(user, services)
        return
    # Legacy AppUser → load or synthesize User
    users = services.get("users")
    if users:
        found = users.get_user(user.id) or users.get_by_username(user.username)
        if found:
            auth_session.login_user(found, services)
            return
    st.session_state[SESSION_USER_ID] = user.id
    st.session_state[SESSION_USER_NAME] = user.display_name or user.username
    policy = services.get("project_access")
    if policy:
        st.session_state[SESSION_VIEW_COST] = policy.can_view_internal_cost(
            user, project_id
        )
