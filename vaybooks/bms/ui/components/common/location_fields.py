"""Shared UI helpers for party / document location association."""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

import streamlit as st

from vaybooks.bms.domain.identity.location_access import ALL_LOCATIONS
from vaybooks.bms.ui.auth.session import (
    current_working_location_id,
    require_specific_location,
)


def location_options_map(services: dict, *, active_only: bool = True) -> Dict[str, str]:
    """Return ``{display_name: location_id}`` for accessible locations."""
    from vaybooks.bms.domain.identity.location_access import accessible_locations
    from vaybooks.bms.ui.auth.session import get_current_user

    user = get_current_user(services)
    inventory = services.get("inventory")
    locations = accessible_locations(user, inventory) if inventory else []
    if not active_only:
        # accessible_locations already returns active; keep signature for callers
        pass
    return {f"{loc.name} ({loc.code})": loc.id for loc in locations}


def render_party_location_multiselect(
    key_prefix: str,
    services: dict,
    current_ids: Optional[Sequence[str]] = None,
    *,
    default_to_working: bool = True,
) -> List[str]:
    """Multiselect for party visibility ``location_ids``.

    On create (no current_ids), defaults to the concrete working location when
    one is selected. When working is ALL, defaults to all accessible locations.
    """
    opts = location_options_map(services)
    if not opts:
        st.warning("No locations available. Add locations under Settings → Locations.")
        return []

    id_to_name = {lid: name for name, lid in opts.items()}
    current = list(current_ids or [])
    if not current and default_to_working:
        working = current_working_location_id(services)
        if working and working != ALL_LOCATIONS and working in id_to_name:
            current = [working]
        else:
            current = list(opts.values())

    default_names = [id_to_name[i] for i in current if i in id_to_name]
    selected = st.multiselect(
        "Visible at locations *",
        list(opts.keys()),
        default=default_names,
        key=f"{key_prefix}_location_ids",
        help="Admin can make this party visible at multiple locations.",
    )
    return [opts[n] for n in selected if n in opts]


def require_location_name(services: dict) -> tuple[str, str]:
    """Return ``(location_id, location_name)`` for document stamping."""
    location_id = require_specific_location(services)
    inventory = services.get("inventory")
    name = ""
    if inventory:
        loc = inventory.get_location(location_id)
        if loc:
            name = loc.name
    return location_id, name
