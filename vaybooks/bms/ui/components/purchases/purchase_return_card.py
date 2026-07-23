"""Cards for purchase returns."""

from __future__ import annotations

from datetime import date, datetime

import streamlit as st

from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.styles import render_card_grid


def _fmt_date(value) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime("%d %b %Y")
    return str(value) if value else "—"


def _return_row(ret) -> dict:
    return {
        "id": ret.id,
        "return_number": ret.return_number,
        "vendor_name": ret.vendor_name,
        "vendor_id": ret.vendor_id,
        "return_date": ret.return_date,
        "total_amount": ret.total_amount,
    }


def _return_card(row: dict, suffix: str) -> None:
    with st.container(border=True):
        st.markdown(
            f'<p class="z-card-title">{row.get("return_number")}</p>',
            unsafe_allow_html=True,
        )
        st.caption(row.get("vendor_name") or "Vendor")
        st.caption(_fmt_date(row.get("return_date")))
        st.caption(f"₹{float(row.get('total_amount') or 0):,.0f}")
        if st.button("View", key=f"pret_view_{suffix}_{row.get('id')}"):
            navigation.go_to_detail("purchase_return_detail", row.get("id"))


def purchase_return_cards(rows: list[dict], suffix: str = "returns") -> None:
    mapped = [_return_row(r) if not isinstance(r, dict) else r for r in rows]
    render_card_grid(
        mapped, lambda row, _idx: _return_card(row, suffix), suffix=suffix
    )
