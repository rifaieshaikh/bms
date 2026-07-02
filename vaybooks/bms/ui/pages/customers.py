import streamlit as st

from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.customer_card import customer_card


@st.dialog("Add Customer", width="medium")
def _add_customer_dialog(customer_service):
    name = st.text_input("Customer Name", key="add_name")
    phone = st.text_input("Phone Number", key="add_phone")
    alt_phone = st.text_input("Alternate Phone", key="add_alt")
    address = st.text_area("Address", key="add_addr")
    notes = st.text_area("Notes", key="add_notes")

    if st.button("Create Customer", type="primary"):
        if name and phone:
            customer = customer_service.create_customer(
                name, phone, alt_phone or None, address, notes
            )
            st.success(f"Created customer: {customer.customer_name}")
            st.rerun()
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


def render(services: dict):
    st.title("Customers")
    customer_service = services["customers"]
    order_service = services["orders"]

    header_cols = st.columns([4, 1])
    with header_cols[0]:
        query = st.text_input(
            "Search by name or phone",
            key="cust_search",
            placeholder="Search customers...",
        )
    with header_cols[1]:
        if st.button("Add Customer", type="primary", use_container_width=True):
            _add_customer_dialog(customer_service)

    customers = customer_service.search_customers(query)
    if not customers:
        st.info("No customers found.")
        return

    order_counts = order_service.order_counts_by_customer()

    cols = st.columns(3)
    for index, customer in enumerate(customers):
        order_count = order_counts.get(customer.id, 0)
        with cols[index % 3]:
            edit_clicked, view_orders_clicked = customer_card(
                customer, order_count, f"cust_{customer.id}"
            )
            if edit_clicked:
                _edit_customer_dialog(customer_service, customer.id)
            if view_orders_clicked:
                st.session_state.orders_customer_filter = customer.id
                if navigation.customization_orders_page is not None:
                    st.switch_page(navigation.customization_orders_page)
                else:
                    st.error("Orders page is not available.")
