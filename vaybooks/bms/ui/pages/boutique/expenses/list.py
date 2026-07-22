from datetime import date

import streamlit as st

from vaybooks.bms.domain.shared.enums import ExpenseSource
from vaybooks.bms.ui.components.boutique.order_selector import order_selector


def render(services: dict):
    st.title("Expenses")
    expense_service = services["expenses"]

    tab1, tab2 = st.tabs(["View by Order", "Add Expense"])

    with tab1:
        order_id = order_selector(services, "exp_ord")
        if order_id:
            expenses = expense_service.get_expenses_by_order(order_id)
            totals = expense_service.get_order_totals(order_id)
            for exp in expenses:
                st.write(
                    f"**{exp.expense_name}** ({exp.expense_source.value})\n"
                    f"Purchase: ₹{exp.total_purchase_price:,.0f} | "
                    f"Selling: ₹{exp.total_selling_price:,.0f} | "
                    f"Date: {exp.expense_date}"
                )
            st.metric("Total Purchase", f"₹{totals['total_purchase']:,.0f}")
            st.metric("Total Selling", f"₹{totals['total_selling']:,.0f}")

    with tab2:
        order_id = order_selector(services, "exp_add_ord")
        if order_id:
            name = st.text_input("Expense Name")
            source = st.selectbox("Source", [e.value for e in ExpenseSource])
            purchase = st.number_input("Purchase Price", min_value=0.01)
            selling = st.number_input("Selling Price", min_value=0.01)
            quantity = st.number_input("Quantity", min_value=0.01, value=1.0)
            vendor = st.text_input("Vendor / Employee")
            notes = st.text_area("Notes")
            if st.button("Add Expense"):
                if purchase <= 0 or selling <= 0:
                    st.error("Price must be a positive value")
                else:
                    try:
                        expense_service.add_expense(
                            order_id=order_id,
                            expense_date=date.today(),
                            expense_name=name,
                            expense_source=source,
                            purchase_price=purchase,
                            selling_price=selling,
                            quantity=quantity,
                            vendor_or_worker_name=vendor,
                            notes=notes,
                        )
                        st.success("Expense added")
                    except Exception as e:
                        st.error(str(e))
