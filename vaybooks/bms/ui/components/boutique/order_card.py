from datetime import date, datetime

import streamlit as st

from vaybooks.bms.domain.boutique.orders.entities import CustomizationOrder
from vaybooks.bms.domain.boutique.orders.order_refs import compact_order_ref
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.styles import render_card_grid, status_badge


def _fmt_date(value) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime("%d %b %Y")
    return str(value) if value else "—"


def order_card(
    order: CustomizationOrder,
    key_prefix: str,
    *,
    view_label: str = "View",
    view_full_width: bool = True,
):
    with st.container(border=True):
        st.markdown(f"**{compact_order_ref(order.order_number)}**")
        st.caption(order.customer_name)
        st.markdown(status_badge(order.order_status.value), unsafe_allow_html=True)
        st.write(f"📅 {_fmt_date(order.expected_delivery_date)}")
        if st.button(
            view_label,
            key=f"{key_prefix}_view",
            use_container_width=view_full_width,
        ):
            navigation.go_to_detail("order_detail", order.id)


def order_cards(
    orders: list[CustomizationOrder],
    key_prefix: str = "ord",
    *,
    view_label: str = "View",
    view_full_width: bool = True,
):
    if not orders:
        st.info("No orders found.")
        return

    render_card_grid(
        orders,
        lambda order, _i: order_card(
            order,
            f"{key_prefix}_{order.id}",
            view_label=view_label,
            view_full_width=view_full_width,
        ),
        suffix=key_prefix,
    )
