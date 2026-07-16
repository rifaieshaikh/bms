"""Edit and invoice-from-DN dialogs for delivery notes."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from vaybooks.bms.ui.components.document_custom_fields import (
    render_document_custom_fields,
)
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler

DN_EDIT_DIALOG = "dn_edit_dialog"
DN_INVOICE_DIALOG = "dn_invoice_dialog"


def arm_dn_edit_dialog(dn_id: str) -> None:
    st.session_state[DN_EDIT_DIALOG] = dn_id


def arm_dn_invoice_dialog(dn_id: str) -> None:
    st.session_state[DN_INVOICE_DIALOG] = dn_id


# Backward-compatible alias used by older callers.
def arm_invoice_from_dn(dn_id: str) -> None:
    arm_dn_invoice_dialog(dn_id)


def _clear_prefix(prefix: str) -> None:
    for key in list(st.session_state.keys()):
        if key == prefix or key.startswith(f"{prefix}_"):
            st.session_state.pop(key, None)


@st.dialog(
    "Edit Delivery Note",
    width="large",
    on_dismiss=make_dismiss_handler(DN_EDIT_DIALOG),
)
def _dn_edit_dialog(services: dict) -> None:
    dn_id = st.session_state.get(DN_EDIT_DIALOG)
    if not dn_id:
        return
    sales = services["sales"]
    dn = sales.get_delivery_note(dn_id)
    if not dn:
        st.error("Delivery note not found")
        return
    business = services["business"].get_profile()
    template = business.document_templates.get("delivery_note")

    edit_date = st.date_input(
        "Delivery date",
        value=dn.delivery_date,
        key=f"{DN_EDIT_DIALOG}_date",
    )
    edit_notes = st.text_area(
        "Notes", value=dn.notes, key=f"{DN_EDIT_DIALOG}_notes"
    )
    edited_df = st.data_editor(
        pd.DataFrame(
            [
                {
                    "product_id": line.product_id,
                    "product_name": line.product_name,
                    "qty_delivered": line.qty_delivered,
                    "rate": line.rate,
                    "sales_order_line_id": line.sales_order_line_id,
                }
                for line in dn.lines
            ]
        ),
        num_rows="dynamic",
        use_container_width=True,
        disabled=["product_id", "product_name", "sales_order_line_id"],
        key=f"{DN_EDIT_DIALOG}_lines",
    )
    initial_custom = {
        item.key: item.value for item in dn.document_content.custom_fields
    }
    custom_values = render_document_custom_fields(
        template.custom_fields if template else [],
        key_prefix=f"{DN_EDIT_DIALOG}_custom",
        initial_values=initial_custom,
    )
    terms = st.text_area(
        "Terms & Conditions",
        value=dn.document_content.terms_and_conditions,
        key=f"{DN_EDIT_DIALOG}_terms",
    )
    if st.button(
        "Update Delivery Note", type="primary", key=f"{DN_EDIT_DIALOG}_save"
    ):
        try:
            sales.update_delivery_note(
                dn.id,
                delivery_date=edit_date,
                lines=edited_df.to_dict("records"),
                notes=edit_notes,
                custom_values=custom_values,
                terms_and_conditions=terms,
            )
            _clear_prefix(DN_EDIT_DIALOG)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


@st.dialog(
    "Create invoice from DN",
    width="large",
    on_dismiss=make_dismiss_handler(DN_INVOICE_DIALOG),
)
def _dn_invoice_dialog(services: dict, *, default_received: float = 0.0) -> None:
    dn_id = st.session_state.get(DN_INVOICE_DIALOG)
    if not dn_id:
        return
    sales = services["sales"]
    accounting = services["accounting"]
    dn = sales.get_delivery_note(dn_id)
    if not dn:
        st.error("Delivery note not found")
        return
    store_accounts = accounting.get_store_accounts()
    if not store_accounts:
        st.error("Need at least one cash/bank store account.")
        return
    store_opts = {a.account_name: a.id for a in store_accounts}
    store_name = st.selectbox(
        "Received in",
        list(store_opts.keys()),
        key=f"{DN_INVOICE_DIALOG}_store",
    )
    inv_no = st.text_input(
        "Invoice number",
        value=dn.dn_number,
        key=f"{DN_INVOICE_DIALOG}_number",
    )
    received = st.number_input(
        "Amount received",
        min_value=0.0,
        value=float(default_received or dn.total_amount or 0),
        key=f"{DN_INVOICE_DIALOG}_received",
    )
    discount = st.number_input(
        "Discount",
        min_value=0.0,
        value=0.0,
        key=f"{DN_INVOICE_DIALOG}_discount",
    )
    if st.button("Post invoice", type="primary", key=f"{DN_INVOICE_DIALOG}_save"):
        try:
            sales.create_sales_invoice_from_dn(
                dn_id=dn.id,
                store_account_id=store_opts[store_name],
                store_invoice_number=inv_no,
                discount_amount=discount,
                amount_received=received,
            )
            _clear_prefix(DN_INVOICE_DIALOG)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def open_dn_detail_dialogs_if_armed(
    services: dict, *, default_received: float = 0.0
) -> None:
    if st.session_state.get(DN_EDIT_DIALOG):
        _dn_edit_dialog(services)
    if st.session_state.get(DN_INVOICE_DIALOG):
        _dn_invoice_dialog(services, default_received=default_received)
