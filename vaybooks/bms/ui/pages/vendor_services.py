import streamlit as st

from vaybooks.bms.ui.components.list_view import render_list
from vaybooks.bms.ui.styles import render_card_grid
from vaybooks.bms.ui.list_schemas import SERVICES

PENDING_EDIT_SERVICE = "pending_edit_vendor_service"
NEW_EXPENSE_OPTION = "➕ Create new expense account…"


def _expense_account_options(accounting_service) -> dict:
    return {a.account_name: a.id for a in accounting_service.get_expense_accounts()}


def _resolve_expense_account(accounting_service, choice: str, new_name: str):
    """Return an expense account id for the chosen option, creating one if asked."""
    if choice == NEW_EXPENSE_OPTION:
        if not new_name.strip():
            st.error("Enter a name for the new expense account")
            return None
        account = accounting_service.create_account(new_name.strip(), "Expense")
        return account.id
    options = _expense_account_options(accounting_service)
    return options.get(choice)


@st.dialog("Add Service")
def _add_service_dialog(service_config, accounting_service):
    name = st.text_input("Service / Material Name", key="add_svc_name")
    options = list(_expense_account_options(accounting_service).keys())
    options.append(NEW_EXPENSE_OPTION)
    choice = st.selectbox("Expense Account", options, key="add_svc_account")
    new_name = ""
    if choice == NEW_EXPENSE_OPTION:
        new_name = st.text_input("New Expense Account Name", key="add_svc_new_acc")

    if st.button("Create Service", type="primary"):
        if not name.strip():
            st.error("Service name is required")
            return
        try:
            expense_account_id = _resolve_expense_account(
                accounting_service, choice, new_name
            )
            if not expense_account_id:
                return
            service_config.create_service(name, expense_account_id)
            st.success(f"Created {name}")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


@st.dialog("Edit Service")
def _edit_service_dialog(service_config, accounting_service, service_id: str):
    service = service_config.get_service(service_id)
    if not service:
        st.error("Service not found")
        return

    name = st.text_input(
        "Service / Material Name", value=service.service_name, key="edit_svc_name"
    )
    account_options = _expense_account_options(accounting_service)
    names = list(account_options.keys())
    current_index = 0
    for i, acc_id in enumerate(account_options.values()):
        if acc_id == service.expense_account_id:
            current_index = i
            break
    names.append(NEW_EXPENSE_OPTION)
    choice = st.selectbox(
        "Expense Account", names, index=current_index, key="edit_svc_account"
    )
    new_name = ""
    if choice == NEW_EXPENSE_OPTION:
        new_name = st.text_input("New Expense Account Name", key="edit_svc_new_acc")

    is_active = st.checkbox("Active", value=service.is_active, key="edit_svc_active")

    if st.button("Save Changes", type="primary"):
        if not name.strip():
            st.error("Service name is required")
            return
        try:
            expense_account_id = _resolve_expense_account(
                accounting_service, choice, new_name
            )
            if not expense_account_id:
                return
            service_config.update_service(
                service_id, name, expense_account_id, is_active
            )
            st.success("Service updated")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def _service_card(service, account_names: dict, index: int):
    with st.container(border=True):
        status = "Active" if service.is_active else "Inactive"
        st.markdown(f"**{service.service_name}**")
        st.caption(status)
        st.write(
            "Expense Account: "
            + account_names.get(service.expense_account_id, "⚠️ Not found")
        )
        if st.button(
            "Edit",
            key=f"edit_svc_btn_{index}_{service.id}",
            use_container_width=True,
        ):
            st.session_state[PENDING_EDIT_SERVICE] = service.id


def _load_services(services, filters, sort):
    try:
        return services["vendor_services"].list_services(active_only=False)
    except Exception:
        return []


def _render_cards(page_services, services):
    accounting_service = services["accounting"]
    account_names = {
        a.id: a.account_name
        for a in accounting_service.list_accounts(active_only=False)
    }
    render_card_grid(
        page_services,
        lambda service, i: _service_card(service, account_names, i),
        suffix="services",
    )


def render(services: dict):
    service_config = services["vendor_services"]
    accounting_service = services["accounting"]
    bar = render_list(
        SERVICES,
        services=services,
        load_fn=_load_services,
        card_renderer=_render_cards,
        primary_label="Add Service",
        primary_key="services_add_btn",
        count_label="services",
        empty_text="No services configured yet.",
    )
    if bar["primary_clicked"]:
        _add_service_dialog(service_config, accounting_service)

    pending = st.session_state.pop(PENDING_EDIT_SERVICE, None)
    if pending:
        _edit_service_dialog(service_config, accounting_service, pending)
