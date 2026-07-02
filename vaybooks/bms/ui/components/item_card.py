import streamlit as st

from vaybooks.bms.ui.components.item_detail_panel import customization_item_detail_panel


def customization_item_card(
    services: dict,
    order,
    item,
    invoices: list,
    deliveries: list,
    key_prefix: str | None = None,
):
    prefix = key_prefix or item.item_id
    customization_item_detail_panel(
        services,
        order,
        item,
        invoices,
        deliveries,
        prefix,
        show_header=True,
        show_item_edit=True,
    )


def bill_card(
    services: dict,
    order,
    bill,
    invoices: list,
    deliveries: list,
):
    item = order.get_item_by_id(bill.bill_id)
    if item:
        with st.container(border=True):
            customization_item_card(services, order, item, invoices, deliveries)
