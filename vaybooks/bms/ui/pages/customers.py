import streamlit as st

from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.ui.components.customer_card import customer_card
from vaybooks.bms.ui.components.list_view import render_list
from vaybooks.bms.ui.styles import render_card_grid
from vaybooks.bms.ui.list_schemas import CUSTOMERS


@st.dialog("Add Customer", width="medium")
def _add_customer_dialog(customer_service):
    name = st.text_input("Customer Name", key="add_name")
    phone = st.text_input("Phone Number", key="add_phone")
    alt_phone = st.text_input("Alternate Phone", key="add_alt")
    address = st.text_area("Address", key="add_addr")
    notes = st.text_area("Notes", key="add_notes")

    if st.button("Create Customer", type="primary"):
        if name and phone:
            try:
                customer = customer_service.create_customer(
                    name, phone, alt_phone or None, address, notes
                )
                st.success(
                    f"Customer submission for {customer.customer_name} saved successfully."
                )
                st.rerun()
            except ValidationError as exc:
                st.error(str(exc))
        else:
            st.error("Name and phone are required")


@st.dialog("Edit Customer", width="medium")
def _edit_customer_dialog(customer_service, customer_id: str):
    customer = customer_service.get_customer_detail(customer_id)
    if not customer:
        st.error("Customer not found")
        return

    name = st.text_input("Customer Name", value=customer.customer_name, key="edit_name")
    phone = st.text_input("Phone Number", value=customer.phone_number, key="edit_phone")
    alt_phone = st.text_input(
        "Alternate Phone",
        value=customer.alternate_phone_number or "",
        key="edit_alt",
    )
    address = st.text_area("Address", value=customer.address or "", key="edit_addr")
    notes = st.text_area("Notes", value=customer.notes or "", key="edit_notes")

    if st.button("Save Changes", type="primary"):
        try:
            customer_service.update_customer(
                customer_id, name, phone, alt_phone or None, address, notes
            )
            st.success("Customer updated")
            st.rerun()
        except Exception as e:
            st.error(str(e))


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
    customer_service = services["customers"]

    def _render(customer, _i):
        edit_clicked = customer_card(
            customer,
            getattr(customer, "order_count", 0),
            getattr(customer, "current_balance", 0.0),
            f"cust_{customer.id}",
        )
        if edit_clicked:
            _edit_customer_dialog(customer_service, customer.id)

    render_card_grid(page_customers, _render, suffix="customers")


def render(services: dict):
    bar = render_list(
        CUSTOMERS,
        services=services,
        load_fn=_load_customers,
        card_renderer=_render_cards,
        primary_label="Add Customer",
        primary_key="customers_add_btn",
        count_label="customers",
        empty_text="No customers found.",
    )
    if bar["primary_clicked"]:
        _add_customer_dialog(services["customers"])
