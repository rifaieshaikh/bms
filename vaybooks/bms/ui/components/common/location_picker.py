"""Shared location selectbox for threading location_id through sales/purchase dialogs."""

from __future__ import annotations

from typing import Collection, Optional

import streamlit as st

from vaybooks.bms.domain.identity.entities import User
from vaybooks.bms.domain.identity.location_access import user_location_ids
from vaybooks.bms.domain.shared.enums import LocationType


def render_location_selectbox(
    inventory,
    key: str,
    *,
    location_type: Optional[LocationType] = None,
    label: str = "Location",
    required: bool = True,
    active_only: bool = True,
    selected_location_id: Optional[str] = None,
    allowed_location_ids: Optional[Collection[str]] = None,
    user: Optional[User] = None,
) -> str:
    """Render a selectbox of locations and return the selected location_id.

    Returns an empty string when no location is selected (or none exist).

    Access filtering (first match wins):
    - ``allowed_location_ids`` if provided (explicit allow-list)
    - else ``user`` via assigned location_ids / role type hint
    """
    locations = inventory.list_locations(
        active_only=active_only, location_type=location_type
    )
    all_by_id = {loc.id: loc for loc in locations}
    if allowed_location_ids is not None:
        allow = {str(lid).strip() for lid in allowed_location_ids if str(lid).strip()}
        locations = [loc for loc in locations if loc.id in allow]
    elif user is not None:
        allowed = user_location_ids(user)
        if allowed is not None:
            allowed_set = set(allowed)
            locations = [loc for loc in locations if loc.id in allowed_set]

    # Keep current/default value visible on edit even if outside allow-list
    default_id = (selected_location_id or "").strip()
    if default_id and default_id not in {loc.id for loc in locations}:
        extra = all_by_id.get(default_id) or inventory.get_location(default_id)
        if extra:
            locations = list(locations) + [extra]

    labels: list[str] = []
    mapping: dict[str, str] = {}
    if not required:
        labels.append("— None —")
        mapping["— None —"] = ""
    for loc in locations:
        loc_label = f"{loc.code} — {loc.name}"
        labels.append(loc_label)
        mapping[loc_label] = loc.id

    if not locations:
        if user is not None or allowed_location_ids is not None:
            st.warning(
                "No accessible locations for your account. "
                "Ask an admin to assign locations under Access → Users."
            )
        else:
            st.warning("No locations configured. Add one under Settings → Locations.")
        if required:
            return ""
        if not labels:
            return ""

    default_index = 0
    if selected_location_id:
        for idx, loc in enumerate(locations):
            if loc.id == selected_location_id:
                default_index = idx + (0 if required else 1)
                break
    elif not required:
        default_index = 0

    # If stored session value is no longer in the option list, reset
    if key in st.session_state and st.session_state[key] not in labels:
        st.session_state.pop(key, None)

    if key not in st.session_state and labels:
        st.session_state[key] = labels[min(default_index, len(labels) - 1)]

    selected_label = st.selectbox(
        label,
        labels,
        key=key,
    )
    location_id = mapping.get(selected_label, "")
    if required and not location_id:
        st.warning(f"Select a {label.lower()}")
    return location_id
