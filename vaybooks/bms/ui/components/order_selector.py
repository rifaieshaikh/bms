import streamlit as st

from vaybooks.bms.application.order_app_service import OrderAppService


def order_selector(services: dict, key_prefix: str = "order"):
    order_service: OrderAppService = services["orders"]
    search = st.text_input(
        "Search Customization Order (name, phone, order #, bill #)",
        key=f"{key_prefix}_search",
    )
    orders = order_service.search_customization_orders(search) if search else []

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
