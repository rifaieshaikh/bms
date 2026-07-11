"""Cards for sales returns."""

from __future__ import annotations

from datetime import date, datetime

import streamlit as st

from vaybooks.bms.ui.styles import render_card_grid


def _fmt_date(value) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime("%d %b %Y")
    return str(value) if value else "—"


def _return_row(ret) -> dict:
    return {
        "id": ret.id,
        "return_number": ret.return_number,
        "customer_name": ret.customer_name,
        "return_date": ret.return_date,
        "total_amount": ret.total_amount,
    }


def _return_card(row: dict, suffix: str) -> None:
    with st.container(border=True):
        st.markdown(f'<p class="z-card-title">{row.get("return_number")}</p>', unsafe_allow_html=True)
        st.caption(row.get("customer_name") or "Customer")
        st.caption(_fmt_date(row.get("return_date")))
        st.caption(f"₹{float(row.get('total_amount') or 0):,.0f}")


def sales_return_cards(rows: list[dict], suffix: str = "sales_returns") -> None:
    render_card_grid(rows, lambda row: _return_card(row, suffix))
