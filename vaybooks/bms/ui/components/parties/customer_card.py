import streamlit as st

from vaybooks.bms.domain.parties.customers.entities import Customer
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.shared import CardAction, card


def _format_balance(balance: float) -> str:
    if abs(balance) < 0.01:
        return "Settled"
    if balance > 0:
        return f"Due \u20b9{balance:,.0f}"
    return f"Advance \u20b9{abs(balance):,.0f}"


def customer_card(
    customer: Customer, order_count: int, balance: float, key_prefix: str
) -> bool:
    color = "red" if balance > 0.01 else ("green" if balance < -0.01 else "gray")
    clicked = {"edit": False}

    def _on_edit() -> None:
        clicked["edit"] = True

    def _on_view() -> None:
        navigation.go_to_detail("customer_detail", customer.id)

    with st.container(border=True):
        card(
            customer.customer_name,
            badges=[
                (f"{order_count} orders", "blue"),
                (_format_balance(balance), color),
            ],
            caption_lines=[("phone", customer.phone_number)]
            + ([f"GSTIN: {customer.gstin}"] if customer.gstin else []),
            actions=[
                CardAction("Edit", key=f"{key_prefix}_edit", kind="secondary", on_click=_on_edit),
                CardAction("View", key=f"{key_prefix}_view", on_click=_on_view),
            ],
        )

    return clicked["edit"]
