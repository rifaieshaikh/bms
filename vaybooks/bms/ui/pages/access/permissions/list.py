"""Access — Permissions: read-only catalog grouped by module."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.domain.entitlements.catalog import (
    PERMISSIONS,
    SYSTEM_ROLE_DEFINITIONS,
    permission_module,
)
from vaybooks.bms.ui.auth.guard import require_page_access


def render(services: dict):
    from vaybooks.bms.ui.keyboard.context import set_current_page

    set_current_page("permissions_settings")
    if not require_page_access(services, "permissions-settings"):
        return

    st.title("Permissions")
    st.caption(
        "Read-only catalog of every permission, which system roles include it, "
        "and whether it is active under the current plan, modules, and flags."
    )

    entitled = services["authorization"].entitlement_keys()

    # Reverse lookup: permission key -> system role names
    roles_by_key: dict[str, list[str]] = {}
    for meta in SYSTEM_ROLE_DEFINITIONS.values():
        for key in meta.get("permission_keys") or []:
            roles_by_key.setdefault(key, []).append(meta["name"])

    grouped: dict[str, list[str]] = {}
    for key in PERMISSIONS:
        grouped.setdefault(permission_module(key), []).append(key)

    for module in sorted(grouped):
        keys = grouped[module]
        active_count = sum(1 for k in keys if k in entitled)
        with st.expander(
            f"{module} ({active_count}/{len(keys)} active)", expanded=False
        ):
            hdr = st.columns([4, 1, 5])
            for col, label in zip(hdr, ("Permission", "Active", "System roles")):
                col.caption(label)
            for key in keys:
                cols = st.columns([4, 1, 5])
                cols[0].code(key, language=None)
                cols[1].write("✅" if key in entitled else "—")
                cols[2].write(", ".join(sorted(roles_by_key.get(key, []))) or "—")
