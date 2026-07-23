"""Sales Overview — KPIs, charts, and action queues."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from vaybooks.bms.application.report_filters import OutstandingFilter
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.common.filter_sort_bar import (
    _mtd_range,
    _normalize_date_range,
    render_filter_sort_bar,
)
from vaybooks.bms.ui.sales_list_schemas import SALES_OVERVIEW
from vaybooks.bms.ui.styles import metric_grid

QUEUE_LIMIT = 8


def _fmt_currency(value: float) -> str:
    return f"₹{float(value or 0):,.0f}"


def _resolved_range(committed: dict) -> tuple[date, date]:
    return _normalize_date_range(committed.get("date_range")) or _mtd_range()


def _customer_receivables_total(services: dict) -> str:
    reports = services.get("reports_business")
    if reports is None:
        return "—"
    try:
        rows = reports.customer_outstanding_report(OutstandingFilter())
    except Exception:
        return "—"
    total = sum(float(r.get("balance_due") or 0) for r in rows)
    return _fmt_currency(total)


def _chart_or_caption(title: str, df: pd.DataFrame, chart_fn, empty_msg: str) -> None:
    st.markdown(f"**{title}**")
    if df.empty:
        st.caption(empty_msg)
        return
    chart_fn(df)


def _render_charts(reports, start: date, end: date) -> None:
    span_days = (end - start).days + 1
    grain = "day" if span_days <= 45 else "week"

    sales_rows = reports.sales_time_series(start, end, grain=grain)
    status_rows = reports.so_status_breakdown()
    customer_rows = reports.sales_by_customer(start, end)[:10]
    dn_customer_rows = reports.dn_pending_by_customer(limit=10)
    vs_rows = reports.sales_vs_returns_series(start, end)

    row1 = st.columns(2)
    with row1[0]:
        sales_df = (
            pd.DataFrame(sales_rows).set_index("period")[["amount"]]
            if sales_rows
            else pd.DataFrame()
        )
        if not sales_df.empty:
            sales_df = sales_df.rename(columns={"amount": "Sales"})
        _chart_or_caption(
            "Sales over time",
            sales_df,
            st.line_chart,
            "No sales invoices in this date range.",
        )
    with row1[1]:
        status_df = (
            pd.DataFrame(status_rows).set_index("status")[["count"]]
            if status_rows
            else pd.DataFrame()
        )
        if not status_df.empty:
            status_df = status_df.rename(columns={"count": "SOs"})
        _chart_or_caption(
            "SO pipeline by status",
            status_df,
            st.bar_chart,
            "No open sales orders.",
        )
        st.caption("As of now — not filtered by date range.")

    row2 = st.columns(2)
    with row2[0]:
        customer_df = (
            pd.DataFrame(customer_rows).set_index("customer_name")[["total"]]
            if customer_rows
            else pd.DataFrame()
        )
        if not customer_df.empty:
            customer_df = customer_df.rename(columns={"total": "Sales"})
        _chart_or_caption(
            "Top customers by sales",
            customer_df,
            st.bar_chart,
            "No customer sales in this date range.",
        )
    with row2[1]:
        dn_df = (
            pd.DataFrame(dn_customer_rows).set_index("customer_name")[["qty_pending"]]
            if dn_customer_rows
            else pd.DataFrame()
        )
        if not dn_df.empty:
            dn_df = dn_df.rename(columns={"qty_pending": "Pending qty"})
        _chart_or_caption(
            "Pending delivery by customer",
            dn_df,
            st.bar_chart,
            "No pending deliveries.",
        )
        st.caption("As of now — not filtered by date range.")

    vs_df = (
        pd.DataFrame(vs_rows).set_index("period")[["sales", "returns"]]
        if vs_rows
        else pd.DataFrame()
    )
    if not vs_df.empty:
        vs_df = vs_df.rename(columns={"sales": "Sales", "returns": "Returns"})
    _chart_or_caption(
        "Sales vs returns by month",
        vs_df,
        st.bar_chart,
        "No sales or returns in this date range.",
    )


def _render_queues(reports) -> None:
    pipeline = reports.sales_orders_pipeline()
    overdue = [r for r in pipeline if r.get("overdue")][:QUEUE_LIMIT]
    pending = sorted(
        reports.delivery_pending(),
        key=lambda r: float(r.get("qty_pending") or 0),
        reverse=True,
    )[:QUEUE_LIMIT]

    with st.expander(f"Overdue SOs ({len(overdue)})", expanded=bool(overdue)):
        st.caption("As of now — expected date past, not yet delivered.")
        if not overdue:
            st.caption("All clear — no overdue sales orders.")
        else:
            for row in overdue:
                cols = st.columns([3, 3, 2, 1])
                cols[0].markdown(f"**{row.get('so_number')}**")
                cols[1].write(row.get("customer_name") or "—")
                expected = row.get("expected_date")
                cols[2].write(
                    expected.strftime("%d %b %Y") if expected else "—"
                )
                if cols[3].button(
                    "Open",
                    key=f"sales_overview_overdue_{row.get('id')}",
                    use_container_width=True,
                ):
                    navigation.go_to_detail("sales_order_detail", row.get("id"))

    with st.expander(
        f"Pending delivery ({len(pending)})", expanded=bool(pending)
    ):
        st.caption("As of now — open SO lines awaiting delivery.")
        if not pending:
            st.caption("All clear — no pending delivery lines.")
        else:
            for idx, row in enumerate(pending):
                cols = st.columns([2, 3, 2, 1, 1])
                cols[0].markdown(f"**{row.get('so_number')}**")
                cols[1].write(row.get("customer_name") or "—")
                cols[2].write(row.get("product_name") or "—")
                cols[3].write(f"{float(row.get('qty_pending') or 0):g}")
                if cols[4].button(
                    "Open",
                    key=f"sales_overview_pending_{idx}_{row.get('id')}",
                    use_container_width=True,
                ):
                    navigation.go_to_detail("sales_order_detail", row.get("id"))


def _render_quick_actions() -> None:
    st.markdown("**Quick actions**")
    cols = st.columns(5)
    if cols[0].button("Sales Orders", use_container_width=True):
        navigation.go_to_list("sales_orders_list")
    if cols[1].button("Delivery Notes", use_container_width=True):
        navigation.go_to_list("delivery_notes_list")
    if cols[2].button("Sales Invoices", use_container_width=True):
        navigation.go_to_list("sales_invoices_list")
    if cols[3].button("Returns", use_container_width=True):
        navigation.go_to_list("sales_returns_list")
    if cols[4].button("Reports", use_container_width=True):
        navigation.go_to_list("sales_reports")


def render(services: dict) -> None:
    st.header("Sales Overview")

    reports = services.get("reports_sales_module")
    if reports is None:
        st.error("Sales reports service is unavailable.")
        return

    bar = render_filter_sort_bar(
        SALES_OVERVIEW,
        services=services,
        title="Sales Overview",
    )
    start, end = _resolved_range(bar["filters"])
    st.caption(f"Period: **{start:%d %b %Y}** → **{end:%d %b %Y}**")

    _render_quick_actions()

    sales_svc = services.get("sales")
    try:
        summary = reports.dashboard_summary(start, end)
        overdue_count = reports.overdue_so_count()
        orders = sales_svc.list_sales_orders() if sales_svc else []
        invoices = sales_svc.list_sales_invoices() if sales_svc else []
    except Exception as exc:
        st.error(f"Could not load sales overview: {exc}")
        return

    if not orders and not invoices:
        st.info("No sales activity yet. Create a sales order to get started.")
        return

    metric_grid(
        [
            ("Open SOs", summary.get("open_so_count", 0)),
            ("Overdue SOs", overdue_count),
            ("Pending DN qty", f"{summary.get('pending_dn_qty', 0):g}"),
            ("Sales (range)", _fmt_currency(summary.get("sales_this_month", 0))),
            ("Returns (range)", _fmt_currency(summary.get("returns_this_month", 0))),
            ("Customer receivables", _customer_receivables_total(services)),
        ],
        suffix="sales_overview",
    )
    st.caption(
        "Open SOs, overdue, pending delivery, and receivables are as of now. "
        "Sales and returns use the Filters period."
    )

    _render_charts(reports, start, end)
    _render_queues(reports)
