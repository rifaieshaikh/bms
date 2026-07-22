"""Read-only cards for purchase bills list."""

from __future__ import annotations

from datetime import date, datetime

import streamlit as st

from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.styles import render_card_grid, status_badge

_PURCHASE_COLOR = "#0F766E"


def _fmt_date(value) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime("%d %b %Y")
    return str(value) if value else "—"


def _payment_badge(outstanding: float) -> str:
    if outstanding > 0.01:
        return status_badge("Credit", compact=True)
    return status_badge("Paid", compact=True)


def _purchase_card(row: dict, suffix: str) -> None:
    bill_no = row.get("vendor_bill_number") or row.get("voucher_number") or "—"
    total = float(row.get("total") or 0)
    outstanding = float(row.get("outstanding") or 0)
    vtype = row.get("voucher_type") or "Purchase Bill"

    with st.container(border=True):
        st.markdown(f'<p class="z-card-title">{bill_no}</p>', unsafe_allow_html=True)
        st.caption(row.get("vendor_name") or "Vendor")
        st.caption(_fmt_date(row.get("bill_date")))
        st.caption(vtype)
        st.markdown(
            f'<p style="color:{_PURCHASE_COLOR};font-weight:600;">₹{total:,.0f}</p>',
            unsafe_allow_html=True,
        )
        st.markdown(_payment_badge(outstanding), unsafe_allow_html=True)
        if st.button("View", key=f"purchase_view_{suffix}_{row.get('id')}", use_container_width=True):
            navigation.go_to_detail("purchase_detail", row.get("id"))


def purchase_cards(rows: list[dict], suffix: str = "purchases") -> None:
    render_card_grid(rows, lambda row, _idx: _purchase_card(row, suffix), suffix=suffix)
