import streamlit as st

from vaybooks.bms.application.dtos import ActivityCompletionResult


def expense_form(result: ActivityCompletionResult, key_prefix: str = "exp"):
    st.subheader(f"Add Expense - {result.activity_name}")

    if result.total_hours > 0:
        st.write(f"Total time: **{result.total_hours}** hours")

    default_expense = (
        result.selling_price
        or result.purchase_price
        or result.total_selling_price
        or result.total_purchase_price
    )
    expense_amount = st.number_input(
        "Expense (per hour or unit)",
        value=float(default_expense),
        min_value=0.0,
        key=f"{key_prefix}_expense",
    )
    vendor = st.text_input("Vendor / Employee Name", key=f"{key_prefix}_vendor")
    notes = st.text_area("Notes", key=f"{key_prefix}_notes")
    add_expense = st.checkbox("Save expense", value=True, key=f"{key_prefix}_save")

    return {
        "purchase_price": expense_amount,
        "selling_price": expense_amount,
        "vendor_or_worker_name": vendor,
        "notes": notes,
        "add_expense": add_expense,
    }
