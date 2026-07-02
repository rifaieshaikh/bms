import streamlit as st

from vaybooks.bms.domain.orders.entities import CustomizationOrder


def bill_selector(order: CustomizationOrder, key: str = "bill_sel"):
    if not order or not order.bill_numbers:
        st.warning("No bill numbers on this order")
        return None
    options = {
        f"{b.bill_number} - {b.item_description}": b.bill_id
        for b in order.bill_numbers
    }
    choice = st.selectbox("Bill Number", list(options.keys()), key=key)
    return options[choice]
