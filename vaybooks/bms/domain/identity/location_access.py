"""Resolve which inventory locations a user may use and how the header behaves.

Working-location model:
- Each user works from a single active location for sales/purchase/inventory
  creates. The active location is chosen in the app header.
- Multi-location roles (below) can also select "All" for viewing/filtering, but
  creates are blocked while "All" is selected.
- Single-location users are pinned to their one assigned location.
- Owner/admin can access every location.
"""

from __future__ import annotations

from typing import List, Optional, Sequence

from vaybooks.bms.domain.entitlements.catalog import (
    ROLE_OWNER,
    ROLE_PROCUREMENT,
    ROLE_PROJECT_MANAGER,
    ROLE_STOREKEEPER,
    ROLE_STORE_MANAGER,
    ROLE_WAREHOUSE_MANAGER,
)
from vaybooks.bms.domain.identity.entities import User

# Sentinel header value meaning "all accessible locations" (view/filter only).
ALL_LOCATIONS = "ALL"

# Roles allowed to span multiple locations and to select "All" in the header.
MULTI_LOCATION_ROLE_IDS = frozenset(
    {
        ROLE_OWNER,
        ROLE_WAREHOUSE_MANAGER,
        ROLE_STORE_MANAGER,
        ROLE_STOREKEEPER,
        ROLE_PROJECT_MANAGER,
        ROLE_PROCUREMENT,
    }
)


def is_admin_user(user: Optional[User]) -> bool:
    """Owner has unrestricted access to all locations."""
    if user is None:
        return False
    return ROLE_OWNER in (user.role_ids or [])


def is_multi_location_user(user: Optional[User]) -> bool:
    """Whether the user's roles permit spanning multiple locations."""
    if user is None:
        return False
    return bool(set(user.role_ids or []) & MULTI_LOCATION_ROLE_IDS)


def accessible_locations(user: Optional[User], inventory) -> List:
    """Return the Location objects the user may work from.

    - Admin/Owner: all active locations.
    - Everyone else: active locations whose id is in ``user.location_ids``.
    """
    if inventory is None:
        return []
    try:
        all_locations = inventory.list_locations(active_only=True)
    except Exception:
        return []
    if is_admin_user(user):
        return list(all_locations)
    if user is None:
        return []
    allowed = {
        str(lid).strip() for lid in (user.location_ids or []) if str(lid).strip()
    }
    if not allowed:
        return []
    return [loc for loc in all_locations if loc.id in allowed]


def can_select_all(user: Optional[User], locations: Sequence) -> bool:
    """Whether the user may pick the "All" header option.

    Only multi-location roles (or Owner) with more than one accessible location.
    """
    if is_admin_user(user):
        return True
    if not is_multi_location_user(user):
        return False
    return len(list(locations)) > 1


def default_working_location_id(user: Optional[User], locations: Sequence) -> str:
    """Initial header selection: the single accessible location, else "All".

    Admin/multi-location users default to All when more than one is available.
    """
    locs = list(locations)
    if len(locs) == 1:
        return locs[0].id
    if can_select_all(user, locs):
        return ALL_LOCATIONS
    return locs[0].id if locs else ALL_LOCATIONS


def user_location_ids(user: Optional[User]) -> Optional[List[str]]:
    """Explicit accessible ids, or None when unrestricted (admin)."""
    if is_admin_user(user):
        return None
    if user is None:
        return []
    return [str(lid).strip() for lid in (user.location_ids or []) if str(lid).strip()]


def is_location_accessible(user: Optional[User], location_id: str) -> bool:
    """Whether ``location_id`` is one the user may work from (empty id -> False)."""
    location_id = (location_id or "").strip()
    if not location_id:
        return False
    if is_admin_user(user):
        return True
    allowed = user_location_ids(user) or []
    return location_id in allowed
