import pandas as pd
import streamlit as st


def render(services: dict):
    st.title("Reports")
    report_service = services["reports"]
    customer_service = services["customers"]

    report_type = st.selectbox(
        "Select Report",
        [
            "Order Profitability",
            "Activity Pending",
            "Time Tracking",
            "Expense",
            "Margin Per Hour (MPH)",
            "Customer Order History",
            "Overdue Orders",
            "Completed Orders",
        ],
    )

    if report_type == "Customer Order History":
        query = st.text_input("Search customer by name or phone")
        if query:
            customers = customer_service.search_customers(query)
            if customers:
                options = {f"{c.customer_name} — {c.phone_number}": c.id for c in customers}
                choice = st.selectbox("Select customer", list(options.keys()))
                data = report_service.customer_order_history(options[choice])
                st.dataframe(pd.DataFrame(data), use_container_width=True)
            else:
                st.info("No customers found")
        return

    report_map = {
        "Order Profitability": report_service.order_profitability_report,
        "Activity Pending": report_service.activity_pending_report,
        "Time Tracking": report_service.time_tracking_report,
        "Expense": report_service.expense_report,
        "Margin Per Hour (MPH)": report_service.mph_report,
        "Overdue Orders": report_service.overdue_order_report,
        "Completed Orders": report_service.completed_order_report,
    }

    data = report_map[report_type]()
    if data:
        st.dataframe(pd.DataFrame(data), use_container_width=True)
    else:
        st.info("No data for this report")
