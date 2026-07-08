import streamlit as st

from vaybooks.bms.domain.customers.entities import Customer
from vaybooks.bms.ui import navigation


def customer_card(customer: Customer, order_count: int, key_prefix: str) -> bool:
    with st.container(border=True):
        st.markdown(f"**{customer.customer_name}**")
        st.write(customer.phone_number)
        st.write(f"Orders: {order_count}")

        col1, col2 = st.columns(2)
        with col1:
            edit_clicked = st.button(
                "Edit",
                key=f"{key_prefix}_edit",
                use_container_width=True,
            )
        with col2:
            if st.button(
                "View",
                key=f"{key_prefix}_view",
                use_container_width=True,
            ):
                navigation.go_to_detail("customer_detail", customer.id)

    return edit_clicked
