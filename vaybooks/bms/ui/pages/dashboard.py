from dataclasses import asdict

import streamlit as st

from vaybooks.bms.ui.components.dashboard_cards import order_action_cards, maybe_navigate_to_order_detail


def _summary_value(summary, name: str, default):
    if isinstance(summary, dict):
        return summary.get(name, default)
    return getattr(summary, name, default)


def _summary_int(summary, name: str, default: int = 0) -> int:
    value = _summary_value(summary, name, default)
    return default if value is None else value


def _summary_float(summary, name: str, default: float = 0.0) -> float:
    value = _summary_value(summary, name, default)
    return default if value is None else value


def _summary_list(summary, name: str) -> list:
    return _summary_value(summary, name, []) or []


def _completed_count(summary) -> int:
    if hasattr(summary, "completed_orders"):
        return summary.completed_orders
    return len(_summary_list(summary, "recently_completed"))


@st.cache_data(ttl=30, show_spinner=False)
def _dashboard_summary(_reports):
    # _reports is prefixed with "_" so Streamlit skips hashing the (unhashable)
    # service object; the summary is recomputed at most once every 30s.
    return asdict(_reports.get_dashboard_summary())


def _kpi_row(summary):
    r1 = st.columns(4)
    r1[0].metric("🧾 Active Orders", _summary_int(summary, "active_orders"), border=True)
    r1[1].metric(
        "⚙️ In Progress", _summary_int(summary, "pending_activity_orders"), border=True
    )
    r1[2].metric("✅ Completed", _completed_count(summary), border=True)
    r1[3].metric(
        "📋 Pending Activities",
        _summary_int(summary, "total_pending_activities"),
        border=True,
    )

    r2 = st.columns(4)
    r2[0].metric(
        "📦 Delivered (Month)", _summary_int(summary, "delivered_this_month"), border=True
    )
    r2[1].metric(
        "💰 Advance (Month)",
        f"₹{_summary_float(summary, 'total_advance_this_month'):,.0f}",
        border=True,
    )
    r2[2].metric(
        "🧾 Invoiced (Month)",
        f"₹{_summary_float(summary, 'total_invoice_this_month'):,.0f}",
        border=True,
    )
    r2[3].metric(
        "⏳ Bills Pending Invoice",
        _summary_int(summary, "bills_pending_invoice"),
        border=True,
    )


def render(services: dict):
    st.title("Dashboard")
    with st.spinner("Loading dashboard..."):
        summary = _dashboard_summary(services["reports"])

    _kpi_row(summary)
    st.divider()

    order_action_cards(
        "Today's ETD Orders", _summary_list(summary, "etd_today"), "etd", accent="orange"
    )
    order_action_cards(
        "Overdue Orders", _summary_list(summary, "overdue_orders"), "overdue", accent="red"
    )
    order_action_cards(
        "In Progress", _summary_list(summary, "in_progress_orders"), "progress", accent="blue"
    )
    order_action_cards(
        "Recently Completed",
        _summary_list(summary, "recently_completed"),
        "completed",
        accent="green",
    )
    maybe_navigate_to_order_detail()
