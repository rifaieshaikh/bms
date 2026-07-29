"""Finance Overview — KPIs, charts, and AR/AP queues."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from vaybooks.bms.application.report_filters import (
    CashMovementFilter,
    DateRange,
    ExpenseBySourceFilter,
    OutstandingFilter,
    TopCustomersFilter,
)
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.common.filter_sort_bar import (
    _mtd_range,
    _normalize_date_range,
    render_filter_sort_bar,
)
from vaybooks.bms.ui.components.common.overview_action_cards import (
    overview_action_cards,
)
from vaybooks.bms.ui.components.shared.dashboard_card import (
    DashboardCardSpec,
    dashboard_card_grid,
)
from vaybooks.bms.ui.finance_list_schemas import FINANCE_OVERVIEW
from vaybooks.bms.ui.styles import metric_grid

QUEUE_LIMIT = 8


def _fmt_currency(value: float) -> str:
    return f"₹{float(value or 0):,.0f}"


def _resolved_range(committed: dict) -> tuple[date, date]:
    return _normalize_date_range(committed.get("date_range")) or _mtd_range()


def _date_range(start: date, end: date) -> DateRange:
    return DateRange(start=start, end=end)


def _tone_if(positive: bool, tone: str) -> str:
    return tone if positive else "neutral"


def _chart_or_caption(title: str, df: pd.DataFrame, chart_fn, empty_msg: str) -> None:
    st.markdown(f"**{title}**")
    if df.empty:
        st.caption(empty_msg)
        return
    chart_fn(df)


def _render_quick_actions() -> None:
    st.markdown("**Quick actions**")
    cols = st.columns(5)
    if cols[0].button("Accounts", width="stretch"):
        navigation.go_to_list("accounts_list")
    if cols[1].button("Receipts", width="stretch"):
        navigation.go_to_list("receipts_list")
    if cols[2].button("Payments", width="stretch"):
        navigation.go_to_list("payments_list")
    if cols[3].button("Journal", width="stretch"):
        navigation.go_to_list("journal_list")
    if cols[4].button("Reports", width="stretch"):
        navigation.go_to_list("reports")


def _render_charts(reports, start: date, end: date) -> None:
    st.markdown("#### Charts")
    dr = _date_range(start, end)
    cash_rows = reports.cash_movement_report(CashMovementFilter(date_range=dr))
    expense_rows = reports.expense_by_source_report(
        ExpenseBySourceFilter(date_range=dr)
    )
    customer_rows = reports.top_customers_by_revenue(
        TopCustomersFilter(date_range=dr)
    )[:10]

    row1 = st.columns(2)
    with row1[0]:
        cash_df = (
            pd.DataFrame(cash_rows).set_index("flow_type")[["amount"]]
            if cash_rows
            else pd.DataFrame()
        )
        if not cash_df.empty:
            cash_df = cash_df.rename(columns={"amount": "Amount"})
        _chart_or_caption(
            "Cash movement",
            cash_df,
            st.bar_chart,
            "No cash vouchers in this date range.",
        )
    with row1[1]:
        expense_df = (
            pd.DataFrame(expense_rows).set_index("expense_source")[["total_amount"]]
            if expense_rows
            else pd.DataFrame()
        )
        if not expense_df.empty:
            expense_df = expense_df.rename(columns={"total_amount": "Spend"})
        _chart_or_caption(
            "Expense by source",
            expense_df,
            st.bar_chart,
            "No expenses in this date range.",
        )

    customer_df = (
        pd.DataFrame(customer_rows).set_index("customer_name")[["total_revenue"]]
        if customer_rows
        else pd.DataFrame()
    )
    if not customer_df.empty:
        customer_df = customer_df.rename(columns={"total_revenue": "Revenue"})
    _chart_or_caption(
        "Top customers by revenue",
        customer_df,
        st.bar_chart,
        "No customer revenue in this date range.",
    )


def _render_queues(reports) -> None:
    try:
        receivables = sorted(
            reports.customer_outstanding_report(OutstandingFilter()),
            key=lambda r: float(r.get("balance_due") or 0),
            reverse=True,
        )[:QUEUE_LIMIT]
        payables = sorted(
            reports.vendor_payables_report(OutstandingFilter()),
            key=lambda r: float(r.get("payable") or 0),
            reverse=True,
        )[:QUEUE_LIMIT]
    except Exception as exc:
        st.warning(f"Could not load AR/AP queues: {exc}")
        return

    overview_action_cards(
        "Top receivables",
        receivables,
        "finance_overview_ar",
        accent="orange",
        title_fn=lambda r: r.get("customer_name") or "—",
        subtitle_fn=lambda r: r.get("account_name") or "—",
        meta_fn=lambda r: _fmt_currency(r.get("balance_due") or 0),
        on_open=lambda r: navigation.go_to_detail(
            "account_detail", r.get("account_id")
        ),
        empty_msg="All clear — no customer receivables.",
        max_cards=QUEUE_LIMIT,
    )

    overview_action_cards(
        "Top payables",
        payables,
        "finance_overview_ap",
        accent="orange",
        title_fn=lambda r: r.get("vendor_name") or "—",
        subtitle_fn=lambda r: r.get("account_name") or "—",
        meta_fn=lambda r: _fmt_currency(r.get("payable") or 0),
        on_open=lambda r: navigation.go_to_detail(
            "account_detail", r.get("account_id")
        ),
        empty_msg="All clear — no vendor payables.",
        max_cards=QUEUE_LIMIT,
    )


def render(services: dict) -> None:
    st.header("Finance Overview")

    reports = services.get("reports_business")
    if reports is None:
        st.error("Finance reports service is unavailable.")
        return

    bar = render_filter_sort_bar(
        FINANCE_OVERVIEW,
        services=services,
        title="Finance Overview",
    )
    start, end = _resolved_range(bar["filters"])
    st.caption(f"Period: **{start:%d %b %Y}** → **{end:%d %b %Y}**")

    _render_quick_actions()

    try:
        summary = reports.get_period_summary(start, end)
        ar_rows = reports.customer_outstanding_report(OutstandingFilter())
        ap_rows = reports.vendor_payables_report(OutstandingFilter())
        cash_rows = reports.cash_movement_report(
            CashMovementFilter(date_range=_date_range(start, end))
        )
    except Exception as exc:
        st.error(f"Could not load finance overview: {exc}")
        return

    ar_total = sum(float(r.get("balance_due") or 0) for r in ar_rows)
    ap_total = sum(float(r.get("payable") or 0) for r in ap_rows)
    net_cash = sum(float(r.get("amount") or 0) for r in cash_rows)

    st.markdown("#### Attention")
    dashboard_card_grid(
        [
            DashboardCardSpec(
                title="Customer receivables",
                value=_fmt_currency(ar_total),
                icon="wallet",
                tone=_tone_if(ar_total > 0, "warning"),
                footer_text="View accounts",
                on_click=lambda: navigation.go_to_list("accounts_list"),
                key="finance_ar_total",
            ),
            DashboardCardSpec(
                title="Vendor payables",
                value=_fmt_currency(ap_total),
                icon="cash-banknote",
                tone=_tone_if(ap_total > 0, "warning"),
                footer_text="View accounts",
                on_click=lambda: navigation.go_to_list("accounts_list"),
                key="finance_ap_total",
            ),
            DashboardCardSpec(
                title="Net cash movement",
                value=_fmt_currency(net_cash),
                icon="chart-line",
                tone="success" if net_cash > 0 else ("danger" if net_cash < 0 else "primary"),
                footer_text="View journal",
                on_click=lambda: navigation.go_to_list("journal_list"),
                key="finance_net_cash",
            ),
        ],
        suffix="finance_overview_attention",
    )

    st.markdown("#### Period")
    metric_grid(
        [
            ("Invoiced", _fmt_currency(summary.get("invoiced", 0))),
            ("Receipts", _fmt_currency(summary.get("receipts", 0))),
            ("Expenses", _fmt_currency(summary.get("expenses", 0))),
            ("Gross margin", _fmt_currency(summary.get("gross_margin", 0))),
        ],
        suffix="finance_overview_period",
    )
    st.caption(
        "Receivables and payables are as of now. "
        "Invoiced, receipts, expenses, margin, and cash use the Filters period."
    )

    _render_charts(reports, start, end)
    _render_queues(reports)
