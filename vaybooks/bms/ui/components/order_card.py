import streamlit as st

from vaybooks.bms.domain.orders.entities import CustomizationOrder
from vaybooks.bms.domain.orders.order_refs import compact_order_ref
from vaybooks.bms.ui.session_keys import VIEW_ORDER_ID


def order_card(order: CustomizationOrder, key_prefix: str):
    with st.container(border=True):
        st.markdown(f"**{compact_order_ref(order.order_number)}**")
        st.write(order.customer_name)
        st.write(order.phone_number)
        st.caption(
            f"Status: {order.order_status.value} | "
            f"Items: {len(order.customization_items)} | "
            f"Advance: ₹{order.advance_amount:,.0f}"
        )
        bill_numbers = sorted({item.bill_number for item in order.customization_items})
        if bill_numbers:
            st.write(f"Bills: {', '.join(bill_numbers[:4])}")
        if st.button("View Order", key=f"{key_prefix}_view", use_container_width=True):
            st.session_state[VIEW_ORDER_ID] = order.id
            st.session_state["orders_open_detail"] = True


def order_cards(orders: list[CustomizationOrder], key_prefix: str = "ord"):
    if not orders:
        st.info("No orders found.")
        return

    cols = st.columns(3)
    for index, order in enumerate(orders):
        with cols[index % 3]:
            order_card(order, f"{key_prefix}_{order.id}")
