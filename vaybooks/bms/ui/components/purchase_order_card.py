"""Cards for purchase orders."""

from __future__ import annotations

from datetime import date, datetime

import streamlit as st

from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.styles import render_card_grid, status_badge


def _fmt_date(value) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime("%d %b %Y")
    return str(value) if value else "—"


def _po_row(order) -> dict:
    return {
        "id": order.id,
        "po_number": order.po_number,
        "vendor_name": order.vendor_name,
        "vendor_id": order.vendor_id,
        "order_date": order.order_date,
        "status": order.status.value if hasattr(order.status, "value") else str(order.status),
        "total_amount": order.total_amount,
    }


def _po_card(row: dict, suffix: str) -> None:
    with st.container(border=True):
        st.markdown(f'<p class="z-card-title">{row.get("po_number")}</p>', unsafe_allow_html=True)
        st.caption(row.get("vendor_name") or "Vendor")
        st.caption(_fmt_date(row.get("order_date")))
        st.markdown(status_badge(row.get("status") or "Draft", compact=True), unsafe_allow_html=True)
        st.caption(f"₹{float(row.get('total_amount') or 0):,.0f}")
        if st.button("View", key=f"po_view_{suffix}_{row.get('id')}", use_container_width=True):
            navigation.go_to_detail("purchase_order_detail", row.get("id"))


def purchase_order_cards(rows: list[dict], suffix: str = "po") -> None:
    render_card_grid(rows, lambda row, _idx: _po_card(row, suffix), suffix=suffix)
