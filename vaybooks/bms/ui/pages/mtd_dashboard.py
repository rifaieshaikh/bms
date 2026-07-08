from datetime import date

import streamlit as st

from vaybooks.bms.application.report_filters import DateRange, OrderMphFilter
from vaybooks.bms.domain.orders.order_refs import compact_order_ref
from vaybooks.bms.ui.pages.reports import AGGREGATED_PERIOD_LABEL


@st.cache_data(ttl=60, show_spinner=False)
def _period_summary(_reports, start: date, end: date):
    # _reports is prefixed with "_" so Streamlit skips hashing the service; the
    # cache key is (start, end), so switching ranges recomputes.
    return _reports.get_period_summary(start, end)


def render(services: dict):
    st.title("MTD Dashboard")

    today = date.today()
    default_start = today.replace(day=1)

    picked = st.date_input(
        "Period",
        value=(default_start, today),
        max_value=today,
        format="DD/MM/YYYY",
    )
    if isinstance(picked, (list, tuple)) and len(picked) == 2:
        start, end = picked
    else:
        # user is mid-selection (only one date chosen) — fall back to MTD
        start, end = default_start, today

    st.caption(f"Showing {start:%d %b %Y} → {end:%d %b %Y}")

    with st.spinner("Loading..."):
        summary = _period_summary(services["reports"], start, end)

    st.subheader("Operations")
    ops = st.columns(4)
    ops[0].metric("🧾 Orders Created", summary["orders_created"], border=True)
    ops[1].metric("📦 Delivered", summary["delivered"], border=True)
    ops[2].metric(
        "📋 Pending Activities (now)", summary["pending_activities"], border=True
    )
    ops[3].metric(
        "⏳ Bills Pending Invoice (now)", summary["bills_pending_invoice"], border=True
    )

    st.subheader("Customization Items")
    items = st.columns(4)
    items[0].metric("🧵 Items Created", summary["items_created"], border=True)
    items[1].metric("📦 Items Delivered", summary["items_delivered"], border=True)
    items[2].metric(
        "⌛ Pending — not delivered (now)", summary["items_pending"], border=True
    )
    items[3].metric(
        "🚚 Awaiting Delivery (now)", summary["items_awaiting_delivery"], border=True
    )

    st.subheader("Finance")
    fin = st.columns(3)
    fin[0].metric("🧾 Invoiced", f"₹{summary['invoiced']:,.0f}", border=True)
    fin[1].metric("💰 Receipts", f"₹{summary['receipts']:,.0f}", border=True)
    fin[2].metric("📉 Expenses", f"₹{summary['expenses']:,.0f}", border=True)

    fin2 = st.columns(3)
    fin2[0].metric("📈 Gross Margin", f"₹{summary['gross_margin']:,.0f}", border=True)
    fin2[1].metric(
        "🚚 Vendor Payments", f"₹{summary['vendor_payments']:,.0f}", border=True
    )
    fin2[2].metric("👷 Salary Paid", f"₹{summary['salary_payments']:,.0f}", border=True)

    st.subheader(AGGREGATED_PERIOD_LABEL)
    mph_rows = services["reports"].mph_report(OrderMphFilter(date_range=DateRange(start, end)))
    if mph_rows:
        for row in mph_rows:
            order_ref = compact_order_ref(row.get("order_number") or "")
            mph = row.get("margin_per_hour")
            mph_txt = f"₹{mph:,.0f}/h" if mph is not None else "—"
            st.caption(f"{order_ref} aggregated order MPH {mph_txt}")
