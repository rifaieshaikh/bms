"""Streamlit filter widgets for the Reports page."""

from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from vaybooks.bms.application.report_filters import (
    ActivityPendingFilter,
    CompletedFilter,
    CustomerHistoryFilter,
    DateRange,
    ExpenseFilter,
    ItemProfitabilityFilter,
    OrderMphFilter,
    OverdueFilter,
    TimeTrackingFilter,
)
from vaybooks.bms.domain.shared.enums import ExpenseSource, OrderStatus
from vaybooks.bms.infrastructure.db.bson_utils import as_date


def _mtd_range() -> DateRange:
    today = date.today()
    return DateRange(today.replace(day=1), today)


def render_date_range(key: str, default: DateRange | None = None) -> DateRange:
    """Date range picker; defaults to month-to-date."""
    today = date.today()
    default = default or _mtd_range()
    widget_key = f"report_period_{key}"
    if widget_key not in st.session_state:
        st.session_state[widget_key] = (default.start, default.end)
    picked = st.date_input(
        "Period",
        value=st.session_state[widget_key],
        max_value=today,
        format="DD/MM/YYYY",
        key=widget_key,
    )
    if isinstance(picked, (list, tuple)) and len(picked) == 2:
        start, end = picked
        if start > end:
            start, end = end, start
        return DateRange(start, end)
    return default


def render_quick_period(key: str) -> None:
    """MTD / Last 30 days shortcuts; updates the paired date_input widget."""
    widget_key = f"report_period_{key}"
    cols = st.columns(2)
    today = date.today()
    if cols[0].button("MTD", key=f"report_mtd_{key}", use_container_width=True):
        st.session_state[widget_key] = (today.replace(day=1), today)
        st.rerun()
    if cols[1].button("Last 30 days", key=f"report_30d_{key}", use_container_width=True):
        st.session_state[widget_key] = (today - timedelta(days=29), today)
        st.rerun()


def _text_search(label: str, key: str) -> str:
    return st.text_input(label, key=f"report_{key}").strip().lower()


def _min_number(label: str, key: str) -> float | None:
    val = st.number_input(label, min_value=0.0, value=0.0, key=f"report_{key}")
    return val if val > 0 else None


def render_item_profitability_filters() -> ItemProfitabilityFilter:
    render_quick_period("item_profit")
    date_range = render_date_range("item_profit")
    st.caption(
        f"Delivered / snapshotted {date_range.start:%d %b %Y} → {date_range.end:%d %b %Y}. "
        "Bill-level MPH per item; order rollup uses aggregated totals."
    )
    c1, c2 = st.columns(2)
    with c1:
        customer = _text_search("Customer", "item_cust")
    with c2:
        bill = _text_search("Bill / order", "item_bill")
    c3, c4 = st.columns(2)
    with c3:
        min_mph = _min_number("Min MPH (₹/h)", "item_min_mph")
    with c4:
        min_margin = _min_number("Min margin (₹)", "item_min_margin")
    return ItemProfitabilityFilter(
        date_range=date_range,
        customer_query=customer,
        bill_query=bill,
        min_mph=min_mph,
        min_margin=min_margin,
    )


def render_order_mph_filters() -> OrderMphFilter:
    render_quick_period("order_mph")
    date_range = render_date_range("order_mph")
    st.caption(
        f"Items delivered in period {date_range.start:%d %b %Y} → {date_range.end:%d %b %Y}. "
        "Order MPH is aggregated across bills (not a simple average of bill-level MPH)."
    )
    customer = _text_search("Customer", "order_mph_cust")
    min_mph = _min_number("Min order MPH (₹/h)", "order_min_mph")
    return OrderMphFilter(date_range=date_range, customer_query=customer, min_mph=min_mph)


def render_activity_pending_filters(activity_names: list[str]) -> ActivityPendingFilter:
    today = date.today()
    picked = st.date_input(
        "ETD range",
        value=(today, today + timedelta(days=30)),
        format="DD/MM/YYYY",
        key="report_etd_range",
    )
    if isinstance(picked, (list, tuple)) and len(picked) == 2:
        etd_start = as_date(picked[0]) or today
        etd_end = as_date(picked[1]) or today + timedelta(days=30)
        if etd_start > etd_end:
            etd_start, etd_end = etd_end, etd_start
    else:
        etd_start, etd_end = today, today + timedelta(days=30)

    overdue_only = st.checkbox("Overdue only (ETD before today)", key="report_overdue_only")
    statuses = st.multiselect(
        "Activity status",
        ["Pending", "In Progress"],
        default=["Pending", "In Progress"],
        key="report_act_status",
    )
    selected_activities = st.multiselect(
        "Activity",
        activity_names,
        key="report_act_names",
    )
    customer = _text_search("Customer / order", "act_pending_search")
    return ActivityPendingFilter(
        etd_start=etd_start,
        etd_end=etd_end,
        statuses=statuses or ["Pending", "In Progress"],
        activity_names=selected_activities,
        customer_query=customer,
        overdue_only=overdue_only,
    )


def render_time_tracking_filters() -> TimeTrackingFilter:
    render_quick_period("time")
    date_range = render_date_range("time")
    st.caption(f"Work date {date_range.start:%d %b %Y} → {date_range.end:%d %b %Y}")
    c1, c2 = st.columns(2)
    with c1:
        worker = _text_search("Worker", "time_worker")
    with c2:
        activity = st.text_input("Activity", key="report_time_activity").strip()
    search = _text_search("Order / bill", "time_search")
    return TimeTrackingFilter(
        date_range=date_range,
        worker=worker,
        activity_name=activity,
        search=search,
    )


def render_expense_filters() -> ExpenseFilter:
    render_quick_period("expense")
    date_range = render_date_range("expense")
    st.caption(f"Expense date {date_range.start:%d %b %Y} → {date_range.end:%d %b %Y}")
    sources = [""] + [s.value for s in ExpenseSource]
    source = st.selectbox(
        "Expense source",
        sources,
        format_func=lambda s: "All" if not s else s,
        key="report_exp_source",
    )
    search = _text_search("Order / bill", "exp_search")
    min_amount = _min_number("Min amount (₹)", "exp_min")
    return ExpenseFilter(
        date_range=date_range,
        expense_source=source,
        search=search,
        min_amount=min_amount,
    )


def render_customer_history_filters(
    customer_id: str | None,
) -> CustomerHistoryFilter | None:
    if not customer_id:
        return None
    render_quick_period("cust_hist")
    date_range = render_date_range("cust_hist")
    statuses = st.multiselect(
        "Order status",
        [s.value for s in OrderStatus],
        key="report_cust_status",
    )
    return CustomerHistoryFilter(
        customer_id=customer_id,
        date_range=date_range,
        statuses=statuses,
    )


def render_overdue_filters() -> OverdueFilter:
    today = date.today()
    as_of = st.date_input("As-of date", value=today, key="report_as_of", format="DD/MM/YYYY")
    min_days = int(
        st.number_input("Min days overdue", min_value=0, value=0, key="report_min_overdue")
    )
    statuses = st.multiselect(
        "Order status",
        [
            OrderStatus.IN_PROGRESS.value,
            OrderStatus.READY_FOR_DELIVERY.value,
            OrderStatus.INVOICE_GENERATED.value,
        ],
        key="report_overdue_status",
    )
    customer = _text_search("Customer / phone", "overdue_search")
    return OverdueFilter(
        as_of_date=as_of,
        min_days_overdue=min_days,
        statuses=statuses,
        customer_query=customer,
    )


def render_completed_filters() -> CompletedFilter:
    render_quick_period("completed")
    date_range = render_date_range("completed")
    st.caption(f"Delivery date {date_range.start:%d %b %Y} → {date_range.end:%d %b %Y}")
    statuses = st.multiselect(
        "Status",
        [OrderStatus.COMPLETED.value, OrderStatus.DELIVERED.value],
        default=[OrderStatus.COMPLETED.value, OrderStatus.DELIVERED.value],
        key="report_completed_status",
    )
    customer = _text_search("Customer", "completed_cust")
    return CompletedFilter(
        date_range=date_range,
        statuses=statuses or [OrderStatus.COMPLETED.value, OrderStatus.DELIVERED.value],
        customer_query=customer,
    )


def filter_token(report_key: str, *parts: str) -> str:
    """Stable string for pagination reset when filters change."""
    return "|".join([report_key, *parts])
