"""Resolve which inventory locations a user may use and how the header behaves.

Working-location model:
- A business may have many locations; each user is assigned 1, several, or all
  (Owner) of those locations via ``user.location_ids``.
- The header working location is the active context for creates and list filters.
- Multi-location roles can select **"All"** for viewing/filtering. **All means
  every location the user can access** — not every location in the business
  (unless the user is Owner / has all locations assigned).
- Creates that stamp a single location are blocked while "All" is selected.
- Single-location users are pinned to their one assigned location.
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

# Sentinel header value: all locations this user can access (view/filter only).
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


def can_transfer_stock(user: Optional[User], accessible: Sequence) -> bool:
    """Stock transfers require access to at least two locations."""
    return len(list(accessible)) >= 2


def assert_locations_accessible(
    user: Optional[User],
    *location_ids: str,
    accessible_ids: Optional[Sequence[str]] = None,
) -> None:
    """Raise ValidationError if any location_id is outside the user's access."""
    from vaybooks.bms.domain.shared.exceptions import ValidationError

    if accessible_ids is None:
        allowed = user_location_ids(user)
        if allowed is None:
            return  # Owner unrestricted
        allowed_set = set(allowed)
    else:
        allowed_set = {str(i).strip() for i in accessible_ids if str(i).strip()}
    for lid in location_ids:
        lid = (lid or "").strip()
        if not lid or lid not in allowed_set:
            raise ValidationError(
                "You can only transfer stock between locations you have access to."
            )


def _normalize_id_list(ids: Optional[Sequence[str]]) -> List[str]:
    return [str(i).strip() for i in (ids or []) if str(i).strip()]


def location_id_mongo_filter(
    working_location_id: str,
    accessible_ids: Optional[Sequence[str]] = None,
) -> dict:
    """Mongo filter for documents stamped with a single ``location_id``.

    - Specific working location → ``{"location_id": working}``
    - ``ALL`` → ``{"location_id": {"$in": accessible_ids}}`` (or {} if unrestricted)
    """
    working = (working_location_id or "").strip()
    accessible = _normalize_id_list(accessible_ids)
    if working and working != ALL_LOCATIONS:
        return {"location_id": working}
    if accessible_ids is None:
        return {}
    if not accessible:
        return {"location_id": {"$in": []}}
    return {"location_id": {"$in": accessible}}


def location_ids_mongo_filter(
    working_location_id: str,
    accessible_ids: Optional[Sequence[str]] = None,
) -> dict:
    """Mongo filter for parties with multi-location visibility ``location_ids``.

    - Specific working location → party visible there
      (``location_ids`` contains working)
    - ``ALL`` → party visible at any accessible location
    """
    working = (working_location_id or "").strip()
    accessible = _normalize_id_list(accessible_ids)
    if working and working != ALL_LOCATIONS:
        return {"location_ids": working}
    if accessible_ids is None:
        return {}
    if not accessible:
        return {"location_ids": {"$in": []}}
    return {"location_ids": {"$in": accessible}}


def merge_mongo_filters(*filters: dict) -> dict:
    """Combine non-empty Mongo filter dicts with ``$and`` when needed."""
    parts = [f for f in filters if f]
    if not parts:
        return {}
    if len(parts) == 1:
        return parts[0]
    return {"$and": parts}
