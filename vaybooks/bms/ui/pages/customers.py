import streamlit as st

from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.customer_card import customer_card
from vaybooks.bms.ui.pagination import CARD_PAGE_SIZE, paginate_list, render_page_controls
from vaybooks.bms.ui.session_keys import ORDERS_KEEP_FILTERS

def _load_order_counts(order_service) -> dict:
    try:
        return order_service.order_counts_by_customer()
    except Exception:
        return {}


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


def render(services: dict):
    st.title("Customers")
    customer_service = services["customers"]
    order_service = services["orders"]
    order_counts = _load_order_counts(order_service)

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
        if query.strip():
            st.info("No customers match your search.")
        else:
            st.info("No customers found.")
        return

    st.caption(f"Customer list displays {len(customers)} records")

    page_customers, page, total_pages = paginate_list(
        customers,
        page_key="cust_page",
        page_size=CARD_PAGE_SIZE,
        filter_key="cust_search",
        filter_value=query,
    )

    cols = st.columns(3)
    for index, customer in enumerate(page_customers):
        order_count = order_counts.get(str(customer.id), 0)
        with cols[index % 3]:
            edit_clicked, view_orders_clicked = customer_card(
                customer, order_count, f"cust_{customer.id}"
            )
            if edit_clicked:
                _edit_customer_dialog(customer_service, customer.id)
            if view_orders_clicked:
                st.session_state.orders_customer_filter = customer.id
                st.session_state[ORDERS_KEEP_FILTERS] = True
                if navigation.customization_orders_page is not None:
                    st.switch_page(navigation.customization_orders_page)
                else:
                    st.error("Orders page is not available.")

    render_page_controls(
        page, total_pages, len(customers),
        page_key="cust_page", prev_key="cust_prev", next_key="cust_next",
        label="customers",
    )
