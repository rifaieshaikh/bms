"""Redesign topbar: Search + New/Export + utility icons + account chip.

Visual chrome matches the UI redesign. Controls reuse ``app_header`` helpers
(location, notifications, schedulers, business→New, access, settings,
migration→Export, account) — no VayBooks brand text.
"""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.ui.auth.session import current_user_name
from vaybooks.bms.ui.components.common import app_header

__all__ = ["render_topbar"]

_SEARCH_HTML = """
<div class="z-topbar-search">
  <i class="ti ti-search"></i>
  <input class="z-topbar-search-input" type="text" placeholder="Search..." disabled />
</div>
"""

_DIVIDER_HTML = '<div class="z-topbar-divider" aria-hidden="true"></div>'


def _render_new(services: dict, *, business_pages: list) -> None:
    pages = app_header.visible_pages(services, business_pages)
    with st.container(key="ztopbar_new"):
        with st.popover("+ New", icon=":material/add:"):
            if not pages:
                st.caption("No business pages available.")
                return
            app_header._render_menu_section("Business", pages)


def _render_export(services: dict, *, migration_pages: list) -> None:
    pages = app_header.visible_pages(services, migration_pages)
    with st.container(key="ztopbar_export"):
        with st.popover("Export", icon=":material/download:"):
            if not pages:
                st.caption("No export / migration tools available.")
                return
            app_header._render_menu_section("Migration", pages)


def _render_account_chip(services: dict) -> None:
    from vaybooks.bms.ui.auth.dialogs import sign_out_dialog

    name = current_user_name() or "Account"
    initial = (name[:1] or "A").upper()
    with st.container(key="ztopbar_account"):
        with st.popover(name, icon=":material/account_circle:"):
            st.markdown(
                f'<div class="z-topbar-account-head">'
                f'<span class="z-topbar-avatar">{initial}</span>'
                f'<span><strong>{name}</strong><br/>'
                f'<span class="z-topbar-user-role">Signed in</span></span>'
                f"</div>",
                unsafe_allow_html=True,
            )
            st.divider()
            if st.button(
                "Sign out",
                icon=":material/logout:",
                use_container_width=True,
                key="header_sign_out",
            ):
                sign_out_dialog(services)


def render_topbar(
    services: dict,
    *,
    settings_pages: list,
    business_pages: list | None = None,
    access_pages: list | None = None,
    migration_pages: list | None = None,
    scheduler_pages: list | None = None,
) -> None:
    """Render the redesign top header. Call once per app run from app.py."""
    with st.container(key="ztopbar"):
        c_search, c_actions = st.columns([3, 5], vertical_alignment="center")
        with c_search:
            st.markdown(_SEARCH_HTML, unsafe_allow_html=True)
        with c_actions:
            with st.container(key="ztopbar_actions"):
                (
                    c_new,
                    c_export,
                    c_div,
                    c_loc,
                    c_notif,
                    c_schedulers,
                    c_access,
                    c_settings,
                    c_account,
                ) = st.columns(
                    [1.35, 1.2, 0.25, 0.7, 0.7, 0.7, 0.7, 0.7, 1.8],
                    gap="small",
                )
                with c_new:
                    _render_new(services, business_pages=business_pages or [])
                with c_export:
                    _render_export(
                        services, migration_pages=migration_pages or []
                    )
                with c_div:
                    st.markdown(_DIVIDER_HTML, unsafe_allow_html=True)
                with c_loc:
                    with st.container(key="ztopbar_loc"):
                        app_header._render_location_switcher(services)
                with c_notif:
                    with st.container(key="ztopbar_notif"):
                        app_header._render_notifications(services)
                with c_schedulers:
                    with st.container(key="ztopbar_sched"):
                        app_header._render_schedulers(
                            services, scheduler_pages=scheduler_pages or []
                        )
                with c_access:
                    # Grid / apps → Access (admin tools)
                    with st.container(key="ztopbar_access"):
                        pages = app_header.visible_pages(
                            services, access_pages or []
                        )
                        with st.popover("\u00a0", icon=":material/apps:"):
                            if not pages:
                                st.caption("No access pages available.")
                            else:
                                app_header._render_menu_section("Access", pages)
                with c_settings:
                    with st.container(key="ztopbar_settings"):
                        # Settings only here; Migration lives under Export.
                        pages = app_header.visible_pages(services, settings_pages)
                        with st.popover("\u00a0", icon=":material/settings:"):
                            if not pages:
                                st.caption("No settings available.")
                            else:
                                app_header._render_menu_section("Settings", pages)
                with c_account:
                    _render_account_chip(services)
