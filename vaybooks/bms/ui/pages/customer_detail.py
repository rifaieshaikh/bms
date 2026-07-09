"""Customer detail route (`?id=<customer_id>`): profile, dashboard, orders."""

from datetime import date, datetime

import streamlit as st

from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.order_card import order_cards
from vaybooks.bms.ui.styles import metric_grid, panel, status_badge

RECENT_ORDER_LIMIT = 5


def _fmt_date(value) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime("%d %b %Y")
    return str(value) if value else "—"


def _format_balance(balance: float) -> str:
    if abs(balance) < 0.01:
        return "Settled"
    if balance > 0:
        return f"Due \u20b9{balance:,.0f}"
    return f"Advance \u20b9{abs(balance):,.0f}"


def render(services: dict):
    customer_service = services["customers"]
    order_service = services["orders"]
    accounting = services.get("accounting")

    customer_id = navigation.current_detail_id("customer_detail")

    if st.button("← Back to customers", key="customer_back"):
        navigation.go_back_to_list("customers", "customers_list")
        return

    customer = customer_service.get_customer_detail(customer_id) if customer_id else None
    if not customer:
        st.error("Customer not found.")
        return

    st.title(customer.customer_name)

    with panel(f"cust_head_{customer.id}"):
        with st.container(border=True):
            info = st.columns(3)
            info[0].write(f"**Phone:** {customer.phone_number}")
            info[1].write(f"**Alt:** {customer.alternate_phone_number or '—'}")
            info[2].write(f"**Since:** {_fmt_date(customer.created_at)}")
            if customer.address:
                st.caption(f"📍 {customer.address}")
            if customer.notes:
                st.caption(f"📝 {customer.notes}")

    try:
        summary = order_service.get_customer_summary(customer.id)
    except Exception:
        summary = {"order_count": 0, "active_count": 0, "total_invoiced": 0.0}

    try:
        account = accounting.get_customer_account(customer.id) if accounting else None
        balance = account.current_balance if account else 0.0
    except Exception:
        balance = 0.0

    total_orders = summary.get("order_count", 0)

    balance_color = (
        "red" if balance > 0.01 else ("green" if balance < -0.01 else "gray")
    )
    st.markdown(
        "**Balance:** "
        + status_badge(_format_balance(balance), balance_color),
        unsafe_allow_html=True,
    )
    metric_grid(
        [
            ("Total Orders", str(total_orders)),
            ("Active Orders", str(summary.get("active_count", 0))),
            ("Total Invoiced", f"\u20b9{summary.get('total_invoiced', 0.0):,.0f}"),
        ],
        suffix=f"cust_{customer.id}",
    )

    header = st.columns([3, 1])
    header[0].subheader("Recent Orders")
    with header[1]:
        if st.button(
            "View all orders →",
            use_container_width=True,
            key="cd_view_orders",
        ):
            navigation.go_to_list("orders_list", customer=customer.id)
            return

    try:
        recent = order_service.list_recent_by_customer(customer.id, RECENT_ORDER_LIMIT)
    except Exception:
        recent = []

    if not recent:
        st.caption("No orders yet.")
        return

    order_cards(recent, key_prefix=f"cd_ord_{customer.id}")

    if total_orders > RECENT_ORDER_LIMIT:
        st.caption(f"Showing latest {RECENT_ORDER_LIMIT} of {total_orders} orders.")
