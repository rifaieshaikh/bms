"""Global authenticated top header: notifications, settings, account."""

from __future__ import annotations

import time

import streamlit as st

from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.auth.session import (
    can_permission,
    can_see_page,
    current_user_id,
    current_user_name,
)

NOTIF_CACHE = "_header_notifications_cache"
NOTIF_CACHE_AT = "_header_notifications_cached_at"
NOTIF_TTL_SECONDS = 120
MAX_NOTIFICATIONS = 15

# Notification kind -> permission required to see it.
_KIND_PERMISSIONS = {
    "quotation_approval": "projects.commercial.approve",
    "ra_approval": "projects.ra_bills.approve",
}


def invalidate_notification_cache() -> None:
    st.session_state.pop(NOTIF_CACHE, None)
    st.session_state.pop(NOTIF_CACHE_AT, None)


def _load_pending_approvals(services: dict) -> list:
    """Pending approvals for the current user, permission-gated and cached.

    The underlying service scans quotation/RA repositories, so results are
    cached in session state for a short TTL instead of re-querying per rerun.
    """
    allowed_kinds = {
        kind
        for kind, perm in _KIND_PERMISSIONS.items()
        if can_permission(services, perm)
    }
    if not allowed_kinds:
        return []

    now = time.time()
    cached_at = float(st.session_state.get(NOTIF_CACHE_AT) or 0)
    if NOTIF_CACHE in st.session_state and (now - cached_at) < NOTIF_TTL_SECONDS:
        items = st.session_state[NOTIF_CACHE]
    else:
        svc = services.get("project_notifications")
        try:
            items = list(svc.list_pending_approvals(current_user_id())) if svc else []
        except Exception:
            items = []
        st.session_state[NOTIF_CACHE] = items
        st.session_state[NOTIF_CACHE_AT] = now

    return [i for i in items if getattr(i, "kind", "") in allowed_kinds]


def _short_name(name: str, *, max_len: int = 18) -> str:
    name = (name or "").strip() or "Account"
    if len(name) <= max_len:
        return name
    return name[: max_len - 1].rstrip() + "…"


def _render_notifications(services: dict) -> None:
    items = _load_pending_approvals(services)
    count = len(items)
    label = f" {count}" if count else ""
    with st.popover(label, icon=":material/notifications:"):
        head_l, head_r = st.columns([3, 1], vertical_alignment="center")
        head_l.markdown("**Notifications**")
        if head_r.button("Refresh", key="header_notif_refresh"):
            invalidate_notification_cache()
            st.rerun()
        if not items:
            st.caption("No pending approvals.")
            return
        st.caption(f"{count} pending approval{'s' if count != 1 else ''}")
        for idx, item in enumerate(items[:MAX_NOTIFICATIONS]):
            row_l, row_r = st.columns([4, 1], vertical_alignment="center")
            row_l.write(getattr(item, "title", "") or "Pending approval")
            project_id = getattr(item, "project_id", "") or ""
            if project_id and row_r.button(
                "Open",
                key=f"header_notif_open_{idx}_{getattr(item, 'id', idx)}",
            ):
                navigation.go_to_list("project_workspace", project=project_id)
        if count > MAX_NOTIFICATIONS:
            st.caption(f"… and {count - MAX_NOTIFICATIONS} more")


def visible_settings_pages(services: dict, settings_pages: list) -> list:
    return [
        page
        for page in settings_pages or []
        if can_see_page(services, getattr(page, "url_path", "") or "")
    ]


def _render_settings(services: dict, settings_pages: list) -> None:
    visible = visible_settings_pages(services, settings_pages)
    with st.popover("", icon=":material/settings:"):
        st.markdown("**Settings**")
        if not visible:
            st.caption("No settings available.")
            return
        for page in visible:
            st.page_link(page)


def _render_account(services: dict) -> None:
    from vaybooks.bms.ui.auth.dialogs import sign_out_dialog

    name = current_user_name() or "Account"
    with st.popover(_short_name(name), icon=":material/account_circle:"):
        st.markdown(f"**{name}**")
        if st.button(
            "Sign out",
            icon=":material/logout:",
            use_container_width=True,
            key="header_sign_out",
        ):
            sign_out_dialog(services)


def render_app_header(services: dict, *, settings_pages: list) -> None:
    """Sticky top bar with brand on the left and account controls on the right."""
    with st.container(key="zheader"):
        c_brand, c_notif, c_settings, c_account = st.columns(
            [8, 1, 1, 2], vertical_alignment="center"
        )
        with c_brand:
            st.markdown(
                '<p class="z-header-brand">VayBooks</p>',
                unsafe_allow_html=True,
            )
        with c_notif:
            _render_notifications(services)
        with c_settings:
            _render_settings(services, settings_pages)
        with c_account:
            _render_account(services)
