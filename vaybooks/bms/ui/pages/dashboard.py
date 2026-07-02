import streamlit as st

from vaybooks.bms.ui.components.dashboard_cards import order_action_cards


def _summary_int(summary, name: str, default: int = 0) -> int:
    value = getattr(summary, name, default)
    return default if value is None else value


def _summary_float(summary, name: str, default: float = 0.0) -> float:
    value = getattr(summary, name, default)
    return default if value is None else value


def _summary_list(summary, name: str) -> list:
    return getattr(summary, name, []) or []


def _completed_count(summary) -> int:
    if hasattr(summary, "completed_orders"):
        return summary.completed_orders
    return len(_summary_list(summary, "recently_completed"))


@st.cache_data(ttl=30, show_spinner=False)
def _dashboard_summary(_reports):
    # _reports is prefixed with "_" so Streamlit skips hashing the (unhashable)
    # service object; the summary is recomputed at most once every 30s.
    return _reports.get_dashboard_summary()


def render(services: dict):
    st.title("Dashboard")
    with st.spinner("Loading dashboard..."):
        summary = _dashboard_summary(services["reports"])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Active Orders", _summary_int(summary, "active_orders"))
    c2.metric("In Progress", _summary_int(summary, "pending_activity_orders"))
    c3.metric("Completed", _completed_count(summary))
    c4.metric("Pending Activities", _summary_int(summary, "total_pending_activities"))

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Delivered This Month", _summary_int(summary, "delivered_this_month"))
    c6.metric("Advance This Month", f"₹{_summary_float(summary, 'total_advance_this_month'):,.0f}")
    c7.metric(
        "Invoice Amount This Month",
        f"₹{_summary_float(summary, 'total_invoice_this_month'):,.0f}",
    )
    c8.metric("Bills Pending Invoice", _summary_int(summary, "bills_pending_invoice"))

    order_action_cards("Today's ETD Orders", _summary_list(summary, "etd_today"), "etd")
    order_action_cards("Overdue Orders", _summary_list(summary, "overdue_orders"), "overdue")
    order_action_cards(
        "In Progress Orders", _summary_list(summary, "in_progress_orders"), "progress"
    )
    order_action_cards(
        "Recently Completed", _summary_list(summary, "recently_completed"), "completed"
    )
