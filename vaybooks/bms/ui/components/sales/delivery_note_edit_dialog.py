"""Edit and invoice-from-DN dialogs for delivery notes."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.ui.components.common.document_custom_fields import (
    render_document_custom_fields,
)
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler, register_armed_dialog
from vaybooks.bms.ui.keyboard.dialog_actions import consume_submit, open_dialog
from vaybooks.bms.ui.keyboard.focus.registry import get_strategy
from vaybooks.bms.ui.keyboard.wired import mark_wired

DN_EDIT_DIALOG = "dn_edit_dialog"
DN_EDIT_FOCUS_STRATEGY = "delivery_note_edit_dialog"
DN_INVOICE_DIALOG = "dn_invoice_dialog"
DN_EDIT_SUBMIT_KEY = "dn_edit_dialog_submit"
DN_EDIT_FOCUS_KEY = f"{DN_EDIT_DIALOG}_focus"


def arm_dn_edit_dialog(dn_id: str) -> None:
    open_dialog(
        DN_EDIT_DIALOG, submit_key=DN_EDIT_SUBMIT_KEY, value=dn_id, clear_others=True
    )
    st.session_state[DN_EDIT_FOCUS_KEY] = f"{DN_EDIT_DIALOG}_date"
    mark_wired("dialog.save")


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
    register_armed_dialog(DN_EDIT_DIALOG)
    mark_wired("dialog.save")

    sales = services["sales"]
    dn = sales.get_delivery_note(dn_id)
    if not dn:
        st.error("Delivery note not found")
        return
    business = services["business"].get_profile()
    template = business.document_templates.get("delivery_note")

    date_key = f"{DN_EDIT_DIALOG}_date"
    save_key = f"{DN_EDIT_DIALOG}_save"
    edit_date = st.date_input(
        "Delivery date",
        value=dn.delivery_date,
        key=date_key,
    )
    edit_notes = st.text_area(
        "Notes", value=dn.notes, key=f"{DN_EDIT_DIALOG}_notes"
    )

    st.markdown("**Delivered quantities**")
    qty_keys: list[str] = []
    updated_lines: list[dict] = []
    for i, line in enumerate(dn.lines):
        uid = line.product_id or str(i)
        qkey = f"{DN_EDIT_DIALOG}_r{uid}_qty_recv"
        qty_keys.append(qkey)
        qty = st.number_input(
            f"{line.product_name or line.product_id}",
            min_value=0.0,
            value=float(line.qty_delivered or 0),
            key=qkey,
        )
        updated_lines.append(
            {
                "product_id": line.product_id,
                "product_name": line.product_name,
                "qty_delivered": qty,
                "rate": line.rate,
                "sales_order_line_id": line.sales_order_line_id,
            }
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

    do_save = st.button(
        "Update Delivery Note", type="primary", key=save_key
    ) or consume_submit(DN_EDIT_SUBMIT_KEY)

    restore = st.session_state.pop(DN_EDIT_FOCUS_KEY, None)
    get_strategy(DN_EDIT_FOCUS_STRATEGY).inject(
        chain=[date_key, *qty_keys, save_key],
        restore_key=restore,
        columns={"qty": qty_keys},
        above_first=date_key,
        below_last=save_key,
        component_key=f"dn_edit_{len(qty_keys)}",
    )

    if do_save:
        try:
            sales.update_delivery_note(
                dn.id,
                delivery_date=edit_date,
                lines=updated_lines,
                notes=edit_notes,
                custom_values=custom_values,
                terms_and_conditions=terms,
            )
            _clear_prefix(DN_EDIT_DIALOG)
            st.session_state.pop(DN_EDIT_SUBMIT_KEY, None)
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
