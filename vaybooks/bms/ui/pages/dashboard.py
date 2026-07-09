from dataclasses import asdict

import streamlit as st

from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.dashboard_cards import order_action_cards
from vaybooks.bms.ui.components.inventory_product_card import inventory_low_stock_cards
from vaybooks.bms.ui.styles import metric_grid


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
    metric_grid(
        [
            ("🧾 Active Orders", _summary_int(summary, "active_orders")),
            ("⚙️ In Progress", _summary_int(summary, "pending_activity_orders")),
            ("✅ Completed", _completed_count(summary)),
            ("📋 Pending Activities", _summary_int(summary, "total_pending_activities")),
            (
                "📦 Delivered (Month)",
                _summary_int(summary, "delivered_this_month"),
            ),
            (
                "💰 Advance (Month)",
                f"₹{_summary_float(summary, 'total_advance_this_month'):,.0f}",
            ),
            (
                "🧾 Invoiced (Month)",
                f"₹{_summary_float(summary, 'total_invoice_this_month'):,.0f}",
            ),
            (
                "⏳ Bills Pending Invoice",
                _summary_int(summary, "bills_pending_invoice"),
            ),
            (
                "⌛ Items Not Delivered",
                _summary_int(summary, "items_pending"),
            ),
            (
                "🚚 Awaiting Delivery",
                _summary_int(summary, "items_awaiting_delivery"),
            ),
        ],
        suffix="dashboard_kpi",
    )


def _inventory_health_row(summary):
    metric_grid(
        [
            ("📦 Active Products", _summary_int(summary, "inventory_active_products")),
            (
                "📊 Total Units",
                f"{_summary_float(summary, 'inventory_total_units'):g}",
            ),
            (
                "💰 Stock Value",
                f"₹{_summary_float(summary, 'inventory_stock_value'):,.0f}",
            ),
            (
                "⚠️ Low Stock",
                _summary_int(summary, "inventory_low_stock_count"),
            ),
            (
                "🚫 Out of Stock",
                _summary_int(summary, "inventory_out_of_stock_count"),
            ),
            (
                "↔️ Movements (Month)",
                _summary_int(summary, "inventory_movements_this_month"),
            ),
        ],
        suffix="dashboard_inv_health",
    )


def _inventory_alerts(summary):
    low_items = _summary_list(summary, "inventory_low_stock_items")
    low_count = _summary_int(summary, "inventory_low_stock_count")
    out_count = _summary_int(summary, "inventory_out_of_stock_count")
    st.markdown(
        f"#### Inventory Alerts &nbsp; :orange[{low_count + out_count}]"
    )
    if not low_items:
        st.caption("All active products are above the low-stock threshold.")
    else:
        inventory_low_stock_cards(low_items, key_prefix="dash_inv_low")
    inv_stock_page = navigation.page("inventory_stock_list")
    reports_page = navigation.page("reports")
    link_cols = st.columns(2)
    if inv_stock_page is not None:
        link_cols[0].page_link(inv_stock_page, label="Stock on Hand →")
    if reports_page is not None:
        link_cols[1].page_link(reports_page, label="Inventory Reports →")
    st.divider()


def render(services: dict):
    st.title("Dashboard")
    with st.spinner("Loading dashboard..."):
        summary = _dashboard_summary(services["reports"])

    _kpi_row(summary)
    st.divider()

    st.markdown("#### Inventory Health")
    _inventory_health_row(summary)
    _inventory_alerts(summary)

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
