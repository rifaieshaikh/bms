"""Shared store invoice number input for create/edit sales invoice dialogs."""

from __future__ import annotations

from datetime import date
from typing import Optional

import streamlit as st


def render_store_invoice_number_field(
    sales_service,
    *,
    key: str,
    voucher_date: Optional[date] = None,
    existing_number: str = "",
    label: str = "Store invoice number",
    editable_existing: bool = False,
) -> str:
    """Render invoice number UI for app (preview) or external (required input).

    Returns the value to pass to create/update. In app mode create flows this is
    empty (assigned on save). In app mode edit, returns ``existing_number``.
    """
    mode = "external"
    if sales_service is not None and hasattr(
        sales_service, "sales_invoice_numbering_mode"
    ):
        mode = sales_service.sales_invoice_numbering_mode()

    if mode == "app":
        if existing_number:
            st.text_input(
                label,
                value=existing_number,
                disabled=True,
                key=key,
            )
            return existing_number
        preview = None
        if hasattr(sales_service, "preview_next_sales_invoice_number"):
            preview = sales_service.preview_next_sales_invoice_number(
                voucher_date or date.today()
            )
        if preview:
            st.caption(f"Will be assigned on save: **{preview}**")
        else:
            st.caption("Invoice number will be assigned automatically on save.")
        return ""

    return st.text_input(
        label,
        value=existing_number if editable_existing or existing_number else "",
        key=key,
    )
