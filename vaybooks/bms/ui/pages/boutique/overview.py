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
from vaybooks.bms.ui.styles import metric_grid

QUEUE_LIMIT = 8


def _fmt_currency(value: float) -> str:
    return f"\u20b9{float(value or 0):,.0f}"


def _resolved_range(committed: dict) -> tuple[date, date]:
    return _normalize_date_range(committed.get("date_range")) or _mtd_range()


def _render_quick_actions() -> None:
    st.markdown("**Quick actions**")
    cols = st.columns(5)
    if cols[0].button("Orders", use_container_width=True):
        navigation.go_to_list("orders_list")
    if cols[1].button("Measurements", use_container_width=True):
        navigation.go_to_list("measurements_list")
    if cols[2].button("Tasks", use_container_width=True):
        navigation.go_to_list("time_list")
    if cols[3].button("Calendar", use_container_width=True):
        navigation.go_to_list("calendar_list")
    if cols[4].button("Reports", use_container_width=True):
        navigation.go_to_list("boutique_reports")


def _render_pipeline_chart(reports) -> None:
    breakdown = reports.status_breakdown()
    st.markdown("**Order pipeline by status**")
    if not breakdown:
        st.caption("No active orders.")
        return
    df = pd.DataFrame(breakdown).set_index("status")[["count"]]
    df = df.rename(columns={"count": "Orders"})
    st.bar_chart(df)
    st.caption("As of now - excludes cancelled orders.")


def _render_queues(reports) -> None:
    overdue = reports.overdue_queue(limit=QUEUE_LIMIT)
    pending = reports.bills_pending_invoice_queue(limit=QUEUE_LIMIT)

    with st.expander(f"Overdue orders ({len(overdue)})", expanded=bool(overdue)):
        st.caption("As of now - ETD past and not yet delivered.")
        if not overdue:
            st.caption("All clear - no overdue orders.")
        else:
            for row in overdue:
                cols = st.columns([3, 3, 2, 1])
                cols[0].markdown(f"**{row.get('order_number')}**")
                cols[1].write(row.get("customer_name") or "\u2014")
                cols[2].write(f"{row.get('days_overdue')} days")
                if cols[3].button(
                    "Open",
                    key=f"boutique_overview_overdue_{row.get('id')}",
                    use_container_width=True,
                ):
                    navigation.go_to_detail("order_detail", row.get("id"))

    with st.expander(
        f"Bills pending invoice ({len(pending)})", expanded=bool(pending)
    ):
        st.caption("As of now - order bills not yet invoiced.")
        if not pending:
            st.caption("All clear - no bills pending invoice.")
        else:
            for row in pending:
                cols = st.columns([3, 4, 2, 1])
                cols[0].markdown(f"**{row.get('order_number')}**")
                cols[1].write(row.get("customer_name") or "\u2014")
                cols[2].write(f"{row.get('pending_bills')} bills")
                if cols[3].button(
                    "Open",
                    key=f"boutique_overview_pending_{row.get('id')}",
                    use_container_width=True,
                ):
                    navigation.go_to_detail("order_detail", row.get("id"))


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
        return

    metric_grid(
        [
            ("Open orders", summary.get("open_orders", 0)),
            ("Overdue orders", summary.get("overdue_orders", 0)),
            ("Bills pending invoice", summary.get("bills_pending_invoice", 0)),
            ("Bills pending delivery", summary.get("bills_pending_delivery", 0)),
            ("Invoiced (range)", _fmt_currency(summary.get("invoiced_revenue", 0))),
            ("Hours logged (range)", f"{summary.get('hours_logged', 0):g}"),
        ],
        suffix="boutique_overview",
    )
    st.caption(
        "Open, overdue, and pending counts are as of now. "
        "Invoiced revenue and logged hours use the Filters period."
    )

    _render_pipeline_chart(reports)
    _render_queues(reports)
