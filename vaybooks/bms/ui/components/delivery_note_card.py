"""Cards for delivery notes."""

from __future__ import annotations

from datetime import date, datetime

import streamlit as st

from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.styles import render_card_grid, status_badge


def _fmt_date(value) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime("%d %b %Y")
    return str(value) if value else "—"


def _dn_row(dn) -> dict:
    return {
        "id": dn.id,
        "dn_number": dn.dn_number,
        "so_number": dn.so_number,
        "customer_name": dn.customer_name,
        "delivery_date": dn.delivery_date,
        "status": dn.status.value if hasattr(dn.status, "value") else str(dn.status),
        "total_amount": dn.total_amount,
    }


def _dn_card(row: dict, suffix: str) -> None:
    with st.container(border=True):
        st.markdown(f'<p class="z-card-title">{row.get("dn_number")}</p>', unsafe_allow_html=True)
        st.caption(row.get("customer_name") or "Customer")
        if row.get("so_number"):
            st.caption(f"SO {row.get('so_number')}")
        st.caption(_fmt_date(row.get("delivery_date")))
        st.markdown(status_badge(row.get("status") or "Draft", compact=True), unsafe_allow_html=True)
        st.caption(f"₹{float(row.get('total_amount') or 0):,.0f}")
        if st.button("View", key=f"dn_view_{suffix}_{row.get('id')}", use_container_width=True):
            navigation.go_to_detail("delivery_note_detail", row.get("id"))


def delivery_note_cards(rows: list[dict], suffix: str = "dn") -> None:
    render_card_grid(rows, lambda row: _dn_card(row, suffix))
