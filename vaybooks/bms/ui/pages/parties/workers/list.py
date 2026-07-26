import streamlit as st

from vaybooks.bms.application.parties.workers.activity_options import refs_from_keys
from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.ui.auth.session import can_permission
from vaybooks.bms.ui.components.common.list_view import render_list
from vaybooks.bms.ui.filtering import ListSchema, SortOption
from vaybooks.bms.ui.pages.access.users.list import (
    _location_options,
    _role_options,
    _validate_location_assignment,
)
from vaybooks.bms.ui.styles import render_card_grid


PENDING_EDIT_WORKER = "pending_edit_worker"


def _activity_options(services, worker=None) -> dict:
    """Picker options as ``{composite key: label}``.

    Options come from the module-aware aggregator (store always; customization
    when boutique is enabled; project when projects is enabled). When editing,
    the worker's existing assignments are kept selectable even if inactive or
    from a disabled module, so they are never silently stripped.
    """
    options_service = services["employee_activity_options"]
    options = {o.key: o.label for o in options_service.list_options(active_only=True)}
    if worker is not None:
        for option in options_service.options_for_refs(worker.activity_refs):
            options.setdefault(option.key, option.label)
    return options


def _can_manage_users(services: dict) -> bool:
    return can_permission(services, "settings.users.manage")


def _login_fields(services: dict, *, key_prefix: str) -> dict:
    """Render optional login fields. Returns payload used by create/update."""
    if not _can_manage_users(services):
        st.caption("You need user-management permission to create a system login.")
        return {"create_login": False}

    create_login = st.checkbox(
        "Create system login",
        key=f"{key_prefix}_create_login",
        help="Lets this employee sign in to VayBooks with a username and password.",
    )
    if not create_login:
        return {"create_login": False}

    roles = services["roles"].list_roles()
    role_ids, role_labels = _role_options(roles)
    location_ids, location_labels = _location_options(services)

    username = st.text_input("Username", key=f"{key_prefix}_username")
    password = st.text_input(
        "Password", type="password", key=f"{key_prefix}_password"
    )
    selected_roles = st.multiselect(
        "Roles",
        options=role_ids,
        format_func=lambda rid: role_labels.get(rid, rid),
        key=f"{key_prefix}_roles",
        help="Choose CRM, sales, or other roles this employee should have.",
    )
    selected_locations = st.multiselect(
        "Accessible locations",
        options=location_ids,
        format_func=lambda lid: location_labels.get(lid, lid),
        key=f"{key_prefix}_locations",
        help="Leave empty for all locations when the role allows it.",
    )
    return {
        "create_login": True,
        "username": username,
        "password": password,
        "role_ids": selected_roles,
        "location_ids": selected_locations,
    }


def _login_caption(services: dict, linked_user_id: str) -> str:
    if not linked_user_id:
        return "No system login"
    users = services.get("users")
    if users is None:
        return "System login linked"
    user = users.get_user(linked_user_id)
    if user is None:
        return "System login missing"
    status = "active" if user.active else "inactive"
    return f"Login: {user.username} ({status})"


@st.dialog("Add Employee")
def _add_worker_dialog(worker_service, services: dict):
    name = st.text_input("Employee Name", key="add_worker_name")
    hourly_rate = st.number_input(
        "Default hourly rate (₹)",
        min_value=0.0,
        value=0.0,
        step=50.0,
        key="add_worker_rate",
    )
    act_opts = _activity_options(services)
    selected = st.multiselect(
        "Activities",
        list(act_opts.keys()),
        format_func=lambda key: act_opts.get(key, key),
        key="add_worker_acts",
        placeholder="Select activities this employee can do…",
    )
    st.divider()
    login = _login_fields(services, key_prefix="add_worker")

    if st.button("Create Employee", type="primary"):
        if not name.strip():
            st.error("Employee name is required")
            return
        try:
            if login.get("create_login"):
                _validate_location_assignment(
                    login.get("role_ids") or [],
                    login.get("location_ids") or [],
                )
            worker_service.create_worker(
                name,
                refs_from_keys(selected),
                default_hourly_rate=hourly_rate,
                **login,
            )
            if login.get("create_login"):
                st.success(f"Created {name} with system login")
            else:
                st.success(f"Created {name}")
            st.rerun()
        except (ValidationError, Exception) as exc:
            st.error(str(exc))


@st.dialog("Edit Employee")
def _edit_worker_dialog(worker_service, services: dict, worker_id: str):
    worker = worker_service.get_worker(worker_id)
    if not worker:
        st.error("Employee not found")
        return

    act_opts = _activity_options(services, worker=worker)
    current_keys = [
        f"{ref.source}:{ref.activity_id}"
        for ref in worker.activity_refs
        if f"{ref.source}:{ref.activity_id}" in act_opts
    ]

    name = st.text_input("Employee Name", value=worker.worker_name, key="edit_worker_name")
    hourly_rate = st.number_input(
        "Default hourly rate (₹)",
        min_value=0.0,
        value=float(worker.default_hourly_rate or 0.0),
        step=50.0,
        key="edit_worker_rate",
    )
    selected = st.multiselect(
        "Activities",
        list(act_opts.keys()),
        default=current_keys,
        format_func=lambda key: act_opts.get(key, key),
        key="edit_worker_acts",
        placeholder="Select activities this employee can do…",
    )
    is_active = st.checkbox("Active", value=worker.is_active, key="edit_worker_active")

    st.divider()
    st.caption(_login_caption(services, worker.linked_user_id or ""))
    login = {"create_login": False}
    if not worker.linked_user_id:
        login = _login_fields(services, key_prefix="edit_worker")
    elif _can_manage_users(services):
        if st.button("Open Users", key="edit_worker_open_users"):
            from vaybooks.bms.ui import navigation

            navigation.go_to_list("users_settings")

    if st.button("Save Changes", type="primary"):
        if not name.strip():
            st.error("Employee name is required")
            return
        try:
            if login.get("create_login"):
                _validate_location_assignment(
                    login.get("role_ids") or [],
                    login.get("location_ids") or [],
                )
            worker_service.update_worker(
                worker_id,
                name,
                refs_from_keys(selected),
                is_active,
                default_hourly_rate=hourly_rate,
                **login,
            )
            st.success("Employee updated")
            st.rerun()
        except (ValidationError, Exception) as exc:
            st.error(str(exc))


def _worker_card(worker, services: dict, index: int):
    with st.container(border=True):
        status = "Active" if worker.is_active else "Inactive"
        st.markdown(f"**{worker.worker_name}**")
        st.caption(f"{status} · {_login_caption(services, worker.linked_user_id or '')}")
        options = services["employee_activity_options"].options_for_refs(
            worker.activity_refs
        )
        acts = [o.label for o in options]
        st.write("Activities: " + (", ".join(acts) if acts else "—"))
        if st.button(
            "Edit",
            key=f"edit_worker_btn_{index}_{worker.id}",
            width="stretch",
        ):
            st.session_state[PENDING_EDIT_WORKER] = worker.id


def _load_workers(services, filters, sort):
    try:
        return services["workers"].list_workers(active_only=False)
    except Exception:
        return []


def _render_cards(page_workers, services):
    render_card_grid(
        page_workers,
        lambda worker, i: _worker_card(worker, services, i),
        suffix="workers",
    )


def render(services: dict):
    worker_service = services["workers"]
    # Local schema (simple list page with only pagination/search handled by base component).
    WORKERS = ListSchema(
        entity_key="workers",
        title="Employees",
        filter_fields=[],
        sort_options=[
            SortOption("created_at", "Created"),
            SortOption("worker_name", "Employee name"),
        ],
        default_sort="created_at",
    )
    bar = render_list(
        WORKERS,
        services=services,
        load_fn=_load_workers,
        card_renderer=_render_cards,
        primary_label="Add Employee",
        primary_key="workers_add_btn",
        count_label="employees",
        empty_text="No employees configured yet.",
        page_key_nav="workers_list",
    )
    if bar["primary_clicked"]:
        _add_worker_dialog(worker_service, services)

    pending = st.session_state.pop(PENDING_EDIT_WORKER, None)
    if pending:
        _edit_worker_dialog(worker_service, services, pending)
