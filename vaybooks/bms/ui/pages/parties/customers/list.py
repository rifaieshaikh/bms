import streamlit as st

from vaybooks.bms.domain.parties.customers.entities import CustomerInput
from vaybooks.bms.domain.shared.exceptions import (
    DuplicateCustomerError,
    ValidationError,
)
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.parties.customer_card import customer_card
from vaybooks.bms.ui.components.parties.customer_form import render_customer_form
from vaybooks.bms.ui.components.common.list_view import render_list
from vaybooks.bms.ui.dialog_utils import (
    clear_all_dialog_flags,
    make_dismiss_handler,
    register_armed_dialog,
)
from vaybooks.bms.ui.keyboard.dialog_actions import (
    consume_submit,
    open_dialog,
)
from vaybooks.bms.ui.keyboard.wired import mark_wired
from vaybooks.bms.ui.styles import render_card_grid
from vaybooks.bms.ui.list_schemas import CUSTOMERS

C_ADD = "customer_add_dialog"
C_EDIT = "customer_edit_dialog"
C_DUP_CUSTOMER_ID = "customer_duplicate_existing_id"
SUBMIT_ADD = "submit_customer_add"
SUBMIT_EDIT = "submit_customer_edit"


def _open_add_customer() -> None:
    clear_all_dialog_flags()
    st.session_state.pop(C_DUP_CUSTOMER_ID, None)
    open_dialog(C_ADD, submit_key=SUBMIT_ADD, clear_others=False)
    mark_wired("customers.add", "list.primary", "dialog.save", "customers.create")


def _open_edit_customer(customer_id: str) -> None:
    clear_all_dialog_flags()
    open_dialog(C_EDIT, submit_key=SUBMIT_EDIT, value=customer_id, clear_others=False)
    mark_wired("customers.save", "dialog.save", "list.edit_nth.1")


def _render_duplicate_customer_warning(existing_customer_id: str, customer_service) -> None:
    existing = customer_service.get_customer_detail(existing_customer_id)
    label = existing.customer_name if existing else "existing customer"
    st.warning(f"A customer with this phone or GSTIN already exists: **{label}**")
    if st.button("Open existing customer", key="customer_open_existing", type="primary"):
        st.session_state.pop(C_ADD, None)
        st.session_state.pop(C_DUP_CUSTOMER_ID, None)
        navigation.go_to_detail("customer_detail", existing_customer_id)
        st.rerun()


def _do_create_customer(customer_service, customer_input: CustomerInput) -> None:
    try:
        customer = customer_service.create_customer(customer_input)
        st.session_state.pop(C_ADD, None)
        st.session_state.pop(C_DUP_CUSTOMER_ID, None)
        st.success(f"Created customer: {customer.customer_name}")
        st.rerun()
    except DuplicateCustomerError as exc:
        st.session_state[C_DUP_CUSTOMER_ID] = exc.existing_customer_id
        st.rerun()
    except ValidationError as exc:
        st.error(str(exc))


def _do_update_customer(
    customer_service, customer_id: str, customer_input: CustomerInput
) -> None:
    try:
        customer_service.update_customer(customer_id, customer_input)
        st.session_state.pop(C_EDIT, None)
        st.success("Customer updated")
        st.rerun()
    except DuplicateCustomerError as exc:
        st.session_state[C_DUP_CUSTOMER_ID] = exc.existing_customer_id
        st.error(str(exc))
    except ValidationError as exc:
        st.error(str(exc))


@st.dialog("Add Customer", width="large", on_dismiss=make_dismiss_handler(C_ADD))
def _add_customer_dialog(customer_service):
    mark_wired("dialog.save", "customers.create")
    dup_id = st.session_state.get(C_DUP_CUSTOMER_ID)
    if dup_id:
        _render_duplicate_customer_warning(dup_id, customer_service)

    customer_input = render_customer_form("c_add")

    cols = st.columns(2)
    do_create = cols[0].button(
        "Create Customer", type="primary", use_container_width=True
    ) or consume_submit(SUBMIT_ADD)
    if do_create:
        _do_create_customer(customer_service, customer_input)
    if cols[1].button("Cancel", use_container_width=True):
        st.session_state.pop(C_ADD, None)
        st.session_state.pop(C_DUP_CUSTOMER_ID, None)
        st.rerun()


@st.dialog("Edit Customer", width="large", on_dismiss=make_dismiss_handler(C_EDIT))
def _edit_customer_dialog(customer_service, customer_id: str):
    mark_wired("dialog.save", "customers.save")
    customer = customer_service.get_customer_detail(customer_id)
    if not customer:
        st.error("Customer not found")
        return

    customer_input = render_customer_form("c_edit", customer=customer)

    cols = st.columns(2)
    do_save = cols[0].button(
        "Save Changes", type="primary", use_container_width=True
    ) or consume_submit(SUBMIT_EDIT)
    if do_save:
        _do_update_customer(customer_service, customer_id, customer_input)
    if cols[1].button("Cancel", use_container_width=True):
        st.session_state.pop(C_EDIT, None)
        st.rerun()


def _load_customers(services, filters, sort):
    customers = services["customers"].list_all_customers()
    accounting = services.get("accounting")
    try:
        counts = services["orders"].order_counts_by_customer()
    except Exception:
        counts = {}
    try:
        balances = (
            accounting.customer_balances_by_customer() if accounting else {}
        )
    except Exception:
        balances = {}
    for customer in customers:
        cid = str(customer.id)
        setattr(customer, "order_count", counts.get(cid, 0))
        setattr(customer, "current_balance", balances.get(cid, 0.0))
    return customers


def _render_cards(page_customers, services):
    def _render(customer, _i):
        edit_clicked = customer_card(
            customer,
            getattr(customer, "order_count", 0),
            getattr(customer, "current_balance", 0.0),
            f"cust_{customer.id}",
        )
        if edit_clicked:
            _open_edit_customer(customer.id)
            st.rerun()

    render_card_grid(page_customers, _render, suffix="customers")


def render(services: dict):
    mark_wired("customers.add", "list.filters.open", "list.sort.open", "list.primary")
    bar = render_list(
        CUSTOMERS,
        services=services,
        load_fn=_load_customers,
        card_renderer=_render_cards,
        primary_label="Add Customer",
        primary_key="customers_add_btn",
        count_label="customers",
        empty_text="No customers found.",
        page_key_nav="customers_list",
    )
    if bar["primary_clicked"]:
        _open_add_customer()
    if bar.get("view_nth"):
        navigation.go_to_detail("customer_detail", bar["view_nth"])
    if bar.get("edit_nth"):
        _open_edit_customer(bar["edit_nth"])
        st.rerun()
    if st.session_state.get(C_ADD):
        # Ensure submit map is present if dialog was opened without open_dialog
        from vaybooks.bms.ui.keyboard.context import get_submit_map

        get_submit_map().setdefault(C_ADD, SUBMIT_ADD)
        register_armed_dialog(C_ADD)
        _add_customer_dialog(services["customers"])
    if st.session_state.get(C_EDIT):
        from vaybooks.bms.ui.keyboard.context import get_submit_map

        get_submit_map().setdefault(C_EDIT, SUBMIT_EDIT)
        register_armed_dialog(C_EDIT)
        _edit_customer_dialog(services["customers"], st.session_state[C_EDIT])
