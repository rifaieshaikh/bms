"""Purchase order detail."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.grn_dialog import arm_grn_dialog, open_grn_dialog_if_armed


def render(services: dict) -> None:
    order_id = st.query_params.get("id")
    if not order_id:
        st.warning("Purchase order not specified")
        return

    purchases = services["purchases"]
    order = purchases.get_purchase_order(order_id)
    if not order:
        st.warning("Purchase order not found")
        return

    if st.button("← Back", key="po_detail_back"):
        navigation.go_back_to_list("purchase_orders_list", "purchase-orders")
        return

    st.title(order.po_number)
    st.caption(f"Vendor: {order.vendor_name}")
    st.caption(f"Status: {order.status.value}")
    st.caption(f"Order date: {order.order_date}")

    for line in order.lines:
        with st.container(border=True):
            st.write(line.product_name or line.product_id)
            st.caption(
                f"Ordered {line.qty_ordered:g} · Received {line.qty_received:g} · "
                f"Rate ₹{line.rate:,.2f}"
            )

    if order.status.value not in ("Cancelled", "Closed", "Received"):
        if st.button("Receive against PO", type="primary", key="po_receive_btn"):
            arm_grn_dialog(po_id=order.id)
            st.rerun()

    open_grn_dialog_if_armed(services)
