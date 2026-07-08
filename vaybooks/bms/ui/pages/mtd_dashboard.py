from datetime import date, timedelta

import streamlit as st

from vaybooks.bms.ui.styles import metric_grid

PERIOD_WIDGET_KEY = "period_dashboard_range"


@st.cache_data(ttl=60, show_spinner=False)
def _period_summary(_reports, start: date, end: date):
    return _reports.get_period_summary(start, end)


def _quarter_start(today: date) -> date:
    month = ((today.month - 1) // 3) * 3 + 1
    return today.replace(month=month, day=1)


def _pct(numerator: float, denominator: float) -> str:
    if not denominator:
        return "—"
    return f"{numerator / denominator * 100:.0f}%"


def _avg_per_order(amount: float, orders: int) -> str:
    if not orders:
        return "—"
    return f"₹{amount / orders:,.0f}"


def _avg_count_per(total: float, count: int) -> str:
    if not count:
        return "—"
    return f"{total / count:.1f}"


def _render_period_picker() -> tuple[date, date]:
    """Quick presets + date range; persists in session state."""
    today = date.today()
    default = (today.replace(day=1), today)
    if PERIOD_WIDGET_KEY not in st.session_state:
        st.session_state[PERIOD_WIDGET_KEY] = default

    presets = st.columns(5)
    if presets[0].button("Today", key="period_preset_today", use_container_width=True):
        st.session_state[PERIOD_WIDGET_KEY] = (today, today)
        st.rerun()
    if presets[1].button("Last 7 days", key="period_preset_7d", use_container_width=True):
        st.session_state[PERIOD_WIDGET_KEY] = (today - timedelta(days=6), today)
        st.rerun()
    if presets[2].button("MTD", key="period_preset_mtd", use_container_width=True):
        st.session_state[PERIOD_WIDGET_KEY] = (today.replace(day=1), today)
        st.rerun()
    if presets[3].button("Last 30 days", key="period_preset_30d", use_container_width=True):
        st.session_state[PERIOD_WIDGET_KEY] = (today - timedelta(days=29), today)
        st.rerun()
    if presets[4].button("This quarter", key="period_preset_qtr", use_container_width=True):
        st.session_state[PERIOD_WIDGET_KEY] = (_quarter_start(today), today)
        st.rerun()

    picked = st.date_input(
        "Custom period",
        value=st.session_state[PERIOD_WIDGET_KEY],
        max_value=today,
        format="DD/MM/YYYY",
        key=PERIOD_WIDGET_KEY,
    )
    if isinstance(picked, (list, tuple)) and len(picked) == 2:
        start, end = picked
        if start > end:
            start, end = end, start
        return start, end
    return default


def _period_mph(gross_margin: float, labor_hours: float) -> str:
    """Margin earned per hour of actual logged labor in the period."""
    if labor_hours <= 0:
        return "—"
    return f"₹{gross_margin / labor_hours:,.0f}/h"


def render(services: dict):
    st.title("Period Dashboard")
    start, end = _render_period_picker()
    st.caption(f"Period: **{start:%d %b %Y}** → **{end:%d %b %Y}**")

    with st.spinner("Loading..."):
        summary = _period_summary(services["reports"], start, end)

    orders_created = summary.get("orders_created", 0)
    invoiced = summary.get("invoiced", 0)
    items_created = summary.get("items_created", 0)

    st.subheader("Orders")
    metric_grid(
        [
            ("🧾 Orders created", orders_created),
            ("📦 Orders delivered", summary.get("delivered", 0)),
            ("✅ Orders completed", summary.get("completed_orders", 0)),
            (
                "📦 Delivery rate",
                _pct(summary.get("delivered", 0), orders_created),
            ),
        ],
        suffix="period_ops",
    )

    st.divider()
    st.subheader("Customers")
    customers_with_orders = summary.get("customers_with_orders", 0)
    customers_invoiced = summary.get("customers_invoiced", 0)
    metric_grid(
        [
            ("👤 New customers", summary.get("customers_created", 0)),
            ("🛍️ Customers with orders", customers_with_orders),
            ("🔁 Repeat customers", summary.get("repeat_customers", 0)),
            ("🧾 Customers invoiced", customers_invoiced),
            (
                "📊 Avg orders / customer",
                _avg_count_per(orders_created, customers_with_orders),
            ),
            (
                "💰 Avg revenue / customer",
                _avg_per_order(invoiced, customers_invoiced),
            ),
        ],
        suffix="period_customers",
    )

    st.divider()
    st.subheader("Items")
    metric_grid(
        [
            ("🧵 Items created", items_created),
            ("📦 Items delivered", summary.get("items_delivered", 0)),
            (
                "📦 Item delivery rate",
                _pct(summary.get("items_delivered", 0), items_created),
            ),
        ],
        suffix="period_items",
    )

    st.divider()
    st.subheader("Finance")
    metric_grid(
        [
            ("🧾 Invoiced", f"₹{invoiced:,.0f}"),
            ("💰 Receipts", f"₹{summary.get('receipts', 0):,.0f}"),
            ("📉 Expenses", f"₹{summary.get('expenses', 0):,.0f}"),
            ("📈 Gross margin", f"₹{summary.get('gross_margin', 0):,.0f}"),
            ("📊 Margin %", _pct(summary.get("gross_margin", 0), invoiced)),
            ("💳 Collection rate", _pct(summary.get("receipts", 0), invoiced)),
            ("🧾 Avg invoice / order", _avg_per_order(invoiced, orders_created)),
            ("🚚 Vendor payments", f"₹{summary.get('vendor_payments', 0):,.0f}"),
            ("👷 Salary paid", f"₹{summary.get('salary_payments', 0):,.0f}"),
        ],
        suffix="period_finance",
    )

    st.divider()
    st.subheader("Time & labor")
    metric_grid(
        [
            ("🧵 Stitching hours", f"{summary.get('stitching_hours', 0):.1f}"),
            ("✋ Hand work hours", f"{summary.get('hand_work_hours', 0):.1f}"),
            ("⏱️ Total labor hours", f"{summary.get('total_time_hours', 0):.1f}"),
            ("📝 Time entries", summary.get("time_entry_count", 0)),
            (
                "📈 Period MPH",
                _period_mph(
                    summary.get("gross_margin", 0),
                    summary.get("total_time_hours", 0),
                ),
            ),
        ],
        suffix="period_time",
    )
    st.caption(
        "Period MPH = period gross margin ÷ actual logged labor hours."
    )
