import streamlit as st

from vaybooks.bms.application.boutique.orders.service import OrderAppService
from vaybooks.bms.domain.identity.location_access import location_id_mongo_filter
from vaybooks.bms.ui.auth.session import working_location_list_context


def order_selector(services: dict, key_prefix: str = "order"):
    order_service: OrderAppService = services["orders"]
    working, accessible = working_location_list_context(services)
    filt = location_id_mongo_filter(working, accessible)
    search = st.text_input(
        "Search Customization Order (name, phone, order #, bill #)",
        key=f"{key_prefix}_search",
    )
    orders = (
        order_service.search_customization_orders(search, location_filter=filt)
        if search
        else []
    )

    selected_id = None
    if orders:
        options = {
            f"{o.order_number} - {o.customer_name} ({o.order_status.value})": o.id
            for o in orders
        }
        choice = st.selectbox(
            "Select Customization Order", list(options.keys()), key=f"{key_prefix}_sel"
        )
        selected_id = options[choice]
    return selected_id
