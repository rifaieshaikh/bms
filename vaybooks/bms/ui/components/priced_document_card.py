"""Responsive cards for estimates and quotations."""

from __future__ import annotations

from datetime import date, datetime

import streamlit as st

from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.priced_document_dialog import (
    arm_priced_document_dialog,
)
from vaybooks.bms.ui.styles import render_card_grid, status_badge


def _fmt_date(value) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime("%d %b %Y")
    return str(value) if value else "—"


def priced_document_row(document, document_type: str) -> dict:
    is_estimate = document_type == "estimate"
    return {
        "id": document.id,
        "document_type": document_type,
        "number": (
            document.estimate_number
            if is_estimate
            else document.quotation_number
        ),
        "customer_name": document.customer_name,
        "customer_id": document.customer_id,
        "document_date": (
            document.estimate_date if is_estimate else document.quotation_date
        ),
        "estimate_number": (
            document.estimate_number if is_estimate else None
        ),
        "quotation_number": (
            None if is_estimate else document.quotation_number
        ),
        "estimate_date": document.estimate_date if is_estimate else None,
        "quotation_date": None if is_estimate else document.quotation_date,
        "status": (
            document.status.value
            if hasattr(document.status, "value")
            else str(document.status)
        ),
        "total_amount": document.total_amount,
    }


def _is_editable(row: dict) -> bool:
    terminal = {"Cancelled", "Expired"}
    if row["document_type"] == "quotation":
        terminal.update({"Converted", "Rejected"})
    return row.get("status") not in terminal


def _priced_document_card(row: dict, suffix: str) -> None:
    document_type = row["document_type"]
    detail_key = (
        "estimate_detail"
        if document_type == "estimate"
        else "quotation_detail"
    )
    with st.container(border=True):
        st.markdown(
            f'<p class="z-card-title">{row.get("number")}</p>',
            unsafe_allow_html=True,
        )
        st.caption(row.get("customer_name") or "Customer")
        st.caption(_fmt_date(row.get("document_date")))
        st.markdown(
            status_badge(row.get("status") or "Draft", compact=True),
            unsafe_allow_html=True,
        )
        st.caption(f"₹{float(row.get('total_amount') or 0):,.0f}")

        if _is_editable(row):
            edit_col, view_col = st.columns(2)
            if edit_col.button(
                "Edit",
                key=f"{document_type}_edit_{suffix}_{row.get('id')}",
                use_container_width=True,
            ):
                arm_priced_document_dialog(
                    document_type, document_id=row.get("id")
                )
                st.rerun()
        else:
            view_col = st

        if view_col.button(
            "View",
            key=f"{document_type}_view_{suffix}_{row.get('id')}",
            type="primary",
            use_container_width=True,
        ):
            navigation.go_to_detail(detail_key, row.get("id"))


def priced_document_cards(
    rows: list[dict], *, document_type: str, suffix: str
) -> None:
    render_card_grid(
        rows,
        lambda row, _idx: _priced_document_card(row, suffix),
        suffix=suffix,
    )
