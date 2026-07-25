"""Boutique Overview - KPIs, pipeline chart, and action queues."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.boutique_list_schemas import BOUTIQUE_OVERVIEW
from vaybooks.bms.ui.components.common.filter_sort_bar import (
    _mtd_range,
    _normalize_date_range,
    render_filter_sort_bar,
)
from vaybooks.bms.ui.components.common.overview_action_cards import (
    overview_action_cards,
)
from vaybooks.bms.ui.styles import metric_grid

QUEUE_LIMIT = 8


def _fmt_currency(value: float) -> str:
    return f"\u20b9{float(value or 0):,.0f}"


def _resolved_range(committed: dict) -> tuple[date, date]:
    return _normalize_date_range(committed.get("date_range")) or _mtd_range()


def _tone_if(positive: bool, tone: str) -> str:
    return tone if positive else "neutral"


def _render_quick_actions() -> None:
    st.markdown("**Quick actions**")
    cols = st.columns(5)
    if cols[0].button("Orders", width="stretch"):
        navigation.go_to_list("orders_list")
    if cols[1].button("Measurements", width="stretch"):
        navigation.go_to_list("measurements_list")
    if cols[2].button("Tasks", width="stretch"):
        navigation.go_to_list("time_list")
    if cols[3].button("Calendar", width="stretch"):
        navigation.go_to_list("calendar_list")
    if cols[4].button("Reports", width="stretch"):
        navigation.go_to_list("boutique_reports")


def _chart_or_caption(title: str, df: pd.DataFrame, chart_fn, empty_msg: str) -> None:
    st.markdown(f"**{title}**")
    if df.empty:
        st.caption(empty_msg)
        return
    chart_fn(df)


def _render_charts(reports, start: date, end: date) -> None:
    st.markdown("#### Charts")
    span_days = (end - start).days + 1
    grain = "day" if span_days <= 45 else "week"

    revenue_rows = reports.invoiced_revenue_series(start, end, grain=grain)
    hours_rows = reports.hours_logged_series(start, end, grain=grain)
    status_rows = reports.status_breakdown()
    customer_rows = reports.top_customers_by_revenue(start, end, limit=10)
    worker_rows = reports.hours_by_worker(start, end, limit=10)
    delivery_rows = reports.delivery_on_time_breakdown(start, end)

    row1 = st.columns(2)
    with row1[0]:
        revenue_df = (
            pd.DataFrame(revenue_rows).set_index("period")[["amount"]]
            if revenue_rows
            else pd.DataFrame()
        )
        if not revenue_df.empty:
            revenue_df = revenue_df.rename(columns={"amount": "Revenue"})
        _chart_or_caption(
            "Invoiced revenue over time",
            revenue_df,
            st.line_chart,
            "No invoices in this date range.",
        )
    with row1[1]:
        hours_df = (
            pd.DataFrame(hours_rows).set_index("period")[["hours"]]
            if hours_rows
            else pd.DataFrame()
        )
        if not hours_df.empty:
            hours_df = hours_df.rename(columns={"hours": "Hours"})
        _chart_or_caption(
            "Hours logged over time",
            hours_df,
            st.line_chart,
            "No time entries in this date range.",
        )

    row2 = st.columns(2)
    with row2[0]:
        status_df = (
            pd.DataFrame(status_rows).set_index("status")[["count"]]
            if status_rows
            else pd.DataFrame()
        )
        if not status_df.empty:
            status_df = status_df.rename(columns={"count": "Orders"})
        _chart_or_caption(
            "Order pipeline by status",
            status_df,
            st.bar_chart,
            "No active orders.",
        )
        st.caption("As of now — excludes cancelled orders.")
    with row2[1]:
        delivery_df = (
            pd.DataFrame(delivery_rows).set_index("outcome")[["count"]]
            if delivery_rows
            else pd.DataFrame()
        )
        if not delivery_df.empty:
            delivery_df = delivery_df.rename(columns={"count": "Deliveries"})
        _chart_or_caption(
            "Delivery on-time vs late",
            delivery_df,
            st.bar_chart,
            "No completed deliveries in this date range.",
        )

    row3 = st.columns(2)
    with row3[0]:
        customer_df = (
            pd.DataFrame(customer_rows).set_index("customer_name")[["total_revenue"]]
            if customer_rows
            else pd.DataFrame()
        )
        if not customer_df.empty:
            customer_df = customer_df.rename(columns={"total_revenue": "Revenue"})
        _chart_or_caption(
            "Top customers by invoiced revenue",
            customer_df,
            st.bar_chart,
            "No customer revenue in this date range.",
        )
    with row3[1]:
        worker_df = (
            pd.DataFrame(worker_rows).set_index("worker_name")[["total_hours"]]
            if worker_rows
            else pd.DataFrame()
        )
        if not worker_df.empty:
            worker_df = worker_df.rename(columns={"total_hours": "Hours"})
        _chart_or_caption(
            "Hours by worker",
            worker_df,
            st.bar_chart,
            "No worker hours in this date range.",
        )


def _render_queues(reports) -> None:
    overdue = reports.overdue_queue(limit=QUEUE_LIMIT)
    pending = reports.bills_pending_invoice_queue(limit=QUEUE_LIMIT)

    overview_action_cards(
        "Overdue orders",
        overdue,
        "boutique_overview_overdue",
        accent="red",
        title_fn=lambda r: r.get("order_number") or "\u2014",
        subtitle_fn=lambda r: r.get("customer_name") or "\u2014",
        meta_fn=lambda r: f"{r.get('days_overdue')} days overdue",
        on_open=lambda r: navigation.go_to_detail("order_detail", r.get("id")),
        empty_msg="All clear - no overdue orders.",
        max_cards=QUEUE_LIMIT,
    )

    overview_action_cards(
        "Bills pending invoice",
        pending,
        "boutique_overview_pending",
        accent="orange",
        title_fn=lambda r: r.get("order_number") or "\u2014",
        subtitle_fn=lambda r: r.get("customer_name") or "\u2014",
        meta_fn=lambda r: f"{r.get('pending_bills')} bills pending",
        on_open=lambda r: navigation.go_to_detail("order_detail", r.get("id")),
        empty_msg="All clear - no bills pending invoice.",
        max_cards=QUEUE_LIMIT,
    )


def render(services: dict) -> None:
    st.header("Boutique Overview")

    reports = services.get("reports_boutique_module")
    if reports is None:
        st.error("Boutique reports service is unavailable.")
        return

    bar = render_filter_sort_bar(
        BOUTIQUE_OVERVIEW,
        services=services,
        title="Boutique Overview",
    )
    start, end = _resolved_range(bar["filters"])
    st.caption(f"Period: **{start:%d %b %Y}** \u2192 **{end:%d %b %Y}**")

    _render_quick_actions()

    try:
        summary = reports.dashboard_summary(start, end)
    except Exception as exc:
        st.error(f"Could not load boutique overview: {exc}")
        return

    if not summary.get("open_orders") and not summary.get("invoiced_revenue"):
        st.info("No boutique activity yet. Create an order to get started.")

    overdue = int(summary.get("overdue_orders", 0) or 0)
    pending_inv = int(summary.get("bills_pending_invoice", 0) or 0)
    pending_del = int(summary.get("bills_pending_delivery", 0) or 0)

    st.markdown("#### Attention")
    metric_grid(
        [
            ("Open orders", summary.get("open_orders", 0)),
            (
                "Overdue orders",
                overdue,
                _tone_if(overdue > 0, "danger"),
            ),
            (
                "Bills pending invoice",
                pending_inv,
                _tone_if(pending_inv > 0, "warn"),
            ),
            (
                "Bills pending delivery",
                pending_del,
                _tone_if(pending_del > 0, "warn"),
            ),
        ],
        suffix="boutique_overview_attention",
    )

    st.markdown("#### Period")
    metric_grid(
        [
            ("Invoiced (range)", _fmt_currency(summary.get("invoiced_revenue", 0))),
            ("Hours logged (range)", f"{summary.get('hours_logged', 0):g}"),
        ],
        suffix="boutique_overview_period",
    )
    st.caption(
        "Open, overdue, and pending counts are as of now. "
        "Invoiced revenue and logged hours use the Filters period."
    )

    _render_charts(reports, start, end)
    _render_queues(reports)
