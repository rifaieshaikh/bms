import streamlit as st

from vaybooks.bms.domain.parties.customers.entities import Customer
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.styles import status_badge


def _format_balance(balance: float) -> str:
    if abs(balance) < 0.01:
        return "Settled"
    if balance > 0:
        return f"Due \u20b9{balance:,.0f}"
    return f"Advance \u20b9{abs(balance):,.0f}"


def customer_card(
    customer: Customer, order_count: int, balance: float, key_prefix: str
) -> bool:
    with st.container(border=True):
        st.markdown(f"### {customer.customer_name}")
        st.write(f"\U0001f4de {customer.phone_number}")
        if customer.gstin:
            st.caption(f"GSTIN: {customer.gstin}")

        color = "red" if balance > 0.01 else ("green" if balance < -0.01 else "gray")
        badges = (
            status_badge(f"{order_count} orders", "blue")
            + " "
            + status_badge(_format_balance(balance), color)
        )
        st.markdown(badges, unsafe_allow_html=True)

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
                type="primary",
                use_container_width=True,
            ):
                navigation.go_to_detail("customer_detail", customer.id)

    return edit_clicked
