from datetime import date

import pandas as pd
import streamlit as st

from vaybooks.bms.ui.components import report_filters as rf
from vaybooks.bms.ui.pagination import REPORT_PAGE_SIZE, paginate_list, render_page_controls

AGGREGATED_PERIOD_LABEL = "Aggregated Totals for period"

REPORT_TYPES = [
    "Item Profitability (MPH)",
    "Activity Pending",
    "Time Tracking",
    "Expense",
    "Margin Per Hour (MPH)",
    "Customer Order History",
    "Overdue Orders",
    "Completed Orders",
]


@st.cache_data(ttl=60, show_spinner=False)
def _period_summary(_report_service, start: date, end: date):
    return _report_service.get_period_summary(start, end)


def _render_aggregated_period_summary(report_service, start: date, end: date) -> None:
    st.subheader(AGGREGATED_PERIOD_LABEL)
    st.caption(f"{start:%d %b %Y} → {end:%d %b %Y}")
    summary = _period_summary(report_service, start, end)
    cols = st.columns(3)
    cols[0].metric("Orders", summary.get("order_count", 0))
    cols[1].metric("Invoiced", f"₹{summary.get('invoiced', 0):,.0f}")
    cols[2].metric("Expenses", f"₹{summary.get('expenses', 0):,.0f}")
    st.divider()


def _render_report_table(data: list, report_key: str, filter_token: str):
    if not data:
        st.info("No rows match the selected filters.")
        return
    page_rows, page, total_pages = paginate_list(
        data,
        page_key=f"report_page_{report_key}",
        page_size=REPORT_PAGE_SIZE,
        filter_key=f"report_filter_{report_key}",
        filter_value=filter_token,
    )
    st.dataframe(pd.DataFrame(page_rows), use_container_width=True)
    render_page_controls(
        page, total_pages, len(data),
        page_key=f"report_page_{report_key}",
        prev_key=f"report_prev_{report_key}",
        next_key=f"report_next_{report_key}",
        label="rows",
    )


def _render_customer_history(report_service, customer_service):
    query = st.text_input(
        "Search customer by name or phone", key="report_cust_search"
    )
    if not query:
        st.caption("Search and select a customer to view order history.")
        return
    customers = customer_service.search_customers(query)
    if not customers:
        st.info("No customers found")
        return
    options = {f"{c.customer_name} — {c.phone_number}": c.id for c in customers}
    choice = st.selectbox("Select customer", list(options.keys()), key="report_cust_pick")
    customer_id = options[choice]
    filters = rf.render_customer_history_filters(customer_id)
    if not filters:
        return
    token = rf.filter_token(
        "customer_order_history",
        customer_id,
        filters.date_range.token_part(),
        ",".join(filters.statuses),
    )
    data = report_service.customer_order_history(filters)
    _render_report_table(data, f"customer_history_{customer_id}", token)


def render(services: dict):
    st.title("Reports")
    report_service = services["reports"]
    customer_service = services["customers"]
    activity_service = services["activities"]

    report_type = st.selectbox("Select Report", REPORT_TYPES, key="report_type_select")
    report_key = report_type.replace(" ", "_").lower()

    st.divider()

    if report_type == "Customer Order History":
        _render_customer_history(report_service, customer_service)
        return

    if report_type == "Item Profitability (MPH)":
        filters = rf.render_item_profitability_filters()
        _render_aggregated_period_summary(
            report_service, filters.date_range.start, filters.date_range.end
        )
        token = rf.filter_token(
            report_key,
            filters.date_range.token_part(),
            filters.customer_query,
            filters.bill_query,
            str(filters.min_mph),
            str(filters.min_margin),
        )
        data = report_service.item_profitability_report(filters)

    elif report_type == "Margin Per Hour (MPH)":
        filters = rf.render_order_mph_filters()
        _render_aggregated_period_summary(
            report_service, filters.date_range.start, filters.date_range.end
        )
        token = rf.filter_token(
            report_key,
            filters.date_range.token_part(),
            filters.customer_query,
            str(filters.min_mph),
        )
        data = report_service.mph_report(filters)

    elif report_type == "Activity Pending":
        activity_names = [
            a.activity_name for a in activity_service.list_activities(active_only=False)
        ]
        filters = rf.render_activity_pending_filters(activity_names)
        token = rf.filter_token(
            report_key,
            filters.etd_start.isoformat(),
            filters.etd_end.isoformat(),
            str(filters.overdue_only),
            ",".join(filters.statuses),
            ",".join(filters.activity_names),
            filters.customer_query,
        )
        data = report_service.activity_pending_report(filters)

    elif report_type == "Time Tracking":
        filters = rf.render_time_tracking_filters()
        token = rf.filter_token(
            report_key,
            filters.date_range.token_part(),
            filters.worker,
            filters.activity_name,
            filters.search,
        )
        data = report_service.time_tracking_report(filters)

    elif report_type == "Expense":
        filters = rf.render_expense_filters()
        token = rf.filter_token(
            report_key,
            filters.date_range.token_part(),
            filters.expense_source,
            filters.search,
            str(filters.min_amount),
        )
        data = report_service.expense_report(filters)

    elif report_type == "Overdue Orders":
        filters = rf.render_overdue_filters()
        token = rf.filter_token(
            report_key,
            filters.as_of_date.isoformat(),
            str(filters.min_days_overdue),
            ",".join(filters.statuses),
            filters.customer_query,
        )
        data = report_service.overdue_order_report(filters)

    elif report_type == "Completed Orders":
        filters = rf.render_completed_filters()
        token = rf.filter_token(
            report_key,
            filters.date_range.token_part(),
            ",".join(filters.statuses),
            filters.customer_query,
        )
        data = report_service.completed_order_report(filters)

    else:
        st.error("Unknown report type")
        return

    _render_report_table(data, report_key, token)
