"""Access — Users: card list with dialog-based CRUD."""

from __future__ import annotations

import streamlit as st

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

EDIT_FLAG = "access_user_edit_flag"
PWD_FLAG = "access_user_pwd_flag"
TOGGLE_FLAG = "access_user_toggle_flag"


def _role_options(roles):
    labels = {r.id: r.name for r in roles}
    return [r.id for r in roles], labels


def _role_names(user, role_labels: dict) -> str:
    names = [role_labels.get(rid, rid) for rid in (user.role_ids or [])]
    return ", ".join(names) if names else "—"


def _match_active(user, _value) -> bool:
    return bool(getattr(user, "active", False))


USERS = ListSchema(
    entity_key="access_users",
    title="Users",
    filter_fields=[
        FilterField("username", "Username", F.REGEX),
        FilterField("display_name", "Display name", F.REGEX),
        FilterField(
            "active_only",
            "Active only",
            F.CHECKBOX,
            match=_match_active,
        ),
    ],
    sort_options=[
        SortOption("display_name", "Display name"),
        SortOption("username", "Username"),
        SortOption("created_at", "Created"),
    ],
    default_sort="display_name",
    default_desc=False,
    page_size=CARD_PAGE_SIZE,
)


@st.dialog("Add User")
def _add_user_dialog(services: dict, roles) -> None:
    role_ids, labels = _role_options(roles)
    with st.form("access_user_add_form"):
        username = st.text_input("Username")
        display_name = st.text_input("Display name")
        password = st.text_input("Password", type="password")
        selected = st.multiselect(
            "Roles", options=role_ids, format_func=lambda rid: labels.get(rid, rid)
        )
        if st.form_submit_button("Create user", type="primary"):
            try:
                services["users"].create_user(
                    username=username,
                    display_name=display_name,
                    password=password,
                    role_ids=selected,
                )
                st.rerun()
            except ValidationError as exc:
                st.error(str(exc))


@st.dialog("Edit User", on_dismiss=make_dismiss_handler(EDIT_FLAG))
def _edit_user_dialog(services: dict, user, roles) -> None:
    role_ids, labels = _role_options(roles)
    with st.form("access_user_edit_form"):
        st.text_input("Username", value=user.username, disabled=True)
        display_name = st.text_input("Display name", value=user.display_name)
        selected = st.multiselect(
            "Roles",
            options=role_ids,
            default=[rid for rid in user.role_ids if rid in role_ids],
            format_func=lambda rid: labels.get(rid, rid),
        )
        active = st.checkbox("Active", value=user.active)
        if st.form_submit_button("Save", type="primary"):
            try:
                services["users"].update_user(
                    user.id,
                    display_name=display_name,
                    role_ids=selected,
                    active=active,
                )
                clear_dialog_flags(EDIT_FLAG)
                st.rerun()
            except ValidationError as exc:
                st.error(str(exc))


@st.dialog("Reset Password", on_dismiss=make_dismiss_handler(PWD_FLAG))
def _reset_password_dialog(services: dict, user) -> None:
    st.caption(f"Set a new password for **{user.username}**.")
    with st.form("access_user_pwd_form"):
        password = st.text_input("New password", type="password")
        confirm = st.text_input("Confirm password", type="password")
        if st.form_submit_button("Reset password", type="primary"):
            if password != confirm:
                st.error("Passwords do not match")
            else:
                try:
                    services["users"].set_password(user.id, password)
                    clear_dialog_flags(PWD_FLAG)
                    st.rerun()
                except ValidationError as exc:
                    st.error(str(exc))


@st.dialog("Confirm", on_dismiss=make_dismiss_handler(TOGGLE_FLAG))
def _toggle_active_dialog(services: dict, user) -> None:
    verb = "Deactivate" if user.active else "Activate"
    st.write(f"{verb} user **{user.username}**?")
    col_yes, col_no = st.columns(2)
    if col_yes.button(verb, type="primary", use_container_width=True):
        try:
            services["users"].update_user(user.id, active=not user.active)
            clear_dialog_flags(TOGGLE_FLAG)
            st.rerun()
        except ValidationError as exc:
            st.error(str(exc))
    if col_no.button("Cancel", use_container_width=True):
        clear_dialog_flags(TOGGLE_FLAG)
        st.rerun()


def _user_card(user, role_labels: dict, index: int) -> None:
    with st.container(border=True):
        name = (user.display_name or user.username or "").strip() or "—"
        st.markdown(f"**{name}**")
        st.caption(f"@{user.username}")
        badge = status_badge(
            "Active" if user.active else "Inactive",
            "green" if user.active else "gray",
            compact=True,
        )
        st.markdown(badge, unsafe_allow_html=True)
        st.caption(_role_names(user, role_labels))

        b1, b2 = st.columns(2)
        if b1.button(
            "Edit",
            key=f"access_user_edit_{index}_{user.id}",
            use_container_width=True,
        ):
            clear_all_dialog_flags()
            st.session_state[EDIT_FLAG] = user.id
            st.rerun()
        if b2.button(
            "Password",
            key=f"access_user_pwd_{index}_{user.id}",
            use_container_width=True,
        ):
            clear_all_dialog_flags()
            st.session_state[PWD_FLAG] = user.id
            st.rerun()

        toggle_label = "Disable" if user.active else "Enable"
        if st.button(
            toggle_label,
            key=f"access_user_toggle_{index}_{user.id}",
            use_container_width=True,
        ):
            clear_all_dialog_flags()
            st.session_state[TOGGLE_FLAG] = user.id
            st.rerun()


def _load_users(services, filters, sort):
    try:
        return services["users"].list_users()
    except Exception:
        return []


def _render_cards(page_users, services):
    roles = services["roles"].list_roles()
    _, role_labels = _role_options(roles)
    render_card_grid(
        page_users,
        lambda user, i: _user_card(user, role_labels, i),
        suffix="access_users",
        card_min_width=240,
    )


def render(services: dict):
    if not require_page_access(services, "users-settings"):
        return

    roles = services["roles"].list_roles()
    bar = render_list(
        USERS,
        services=services,
        load_fn=_load_users,
        card_renderer=_render_cards,
        primary_label="Add User",
        primary_key="access_users_add_btn",
        count_label="users",
        empty_text="No users yet. Add one to get started.",
        page_key_nav="users_settings",
    )
    if bar.get("primary_clicked"):
        clear_all_dialog_flags()
        _add_user_dialog(services, roles)

    for flag, dialog in (
        (EDIT_FLAG, lambda u: _edit_user_dialog(services, u, roles)),
        (PWD_FLAG, lambda u: _reset_password_dialog(services, u)),
        (TOGGLE_FLAG, lambda u: _toggle_active_dialog(services, u)),
    ):
        pending_id = st.session_state.get(flag)
        if pending_id:
            user = services["users"].get_user(pending_id)
            if user is None:
                clear_dialog_flags(flag)
            else:
                dialog(user)
            break
