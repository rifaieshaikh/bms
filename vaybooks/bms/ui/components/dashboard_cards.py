from datetime import date, datetime

import streamlit as st

from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.session_keys import ORDERS_KEEP_FILTERS, PENDING_ORDERS_PAGE, PENDING_ORDERS_NAV, VIEW_ORDER_ID

STATUS_COLORS = {
    "Draft": "gray",
    "In Progress": "blue",
    "Ready For Delivery": "orange",
    "Invoice Generated": "violet",
    "Completed": "green",
    "Delivered": "green",
    "Cancelled": "red",
}


def _fmt_date(value) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime("%d %b %Y")
    return str(value) if value else "—"


def queue_order_detail_navigation(order_id: str) -> None:
    """Set session state from a widget callback; navigate in main script."""
    st.session_state[VIEW_ORDER_ID] = order_id
    st.session_state[PENDING_ORDERS_NAV] = True


def maybe_navigate_to_order_detail() -> None:
    """Call at end of page render — switch_page cannot run inside callbacks."""
    if st.session_state.pop(PENDING_ORDERS_NAV, False):
        if navigation.customization_orders_page is not None:
            st.switch_page(navigation.customization_orders_page)


def queue_orders_page_navigation() -> None:
    st.session_state[PENDING_ORDERS_PAGE] = True


def queue_customer_orders_navigation(customer_id: str) -> None:
    st.session_state.orders_customer_filter = customer_id
    st.session_state[ORDERS_KEEP_FILTERS] = True
    queue_orders_page_navigation()


def maybe_navigate_to_orders_page() -> None:
    if st.session_state.pop(PENDING_ORDERS_PAGE, False):
        if navigation.customization_orders_page is not None:
            st.switch_page(navigation.customization_orders_page)


def order_action_cards(
    title: str,
    orders: list,
    key_prefix: str,
    accent: str = "blue",
    max_cards: int = 6,
):
    total = len(orders)
    st.markdown(f"#### {title} &nbsp; :{accent}[{total}]")

    if not orders:
        st.caption("Nothing here right now.")
        st.divider()
        return

    shown = orders[:max_cards]
    cols = st.columns(3)  # fixed grid so cards stay a consistent width
    for i, o in enumerate(shown):
        raw_id = o.get("id") or o.get("_id")
        order_id = str(raw_id) if raw_id is not None else ""
        status = o.get("order_status", "")
        color = "red" if accent == "red" else STATUS_COLORS.get(status, "gray")
        with cols[i % 3]:
            with st.container(border=True):
                st.markdown(f"**{o.get('order_number', '—')}**")
                st.caption(o.get("customer_name", ""))
                if status:
                    st.badge(status, color=color)
                st.write(f"📅 {_fmt_date(o.get('expected_delivery_date'))}")
                if order_id:
                    st.button(
                        "Open →",
                        key=f"{key_prefix}_{order_id}",
                        use_container_width=True,
                        on_click=queue_order_detail_navigation,
                        args=(order_id,),
                    )

    if total > max_cards:
        st.caption(f"+ {total - max_cards} more")
        if navigation.customization_orders_page is not None:
            st.page_link(
                navigation.customization_orders_page, label="View all in Orders →"
            )
    st.divider()
