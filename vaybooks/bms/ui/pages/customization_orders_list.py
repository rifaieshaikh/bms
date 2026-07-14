"""Customization Orders list route (filter/sort + new-order dialog)."""

import streamlit as st

from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.list_view import render_list
from vaybooks.bms.ui.components.order_card import order_cards
from vaybooks.bms.ui.list_schemas import ORDERS
from vaybooks.bms.ui.pages.customization_orders import _new_order_dialog
from vaybooks.bms.ui.session_keys import filters_key


def _load_orders(services, filters, sort):
    try:
        return services["orders"].search_customization_orders("")
    except Exception:
        return []


def _render_cards(page_orders, services):
    order_cards(page_orders)


def _apply_customer_deep_link(services) -> None:
    """`/orders?customer=<id>` (or session fallback) seeds the customer filter
    once, then strips it. Uses ``consume_list_param`` so it survives the query
    param being dropped across ``st.switch_page``."""
    customer_id = navigation.consume_list_param("orders_list", "customer")
    if not customer_id:
        return
    key = filters_key(ORDERS.entity_key)
    from vaybooks.bms.ui import filtering as F

    committed = st.session_state.setdefault(key, F.default_filters(ORDERS))
    committed["customer_id"] = customer_id
    st.session_state.pop(f"{ORDERS.entity_key}_flt_customer_id", None)


def render(services: dict):
    _apply_customer_deep_link(services)
    bar = render_list(
        ORDERS,
        services=services,
        load_fn=_load_orders,
        card_renderer=_render_cards,
        primary_label="New Order",
        primary_key="orders_new_btn",
        count_label="orders",
        empty_text="No orders found.",
        page_key_nav="orders_list",
    )
    if bar["primary_clicked"]:
        _new_order_dialog(services)
    if bar.get("view_nth"):
        navigation.go_to_detail("order_detail", bar["view_nth"])
