import streamlit as st

from vaybooks.bms.domain.customers.entities import Customer
from vaybooks.bms.ui.components.dashboard_cards import queue_customer_orders_navigation


def customer_card(customer: Customer, order_count: int, key_prefix: str) -> bool:
    with st.container(border=True):
        st.markdown(f"**{customer.customer_name}**")
        st.write(customer.phone_number)
        st.write(f"Orders: {order_count}")

        col1, col2 = st.columns(2)
        with col1:
            edit_clicked = st.button(
                "Edit Customer",
                key=f"{key_prefix}_edit",
                use_container_width=True,
            )
        with col2:
            st.button(
                "View Orders",
                key=f"{key_prefix}_orders",
                use_container_width=True,
                on_click=queue_customer_orders_navigation,
                args=(customer.id,),
            )

    return edit_clicked
