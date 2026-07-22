from datetime import date, datetime

import streamlit as st

from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.styles import STATUS_BADGE_COLORS, render_card_grid, status_badge

STATUS_COLORS = STATUS_BADGE_COLORS


def _fmt_date(value) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime("%d %b %Y")
    return str(value) if value else "—"


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

    def _render(o, _i):
        raw_id = o.get("id") or o.get("_id")
        order_id = str(raw_id) if raw_id is not None else ""
        status = o.get("order_status", "")
        color = "red" if accent == "red" else STATUS_COLORS.get(status, "gray")
        with st.container(border=True):
            st.markdown(f"**{o.get('order_number', '—')}**")
            st.caption(o.get("customer_name", ""))
            if status:
                st.markdown(status_badge(status, color), unsafe_allow_html=True)
            st.write(f"📅 {_fmt_date(o.get('expected_delivery_date'))}")
            if order_id and st.button(
                "Open →",
                key=f"{key_prefix}_{order_id}",
                use_container_width=True,
            ):
                navigation.go_to_detail("order_detail", order_id)

    render_card_grid(shown, _render, suffix=key_prefix)

    if total > max_cards:
        st.caption(f"+ {total - max_cards} more")
        orders_page = navigation.page("orders_list")
        if orders_page is not None:
            st.page_link(orders_page, label="View all →")
    st.divider()
