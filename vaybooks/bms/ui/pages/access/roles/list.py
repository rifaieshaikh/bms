"""Access — Roles: card list; system roles read-only; custom roles via dialogs."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.domain.entitlements.catalog import PERMISSIONS
from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.ui.auth.guard import require_page_access
from vaybooks.bms.ui.components.common.list_view import render_list
from vaybooks.bms.ui.dialog_utils import (
    clear_all_dialog_flags,
    clear_dialog_flags,
    make_dismiss_handler,
)
from vaybooks.bms.ui.filtering import FilterField, ListSchema, SortOption
from vaybooks.bms.ui import filtering as F
from vaybooks.bms.ui.pagination import CARD_PAGE_SIZE
from vaybooks.bms.ui.styles import render_card_grid, status_badge

EDIT_FLAG = "access_role_edit_flag"
DELETE_FLAG = "access_role_delete_flag"
VIEW_FLAG = "access_role_view_flag"


def _permission_options(services: dict) -> list:
    assignable = sorted(services["authorization"].assignable_permission_keys())
    return assignable or list(PERMISSIONS)


def _match_system(role, value) -> bool:
    want_system = value == "system"
    return bool(getattr(role, "is_system", False)) is want_system


ROLES = ListSchema(
    entity_key="access_roles",
    title="Roles",
    filter_fields=[
        FilterField("name", "Name", F.REGEX),
        FilterField(
            "kind",
            "Type",
            F.SELECT,
            options=[("system", "System"), ("custom", "Custom")],
            match=_match_system,
        ),
    ],
    sort_options=[
        SortOption("name", "Name"),
        SortOption("created_at", "Created"),
    ],
    default_sort="name",
    default_desc=False,
    page_size=CARD_PAGE_SIZE,
)


@st.dialog("Create Role")
def _create_role_dialog(services: dict, system_roles) -> None:
    options = _permission_options(services)
    with st.form("access_role_create_form"):
        name = st.text_input("Name")
        description = st.text_input("Description")
        clone_from = st.selectbox(
            "Clone from (optional)",
            options=[""] + [r.id for r in system_roles],
            format_func=lambda rid: (
                "(none)" if not rid else next(r.name for r in system_roles if r.id == rid)
            ),
        )
        selected = st.multiselect("Permissions", options=options)
        if st.form_submit_button("Create role", type="primary"):
            try:
                services["roles"].create_custom_role(
                    name=name,
                    description=description,
                    permission_keys=selected,
                    clone_from_role_id=clone_from,
                )
                st.rerun()
            except ValidationError as exc:
                st.error(str(exc))


@st.dialog("Edit Role", on_dismiss=make_dismiss_handler(EDIT_FLAG))
def _edit_role_dialog(services: dict, role) -> None:
    options = _permission_options(services)
    with st.form("access_role_edit_form"):
        name = st.text_input("Name", value=role.name)
        description = st.text_input("Description", value=role.description)
        selected = st.multiselect(
            "Permissions",
            options=options,
            default=[p for p in role.permission_keys if p in options],
        )
        if st.form_submit_button("Save role", type="primary"):
            try:
                services["roles"].update_custom_role(
                    role.id,
                    name=name,
                    description=description,
                    permission_keys=selected,
                )
                clear_dialog_flags(EDIT_FLAG)
                st.rerun()
            except ValidationError as exc:
                st.error(str(exc))


@st.dialog("Delete Role", on_dismiss=make_dismiss_handler(DELETE_FLAG))
def _delete_role_dialog(services: dict, role) -> None:
    st.write(f"Delete custom role **{role.name}**? This cannot be undone.")
    col_yes, col_no = st.columns(2)
    if col_yes.button("Delete", type="primary", use_container_width=True):
        try:
            services["roles"].delete_custom_role(role.id)
            clear_dialog_flags(DELETE_FLAG)
            st.rerun()
        except ValidationError as exc:
            st.error(str(exc))
    if col_no.button("Cancel", use_container_width=True):
        clear_dialog_flags(DELETE_FLAG)
        st.rerun()


@st.dialog("Role details", on_dismiss=make_dismiss_handler(VIEW_FLAG))
def _view_role_dialog(role) -> None:
    kind = "System" if role.is_system else "Custom"
    st.markdown(f"**{role.name}**")
    st.caption(f"{kind} · {len(role.permission_keys or [])} permissions")
    if role.description:
        st.write(role.description)
    keys = list(role.permission_keys or [])
    if not keys:
        st.info("No permissions on this role.")
        return
    # Group by first segment for readability
    groups: dict[str, list[str]] = {}
    for key in keys:
        groups.setdefault(key.split(".", 1)[0], []).append(key)
    for module in sorted(groups):
        with st.expander(f"{module} ({len(groups[module])})", expanded=False):
            st.code("\n".join(sorted(groups[module])), language=None)


def _role_card(role, index: int) -> None:
    with st.container(border=True):
        st.markdown(f"**{role.name}**")
        kind = "System" if role.is_system else "Custom"
        tone = "blue" if role.is_system else "violet"
        st.markdown(status_badge(kind, tone, compact=True), unsafe_allow_html=True)
        st.caption(role.description or "—")
        st.caption(f"{len(role.permission_keys or [])} permissions")

        if role.is_system:
            if st.button(
                "View",
                key=f"access_role_view_{index}_{role.id}",
                use_container_width=True,
            ):
                clear_all_dialog_flags()
                st.session_state[VIEW_FLAG] = role.id
                st.rerun()
        else:
            b1, b2 = st.columns(2)
            if b1.button(
                "Edit",
                key=f"access_role_edit_{index}_{role.id}",
                use_container_width=True,
            ):
                clear_all_dialog_flags()
                st.session_state[EDIT_FLAG] = role.id
                st.rerun()
            if b2.button(
                "Delete",
                key=f"access_role_del_{index}_{role.id}",
                use_container_width=True,
            ):
                clear_all_dialog_flags()
                st.session_state[DELETE_FLAG] = role.id
                st.rerun()


def _load_roles(services, filters, sort):
    try:
        return services["roles"].list_roles()
    except Exception:
        return []


def _render_cards(page_roles, services):
    render_card_grid(
        page_roles,
        lambda role, i: _role_card(role, i),
        suffix="access_roles",
        card_min_width=240,
    )


def render(services: dict):
    if not require_page_access(services, "roles-settings"):
        return

    system_roles = [r for r in services["roles"].list_roles() if r.is_system]
    bar = render_list(
        ROLES,
        services=services,
        load_fn=_load_roles,
        card_renderer=_render_cards,
        primary_label="Create Role",
        primary_key="access_roles_add_btn",
        count_label="roles",
        empty_text="No roles found.",
        page_key_nav="roles_settings",
    )
    if bar.get("primary_clicked"):
        clear_all_dialog_flags()
        _create_role_dialog(services, system_roles)

    for flag, dialog in (
        (VIEW_FLAG, lambda r: _view_role_dialog(r)),
        (EDIT_FLAG, lambda r: _edit_role_dialog(services, r)),
        (DELETE_FLAG, lambda r: _delete_role_dialog(services, r)),
    ):
        pending_id = st.session_state.get(flag)
        if not pending_id:
            continue
        role = services["roles"].get_role(pending_id)
        if role is None:
            clear_dialog_flags(flag)
            break
        if flag in (EDIT_FLAG, DELETE_FLAG) and role.is_system:
            clear_dialog_flags(flag)
            break
        dialog(role)
        break
