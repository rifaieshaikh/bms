"""Customer detail route (`?id=<customer_id>`): profile, edit, order history."""

import streamlit as st

from vaybooks.bms.domain.orders.order_refs import compact_order_ref
from vaybooks.bms.ui import navigation


def render(services: dict):
    customer_service = services["customers"]
    order_service = services["orders"]

    customer_id = navigation.current_detail_id("customer_detail")

    if st.button("← Back to customers", key="customer_back"):
        navigation.go_back_to_list("customers", "customers_list")
        return

    customer = customer_service.get_customer_detail(customer_id) if customer_id else None
    if not customer:
        st.error("Customer not found.")
        return

    st.title(customer.customer_name)

    with st.container(border=True):
        info = st.columns(3)
        info[0].write(f"**Phone:** {customer.phone_number}")
        info[1].write(f"**Alt:** {customer.alternate_phone_number or '—'}")
        try:
            counts = order_service.order_counts_by_customer()
        except Exception:
            counts = {}
        info[2].write(f"**Orders:** {counts.get(str(customer.id), 0)}")
        if customer.address:
            st.caption(f"Address: {customer.address}")
        if customer.notes:
            st.caption(f"Notes: {customer.notes}")

    with st.expander("Edit customer"):
        name = st.text_input("Customer Name", value=customer.customer_name,
                             key="cd_edit_name")
        phone = st.text_input("Phone Number", value=customer.phone_number,
                             key="cd_edit_phone")
        alt_phone = st.text_input("Alternate Phone",
                                 value=customer.alternate_phone_number or "",
                                 key="cd_edit_alt")
        address = st.text_area("Address", value=customer.address or "",
                              key="cd_edit_addr")
        notes = st.text_area("Notes", value=customer.notes or "", key="cd_edit_notes")
        if st.button("Save Changes", type="primary", key="cd_edit_save"):
            try:
                customer_service.update_customer(
                    customer.id, name, phone, alt_phone or None, address, notes
                )
                st.success("Customer updated")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    header = st.columns([3, 1])
    with header[0]:
        st.subheader("Orders")
    with header[1]:
        if st.button("View all orders →", use_container_width=True,
                     key="cd_view_orders"):
            navigation.go_to_list("orders_list", customer=customer.id)
            return

    try:
        orders = order_service.list_by_customer(customer.id)
    except Exception:
        orders = []
    if not orders:
        st.caption("No orders yet.")
        return
    for order in orders[:20]:
        with st.container(border=True):
            cols = st.columns([3, 1])
            cols[0].markdown(f"**{compact_order_ref(order.order_number)}**")
            cols[0].caption(
                f"Status: {order.order_status.value} | "
                f"Items: {len(order.customization_items)}"
            )
            if cols[1].button("Open →", key=f"cd_order_{order.id}",
                              use_container_width=True):
                navigation.go_to_detail("order_detail", order.id)
