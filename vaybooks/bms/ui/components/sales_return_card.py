"""Cards for sales returns."""

from __future__ import annotations

from datetime import date, datetime

import streamlit as st

from vaybooks.bms.domain.shared.enums import SalesReturnStatus
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.sales_return_edit_dialog import (
    arm_sales_return_edit_dialog,
)
from vaybooks.bms.ui.styles import render_card_grid, status_badge


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
        "source_invoice_number": ret.source_invoice_number,
        "total_amount": ret.total_amount,
        "status": ret.status.value,
    }


def _return_card(row: dict, suffix: str) -> None:
    with st.container(border=True):
        st.markdown(f'<p class="z-card-title">{row.get("return_number")}</p>', unsafe_allow_html=True)
        st.caption(row.get("customer_name") or "Customer")
        st.caption(
            f"Invoice: {row.get('source_invoice_number') or 'Not linked'}"
        )
        st.caption(_fmt_date(row.get("return_date")))
        st.markdown(
            status_badge(row.get("status") or "Approved", compact=True),
            unsafe_allow_html=True,
        )
        st.caption(f"₹{float(row.get('total_amount') or 0):,.0f}")
        view_col, edit_col = st.columns(2)
        if view_col.button(
            "View",
            key=f"return_view_{suffix}_{row.get('id')}",
            use_container_width=True,
        ):
            navigation.go_to_detail("sales_return_detail", row.get("id"))
        if edit_col.button(
            "Edit",
            key=f"return_edit_{suffix}_{row.get('id')}",
            use_container_width=True,
            disabled=row.get("status") != SalesReturnStatus.PENDING.value,
        ):
            arm_sales_return_edit_dialog(row.get("id"))
            st.rerun()


def sales_return_cards(rows: list[dict], suffix: str = "sales_returns") -> None:
    render_card_grid(rows, lambda row, _idx: _return_card(row, suffix), suffix=suffix)
