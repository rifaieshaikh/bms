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
SCHED_CACHE = "_header_scheduler_notifications_cache"
SCHED_CACHE_AT = "_header_scheduler_notifications_cached_at"
NOTIF_TTL_SECONDS = 120
MAX_NOTIFICATIONS = 15

# Icon-only popover labels (Streamlit requires a label string; keep visually empty).
_ICON_LABEL = "\u00a0"

# Notification kind -> permission required to see it.
_KIND_PERMISSIONS = {
    "quotation_approval": "projects.commercial.approve",
    "ra_approval": "projects.ra_bills.approve",
}


def invalidate_notification_cache() -> None:
    for key in (NOTIF_CACHE, NOTIF_CACHE_AT, SCHED_CACHE, SCHED_CACHE_AT):
        st.session_state.pop(key, None)


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


def _load_scheduler_notifications(services: dict) -> list:
    """Open scheduler notifications addressed to the current user."""
    now = time.time()
    cached_at = float(st.session_state.get(SCHED_CACHE_AT) or 0)
    if SCHED_CACHE in st.session_state and (now - cached_at) < NOTIF_TTL_SECONDS:
        return st.session_state[SCHED_CACHE]
    svc = services.get("schedulers")
    try:
        items = (
            list(svc.list_notifications(current_user_id(), limit=MAX_NOTIFICATIONS))
            if svc
            else []
        )
    except Exception:
        items = []
    st.session_state[SCHED_CACHE] = items
    st.session_state[SCHED_CACHE_AT] = now
    return items


def _render_notifications(services: dict) -> None:
    approvals = _load_pending_approvals(services)
    scheduled = _load_scheduler_notifications(services)
    count = len(approvals) + len(scheduled)
    # Badge count only when there are pending items; otherwise icon-only.
    label = str(count) if count else _ICON_LABEL
    with st.popover(label, icon=":material/notifications:"):
        head_l, head_r = st.columns([3, 1], vertical_alignment="center")
        head_l.markdown("**Notifications**")
        if head_r.button("Refresh", key="header_notif_refresh"):
            invalidate_notification_cache()
            st.rerun()
        if not count:
            st.caption("Nothing needs your attention.")
            return
        if approvals:
            st.caption(
                f"{len(approvals)} pending approval{'s' if len(approvals) != 1 else ''}"
            )
        for idx, item in enumerate(approvals[:MAX_NOTIFICATIONS]):
            row_l, row_r = st.columns([4, 1], vertical_alignment="center")
            row_l.write(getattr(item, "title", "") or "Pending approval")
            project_id = getattr(item, "project_id", "") or ""
            if project_id and row_r.button(
                "Open",
                key=f"header_notif_open_{idx}_{getattr(item, 'id', idx)}",
            ):
                navigation.go_to_list("project_workspace", project=project_id)
        if len(approvals) > MAX_NOTIFICATIONS:
            st.caption(f"… and {len(approvals) - MAX_NOTIFICATIONS} more")

        if scheduled:
            if approvals:
                st.divider()
            st.caption(f"{len(scheduled)} from schedulers")
        for idx, item in enumerate(scheduled[:MAX_NOTIFICATIONS]):
            row_l, row_r = st.columns([4, 1], vertical_alignment="center")
            row_l.write(getattr(item, "title", "") or "Scheduler notification")
            message = getattr(item, "message", "")
            if message:
                row_l.caption(message)
            if row_r.button(
                "Dismiss",
                key=f"header_sched_read_{idx}_{getattr(item, 'id', idx)}",
            ):
                services["schedulers"].mark_notification_read(getattr(item, "id", ""))
                invalidate_notification_cache()
                st.rerun()


def visible_pages(services: dict, pages: list) -> list:
    """Permission-filter a list of ``st.Page`` objects by ``url_path``."""
    return [
        page
        for page in pages or []
        if can_see_page(services, getattr(page, "url_path", "") or "")
    ]


# Backward-compatible alias used by existing tests.
visible_settings_pages = visible_pages


def _render_menu_section(title: str, pages: list) -> None:
    if not pages:
        return
    st.markdown(f"**{title}**")
    for page in pages:
        st.page_link(page)


def _render_settings(
    services: dict,
    *,
    settings_pages: list,
    access_pages: list,
    migration_pages: list,
) -> None:
    settings = visible_pages(services, settings_pages)
    access = visible_pages(services, access_pages)
    migration = visible_pages(services, migration_pages)
    with st.popover(_ICON_LABEL, icon=":material/settings:"):
        if not (settings or access or migration):
            st.caption("No settings available.")
            return
        _render_menu_section("Settings", settings)
        if settings and (access or migration):
            st.divider()
        _render_menu_section("Access", access)
        if access and migration:
            st.divider()
        _render_menu_section("Migration", migration)


def _render_schedulers(services: dict, *, scheduler_pages: list) -> None:
    pages = visible_pages(services, scheduler_pages)
    with st.popover(_ICON_LABEL, icon=":material/schedule:"):
        if not pages:
            st.caption("No schedulers available.")
            return
        _render_menu_section("Schedulers", pages)


def _render_location_switcher(services: dict) -> None:
    """Header control for the active working location (sales/purchase/inventory)."""
    from vaybooks.bms.domain.identity.location_access import (
        ALL_LOCATIONS,
        can_select_all,
    )
    from vaybooks.bms.ui.auth.session import (
        current_working_location_id,
        get_current_user,
        set_working_location_id,
    )

    inventory = services.get("inventory")
    if inventory is None:
        return

    user = get_current_user(services)
    locations = _accessible_locations(user, inventory)
    if not locations:
        with st.popover(_ICON_LABEL, icon=":material/location_off:"):
            st.caption("No locations assigned to your account.")
            st.caption("Ask an admin to assign locations under Access -> Users.")
        return

    current = current_working_location_id(services)
    allow_all = can_select_all(user, locations)

    label_by_id: dict[str, str] = {loc.id: f"{loc.code} - {loc.name}" for loc in locations}
    options: list[str] = []
    if allow_all:
        options.append(ALL_LOCATIONS)
    options.extend(loc.id for loc in locations)

    def _fmt(value: str) -> str:
        if value == ALL_LOCATIONS:
            return "All locations"
        return label_by_id.get(value, value)

    # Single fixed location: show as a static caption, no switcher.
    if len(options) == 1:
        with st.popover(_ICON_LABEL, icon=":material/location_on:"):
            st.markdown("**Working location**")
            st.caption(_fmt(options[0]))
        return

    with st.popover(_ICON_LABEL, icon=":material/location_on:"):
        st.markdown("**Working location**")
        try:
            index = options.index(current)
        except ValueError:
            index = 0
        selected = st.radio(
            "Working location",
            options,
            index=index,
            format_func=_fmt,
            key="header_working_location_radio",
            label_visibility="collapsed",
        )
        if selected != current:
            set_working_location_id(selected)
            st.rerun()
        if selected == ALL_LOCATIONS:
            st.caption(
                "All is view-only. Pick a specific location to create documents."
            )


def _accessible_locations(user, inventory) -> list:
    from vaybooks.bms.domain.identity.location_access import accessible_locations

    return accessible_locations(user, inventory)


def _render_account(services: dict) -> None:
    from vaybooks.bms.ui.auth.dialogs import sign_out_dialog

    name = current_user_name() or "Account"
    # Icon only in the header; display name lives inside the popover.
    with st.popover(_ICON_LABEL, icon=":material/account_circle:"):
        st.markdown(f"**{name}**")
        st.caption("Signed in")
        if st.button(
            "Sign out",
            icon=":material/logout:",
            use_container_width=True,
            key="header_sign_out",
        ):
            sign_out_dialog(services)


def render_app_header(
    services: dict,
    *,
    settings_pages: list,
    access_pages: list | None = None,
    migration_pages: list | None = None,
    scheduler_pages: list | None = None,
) -> None:
    """Sticky top bar: brand left, icon actions hugging the right edge."""
    with st.container(key="zheader"):
        c_brand, c_actions = st.columns([10, 1], vertical_alignment="center")
        with c_brand:
            st.markdown(
                '<p class="z-header-brand">VayBooks</p>',
                unsafe_allow_html=True,
            )
        with c_actions:
            with st.container(key="zh_actions"):
                c_loc, c_notif, c_schedulers, c_settings, c_account = st.columns(
                    5, gap="small"
                )
                with c_loc:
                    _render_location_switcher(services)
                with c_notif:
                    _render_notifications(services)
                with c_schedulers:
                    _render_schedulers(
                        services, scheduler_pages=scheduler_pages or []
                    )
                with c_settings:
                    _render_settings(
                        services,
                        settings_pages=settings_pages,
                        access_pages=access_pages or [],
                        migration_pages=migration_pages or [],
                    )
                with c_account:
                    _render_account(services)
