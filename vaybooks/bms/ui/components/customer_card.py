import streamlit as st

from vaybooks.bms.domain.customers.entities import Customer


def customer_card(customer: Customer, order_count: int, key_prefix: str) -> tuple[bool, bool]:
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
            view_orders_clicked = st.button(
                "View Orders",
                key=f"{key_prefix}_orders",
                use_container_width=True,
            )

    return edit_clicked, view_orders_clicked
