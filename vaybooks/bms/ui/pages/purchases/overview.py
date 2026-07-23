"""Purchases Overview — KPIs, charts, and action queues."""

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
from vaybooks.bms.ui.purchase_list_schemas import PURCHASES_OVERVIEW
from vaybooks.bms.ui.styles import metric_grid

QUEUE_LIMIT = 8


def _fmt_currency(value: float) -> str:
    return f"₹{float(value or 0):,.0f}"


def _resolved_range(committed: dict) -> tuple[date, date]:
    return _normalize_date_range(committed.get("date_range")) or _mtd_range()


def _vendor_payables_total(services: dict) -> str:
    reports = services.get("reports_business")
    if reports is None:
        return "—"
    try:
        rows = reports.vendor_payables_report(OutstandingFilter())
    except Exception:
        return "—"
    total = sum(float(r.get("payable") or 0) for r in rows)
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

    spend_rows = reports.spend_time_series(start, end, grain=grain)
    status_rows = reports.po_status_breakdown()
    vendor_rows = reports.purchases_by_vendor(start, end)[:10]
    grn_vendor_rows = reports.grn_pending_by_vendor(limit=10)
    vs_rows = reports.purchases_vs_returns_series(start, end)

    row1 = st.columns(2)
    with row1[0]:
        spend_df = (
            pd.DataFrame(spend_rows).set_index("period")[["amount"]]
            if spend_rows
            else pd.DataFrame()
        )
        if not spend_df.empty:
            spend_df = spend_df.rename(columns={"amount": "Spend"})
        _chart_or_caption(
            "Spend over time",
            spend_df,
            st.line_chart,
            "No purchase bills in this date range.",
        )
    with row1[1]:
        status_df = (
            pd.DataFrame(status_rows).set_index("status")[["count"]]
            if status_rows
            else pd.DataFrame()
        )
        if not status_df.empty:
            status_df = status_df.rename(columns={"count": "POs"})
        _chart_or_caption(
            "PO pipeline by status",
            status_df,
            st.bar_chart,
            "No open purchase orders.",
        )
        st.caption("As of now — not filtered by date range.")

    row2 = st.columns(2)
    with row2[0]:
        vendor_df = (
            pd.DataFrame(vendor_rows).set_index("vendor_name")[["total"]]
            if vendor_rows
            else pd.DataFrame()
        )
        if not vendor_df.empty:
            vendor_df = vendor_df.rename(columns={"total": "Spend"})
        _chart_or_caption(
            "Top vendors by spend",
            vendor_df,
            st.bar_chart,
            "No vendor spend in this date range.",
        )
    with row2[1]:
        grn_df = (
            pd.DataFrame(grn_vendor_rows).set_index("vendor_name")[["qty_pending"]]
            if grn_vendor_rows
            else pd.DataFrame()
        )
        if not grn_df.empty:
            grn_df = grn_df.rename(columns={"qty_pending": "Pending qty"})
        _chart_or_caption(
            "Pending GRN by vendor",
            grn_df,
            st.bar_chart,
            "No pending goods receipts.",
        )
        st.caption("As of now — not filtered by date range.")

    vs_df = (
        pd.DataFrame(vs_rows).set_index("period")[["purchases", "returns"]]
        if vs_rows
        else pd.DataFrame()
    )
    if not vs_df.empty:
        vs_df = vs_df.rename(columns={"purchases": "Purchases", "returns": "Returns"})
    _chart_or_caption(
        "Purchases vs returns by month",
        vs_df,
        st.bar_chart,
        "No purchases or returns in this date range.",
    )


def _render_queues(reports) -> None:
    pipeline = reports.purchase_orders_pipeline()
    overdue = [r for r in pipeline if r.get("overdue")][:QUEUE_LIMIT]
    pending = sorted(
        reports.grn_pending(),
        key=lambda r: float(r.get("qty_pending") or 0),
        reverse=True,
    )[:QUEUE_LIMIT]

    with st.expander(f"Overdue POs ({len(overdue)})", expanded=bool(overdue)):
        st.caption("As of now — expected date past, not yet received.")
        if not overdue:
            st.caption("All clear — no overdue purchase orders.")
        else:
            for row in overdue:
                cols = st.columns([3, 3, 2, 1])
                cols[0].markdown(f"**{row.get('po_number')}**")
                cols[1].write(row.get("vendor_name") or "—")
                expected = row.get("expected_date")
                cols[2].write(
                    expected.strftime("%d %b %Y") if expected else "—"
                )
                if cols[3].button(
                    "Open",
                    key=f"purchases_overview_overdue_{row.get('id')}",
                    use_container_width=True,
                ):
                    navigation.go_to_detail("purchase_order_detail", row.get("id"))

    with st.expander(
        f"Pending receive ({len(pending)})", expanded=bool(pending)
    ):
        st.caption("As of now — open PO lines awaiting goods receipt.")
        if not pending:
            st.caption("All clear — no pending GRN lines.")
        else:
            for idx, row in enumerate(pending):
                cols = st.columns([2, 3, 2, 1, 1])
                cols[0].markdown(f"**{row.get('po_number')}**")
                cols[1].write(row.get("vendor_name") or "—")
                cols[2].write(row.get("product_name") or "—")
                cols[3].write(f"{float(row.get('qty_pending') or 0):g}")
                if cols[4].button(
                    "Open",
                    key=f"purchases_overview_pending_{idx}_{row.get('id')}",
                    use_container_width=True,
                ):
                    navigation.go_to_detail("purchase_order_detail", row.get("id"))


def _render_quick_actions() -> None:
    st.markdown("**Quick actions**")
    cols = st.columns(5)
    if cols[0].button("Purchase Orders", use_container_width=True):
        navigation.go_to_list("purchase_orders_list")
    if cols[1].button("Goods Receipt", use_container_width=True):
        navigation.go_to_list("goods_receipt_list")
    if cols[2].button("Purchase Bills", use_container_width=True):
        navigation.go_to_list("purchases_list")
    if cols[3].button("Returns", use_container_width=True):
        navigation.go_to_list("purchase_returns_list")
    if cols[4].button("Reports", use_container_width=True):
        navigation.go_to_list("purchases_reports")


def render(services: dict) -> None:
    st.header("Purchases Overview")

    reports = services.get("reports_purchases")
    if reports is None:
        st.error("Purchase reports service is unavailable.")
        return

    bar = render_filter_sort_bar(
        PURCHASES_OVERVIEW,
        services=services,
        title="Purchases Overview",
    )
    start, end = _resolved_range(bar["filters"])
    st.caption(f"Period: **{start:%d %b %Y}** → **{end:%d %b %Y}**")

    _render_quick_actions()

    purchases_svc = services.get("purchases")
    try:
        summary = reports.dashboard_summary(start, end)
        overdue_count = reports.overdue_po_count()
        orders = purchases_svc.list_purchase_orders() if purchases_svc else []
        bills = purchases_svc.list_purchase_bills() if purchases_svc else []
    except Exception as exc:
        st.error(f"Could not load purchases overview: {exc}")
        return

    if not orders and not bills:
        st.info("No purchase activity yet. Create a purchase order to get started.")
        return

    metric_grid(
        [
            ("Open POs", summary.get("open_po_count", 0)),
            ("Overdue POs", overdue_count),
            ("Pending GRN qty", f"{summary.get('pending_grn_qty', 0):g}"),
            ("Purchases (range)", _fmt_currency(summary.get("purchases_this_month", 0))),
            ("Returns (range)", _fmt_currency(summary.get("returns_this_month", 0))),
            ("Vendor payables", _vendor_payables_total(services)),
        ],
        suffix="purchases_overview",
    )
    st.caption(
        "Open POs, overdue, pending GRN, and vendor payables are as of now. "
        "Purchases and returns use the Filters period."
    )

    _render_charts(reports, start, end)
    _render_queues(reports)
