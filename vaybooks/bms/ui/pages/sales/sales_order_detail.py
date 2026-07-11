"""Sales order detail."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.delivery_note_dialog import arm_dn_dialog, open_dn_dialog_if_armed


def render(services: dict) -> None:
    order_id = navigation.current_detail_id("sales_order_detail")
    if not order_id:
        st.warning("Sales order not specified")
        return

    sales = services["sales"]
    order = sales.get_sales_order(order_id)
    if not order:
        st.warning("Sales order not found")
        return

    if st.button("← Back", key="so_detail_back"):
        navigation.go_back_to_list("sales_orders", "sales_orders_list")
        return

    st.title(order.so_number)
    st.caption(f"Customer: {order.customer_name}")
    st.caption(f"Status: {order.status.value}")
    st.caption(f"Order date: {order.order_date}")

    for line in order.lines:
        with st.container(border=True):
            st.write(line.product_name or line.product_id)
            st.caption(
                f"Ordered {line.qty_ordered:g} · Delivered {line.qty_delivered:g} · "
                f"Rate ₹{line.rate:,.2f}"
            )

    if order.status.value not in ("Cancelled", "Closed", "Delivered"):
        if st.button("Deliver against SO", type="primary", key="so_deliver_btn"):
            arm_dn_dialog(so_id=order.id)
            st.rerun()

    open_dn_dialog_if_armed(services)
