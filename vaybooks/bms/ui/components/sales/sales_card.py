"""Read-only cards for store sales list rows."""

from __future__ import annotations

from datetime import date, datetime

import streamlit as st

from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.styles import render_card_grid, status_badge

_SALES_AMOUNT_COLOR = "#6B3FA0"


def _fmt_date(value) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime("%d %b %Y")
    return str(value) if value else "—"


def _customer_name(party_name: str) -> str:
    rest = (party_name or "").strip()
    if rest.startswith("Customer - "):
        rest = rest[len("Customer - ") :].strip()
    if " - " in rest:
        name, _phone = rest.rsplit(" - ", 1)
        return name.strip() or "Customer"
    return rest or "Customer"


def _payment_badge(outstanding: float) -> str:
    if outstanding > 0.01:
        return status_badge("Unpaid", compact=True)
    return status_badge("Paid", compact=True)


def _sales_card(row: dict, suffix: str) -> None:
    store_no = row.get("store_invoice_number") or "—"
    gross = float(row.get("gross") or 0)
    net = float(row.get("net") or gross)
    balance = float(row.get("outstanding") or 0)

    with st.container(border=True):
        st.markdown(
            f'<p class="z-card-title">{store_no}</p>',
            unsafe_allow_html=True,
        )
        st.caption(_customer_name(row.get("party_name") or ""))
        project_id = row.get("reference_project_id") or ""
        project_name = (row.get("project_name") or "").strip()
        if project_name:
            st.caption(f"Project: {project_name}")
        elif project_id:
            st.caption(f"Project: {project_id[:8]}…")
        st.caption(_fmt_date(row.get("sale_date")))
        st.markdown(
            f'<p class="z-card-amount" style="color:{_SALES_AMOUNT_COLOR}">'
            f"₹{net:,.0f}</p>",
            unsafe_allow_html=True,
        )
        st.markdown(_payment_badge(balance), unsafe_allow_html=True)

        sale_id = row.get("id")
        if sale_id and st.button(
            "View",
            key=f"{suffix}_view_{sale_id}",
            use_container_width=True,
        ):
            navigation.go_to_detail("sales_detail", sale_id)


def sales_cards(rows: list[dict], *, suffix: str = "store_sales") -> None:
    render_card_grid(
        rows,
        lambda row, _i: _sales_card(row, suffix),
        suffix=suffix,
        card_min_width=240,
    )
