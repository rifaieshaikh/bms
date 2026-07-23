"""Cards for goods receipts."""

from __future__ import annotations

from datetime import date, datetime

import streamlit as st

from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.styles import render_card_grid, status_badge


def _fmt_date(value) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime("%d %b %Y")
    return str(value) if value else "—"


def _grn_row(grn) -> dict:
    total = sum(line.line_total for line in grn.lines)
    return {
        "id": grn.id,
        "grn_number": grn.grn_number,
        "po_number": grn.po_number,
        "vendor_name": grn.vendor_name,
        "vendor_id": grn.vendor_id,
        "receipt_date": grn.receipt_date,
        "status": grn.status.value if hasattr(grn.status, "value") else str(grn.status),
        "total_amount": round(total, 2),
    }


def _grn_card(row: dict, suffix: str) -> None:
    with st.container(border=True):
        st.markdown(f'<p class="z-card-title">{row.get("grn_number")}</p>', unsafe_allow_html=True)
        st.caption(row.get("vendor_name") or "Vendor")
        if row.get("po_number"):
            st.caption(f"PO {row.get('po_number')}")
        st.caption(_fmt_date(row.get("receipt_date")))
        st.markdown(status_badge(row.get("status") or "Draft", compact=True), unsafe_allow_html=True)
        if st.button("View", key=f"grn_view_{suffix}_{row.get('id')}", use_container_width=True):
            navigation.go_to_detail("grn_detail", row.get("id"))


def grn_cards(rows: list[dict], suffix: str = "grn") -> None:
    render_card_grid(rows, lambda row, _idx: _grn_card(row, suffix), suffix=suffix)
