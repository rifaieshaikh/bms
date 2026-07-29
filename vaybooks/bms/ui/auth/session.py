"""App-wide login session helpers for Streamlit."""

from __future__ import annotations

import logging
import time
from typing import Optional, Set

import streamlit as st

from vaybooks.bms.domain.identity.entities import User

logger = logging.getLogger(__name__)

SESSION_USER_ID = "auth_user_id"
SESSION_USER_NAME = "auth_user_name"
SESSION_EFFECTIVE_KEYS = "auth_effective_keys"
SESSION_ENTITLEMENT_VERSION = "auth_entitlement_version"
SESSION_WORKING_LOCATION_ID = "auth_working_location_id"
_RESTORE_ATTEMPTED = "_auth_restore_attempted"

# Legacy project session keys (kept in sync for audit callers)
LEGACY_USER_ID = "project_session_user_id"
LEGACY_USER_NAME = "project_session_user_name"
LEGACY_VIEW_COST = "project_session_view_internal_cost"


def is_authenticated() -> bool:
    return bool(st.session_state.get(SESSION_USER_ID))


def current_user_id() -> str:
    return (st.session_state.get(SESSION_USER_ID) or "").strip()


def current_user_name() -> str:
    return (st.session_state.get(SESSION_USER_NAME) or "").strip()


def current_effective_keys() -> Set[str]:
    keys = st.session_state.get(SESSION_EFFECTIVE_KEYS) or set()
    return set(keys)


def get_current_user(services: dict) -> Optional[User]:
    user_id = current_user_id()
    if not user_id:
        return None
    users = services.get("users")
    if users is None:
        return None
    return users.get_user(user_id)


def login_user(user: User, services: dict, *, persist: bool = True) -> None:
    auth = services.get("authorization")
    keys = set()
    version = 1
    if auth is not None:
        keys = auth.effective_keys(user)
        version = auth.get_org_entitlement().version
    st.session_state[SESSION_USER_ID] = user.id
    st.session_state[SESSION_USER_NAME] = user.display_name or user.username
    st.session_state[SESSION_EFFECTIVE_KEYS] = keys
    st.session_state[SESSION_ENTITLEMENT_VERSION] = version
    # Force the working location to be re-derived for the new user.
    st.session_state.pop(SESSION_WORKING_LOCATION_ID, None)
    st.session_state.pop("header_working_location_radio", None)
    # Keep project audit helpers working
    st.session_state[LEGACY_USER_ID] = user.id
    st.session_state[LEGACY_USER_NAME] = user.display_name or user.username
    st.session_state[LEGACY_VIEW_COST] = "projects.cost.view_internal" in keys
    st.session_state[_RESTORE_ATTEMPTED] = True

    if persist:
        try:
            from vaybooks.bms.ui.auth.persist import issue_token, set_auth_cookie

            set_auth_cookie(issue_token(user.id))
            # Give the browser a moment to apply the cookie before a rerun.
            time.sleep(0.35)
        except Exception:
            logger.exception("Failed to persist auth cookie")


def logout_user() -> None:
    for key in (
        SESSION_USER_ID,
        SESSION_USER_NAME,
        SESSION_EFFECTIVE_KEYS,
        SESSION_ENTITLEMENT_VERSION,
        SESSION_WORKING_LOCATION_ID,
        LEGACY_USER_ID,
        LEGACY_USER_NAME,
        LEGACY_VIEW_COST,
    ):
        st.session_state.pop(key, None)
    st.session_state.pop("header_working_location_radio", None)
    st.session_state[_RESTORE_ATTEMPTED] = True
    try:
        from vaybooks.bms.ui.auth.persist import clear_auth_cookie

        clear_auth_cookie()
        time.sleep(0.35)
    except Exception:
        logger.exception("Failed to clear auth cookie")


def try_restore_session(services: dict) -> bool:
    """Restore login from the persistent cookie after a browser refresh.

    Returns True when the in-memory session is authenticated after this call.
    """
    if is_authenticated():
        return True
    if st.session_state.get(_RESTORE_ATTEMPTED):
        return False
    st.session_state[_RESTORE_ATTEMPTED] = True

    try:
        from vaybooks.bms.ui.auth.persist import (
            clear_auth_cookie,
            issue_token,
            read_auth_cookie,
            set_auth_cookie,
            verify_token,
        )
    except Exception:
        return False

    token = read_auth_cookie()
    user_id = verify_token(token) if token else None
    if not user_id:
        if token:
            try:
                clear_auth_cookie()
            except Exception:
                pass
        return False

    users = services.get("users")
    if users is None:
        return False
    user = users.get_user(user_id)
    if user is None or not user.active:
        try:
            clear_auth_cookie()
        except Exception:
            pass
        return False

    # Hydrate session without rewriting the cookie first…
    login_user(user, services, persist=False)
    # …then slide the expiry forward another day while the user is active.
    try:
        set_auth_cookie(issue_token(user.id))
    except Exception:
        logger.exception("Failed to refresh auth cookie on restore")
    return True


def refresh_effective_keys(services: dict) -> Set[str]:
    user = get_current_user(services)
    auth = services.get("authorization")
    if user is None or auth is None:
        return set()
    keys = auth.effective_keys(user)
    st.session_state[SESSION_EFFECTIVE_KEYS] = keys
    st.session_state[SESSION_ENTITLEMENT_VERSION] = auth.get_org_entitlement().version
    st.session_state[LEGACY_VIEW_COST] = "projects.cost.view_internal" in keys
    return keys


def sync_entitlement_cache(services: dict) -> None:
    """Refresh cached permissions only when the org entitlement version changes.

    Called once per script run (top of app.py). Role/plan/flag/module mutations
    all call ``authorization.bump_org_version()``, and migrations bump the stored
    version too, so a single cheap version check keeps cached keys correct without
    recomputing (and re-querying) on every rerun.
    """
    if not is_authenticated():
        return
    auth = services.get("authorization")
    if auth is None:
        return
    current = auth.get_org_entitlement().version
    cached = st.session_state.get(SESSION_ENTITLEMENT_VERSION)
    if cached != current or SESSION_EFFECTIVE_KEYS not in st.session_state:
        refresh_effective_keys(services)


def _cached_keys(services: dict) -> Set[str]:
    """Effective keys from session cache, computing once if not yet loaded."""
    if SESSION_EFFECTIVE_KEYS not in st.session_state:
        return refresh_effective_keys(services)
    return current_effective_keys()


def can_permission(services: dict, feature_key: str, *, project_id: str = "") -> bool:
    auth = services.get("authorization")
    if auth is None:
        return True
    key = (feature_key or "").strip()
    if not key:
        return True
    # Project-scoped checks depend on membership and must be computed live.
    if project_id:
        return auth.can(get_current_user(services), key, project_id=project_id)
    return key in _cached_keys(services)


def can_see_page(services: dict, url_path: str) -> bool:
    auth = services.get("authorization")
    if auth is None:
        return True
    from vaybooks.bms.domain.entitlements.catalog import permission_for_page

    perm = permission_for_page(url_path)
    if not perm:
        return True
    return perm in _cached_keys(services)


# ---------------------------------------------------------------------------
# Working location (header context for sales / purchase / inventory creates)
# ---------------------------------------------------------------------------


def get_working_location_id() -> str:
    """Raw session value: ALL_LOCATIONS, a location id, or "" when unset."""
    return (st.session_state.get(SESSION_WORKING_LOCATION_ID) or "").strip()


def set_working_location_id(location_id: str) -> None:
    st.session_state[SESSION_WORKING_LOCATION_ID] = (location_id or "").strip()


def ensure_working_location(services: dict) -> str:
    """Initialize / revalidate the header working location for the current user.

    Returns the effective working-location value (``ALL_LOCATIONS`` or an id).
    Must be called before reading the working location on a page render.
    """
    from vaybooks.bms.domain.identity.location_access import (
        ALL_LOCATIONS,
        can_select_all,
        default_working_location_id,
    )

    user = get_current_user(services)
    inventory = services.get("inventory")
    locations = _accessible_locations(user, inventory)
    valid_ids = {loc.id for loc in locations}

    current = get_working_location_id()
    is_valid = current == ALL_LOCATIONS and can_select_all(user, locations)
    is_valid = is_valid or (current in valid_ids)

    if not is_valid:
        current = default_working_location_id(user, locations)
        set_working_location_id(current)
    return current


def current_working_location_id(services: dict) -> str:
    """Effective working location after ensuring it is initialized/valid."""
    return ensure_working_location(services)


def require_specific_location(services: dict) -> str:
    """Return the active location id, or raise when header is "All"/unset.

    Use at sales/purchase/inventory create entry points so documents are always
    stamped with a concrete location.
    """
    from vaybooks.bms.domain.identity.location_access import ALL_LOCATIONS
    from vaybooks.bms.domain.shared.exceptions import ValidationError

    location_id = ensure_working_location(services)
    if not location_id or location_id == ALL_LOCATIONS:
        raise ValidationError(
            "Select a specific location in the header before creating "
            "sales, purchase, or inventory documents."
        )
    return location_id


def working_location_list_context(services: dict) -> tuple[str, list[str] | None]:
    """Return ``(working_location_id, accessible_ids_or_None)`` for list filters.

    ``accessible_ids`` is always the locations the current user may access.
    When working location is ALL, filters use that set (not the full business
    roster unless the user is Owner with every location).

    ``None`` is reserved for unit UI tests with no session user.
    """
    from vaybooks.bms.domain.identity.location_access import ALL_LOCATIONS

    working = current_working_location_id(services)
    user = get_current_user(services)
    inventory = services.get("inventory")
    locations = _accessible_locations(user, inventory)
    accessible_ids = [loc.id for loc in locations]
    if user is None and working == ALL_LOCATIONS:
        return working, None
    return working, accessible_ids


def _accessible_locations(user, inventory) -> list:
    from vaybooks.bms.domain.identity.location_access import accessible_locations

    return accessible_locations(user, inventory)
