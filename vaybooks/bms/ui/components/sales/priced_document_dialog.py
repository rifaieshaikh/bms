"""Create and edit dialogs for estimates and quotations."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.sales.priced_document_form import (
    render_priced_document_form,
)
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler

ESTIMATE_INVOICE_DIALOG = "estimate_invoice_dialog"


def _dialog_key(document_type: str) -> str:
    return f"{document_type}_document_dialog"


def _form_prefix(document_type: str) -> str:
    return f"{document_type}_document_form"


def arm_priced_document_dialog(
    document_type: str, *, document_id: str | None = None
) -> None:
    from vaybooks.bms.ui.keyboard.dialog_actions import open_dialog
    from vaybooks.bms.ui.keyboard.wired import mark_wired

    dialog_key = _dialog_key(document_type)
    form_prefix = _form_prefix(document_type)
    for key in list(st.session_state.keys()):
        if key == dialog_key or key.startswith(form_prefix):
            st.session_state.pop(key, None)
    open_dialog(
        dialog_key,
        submit_key=f"{form_prefix}_kb_submit",
        value=document_id or "new",
        clear_others=True,
    )
    mark_wired("dialog.save")


def arm_estimate_invoice_dialog(estimate_id: str) -> None:
    from vaybooks.bms.ui.keyboard.dialog_actions import open_dialog

    for key in list(st.session_state.keys()):
        if key == ESTIMATE_INVOICE_DIALOG or key.startswith(
            f"{ESTIMATE_INVOICE_DIALOG}_"
        ):
            st.session_state.pop(key, None)
    open_dialog(
        ESTIMATE_INVOICE_DIALOG,
        submit_key=f"{ESTIMATE_INVOICE_DIALOG}_kb_submit",
        value=estimate_id,
        clear_others=True,
    )


def _clear(document_type: str) -> None:
    dialog_key = _dialog_key(document_type)
    form_prefix = _form_prefix(document_type)
    for key in list(st.session_state.keys()):
        if key == dialog_key or key.startswith(form_prefix):
            st.session_state.pop(key, None)


def _clear_estimate_invoice() -> None:
    for key in list(st.session_state.keys()):
        if key == ESTIMATE_INVOICE_DIALOG or key.startswith(
            f"{ESTIMATE_INVOICE_DIALOG}_"
        ):
            st.session_state.pop(key, None)


def _render_dialog(services: dict, document_type: str) -> None:
    document_id = st.session_state.get(_dialog_key(document_type))
    if not document_id:
        return

    existing = None
    if document_id != "new":
        getter = (
            services["sales"].get_estimate
            if document_type == "estimate"
            else services["sales"].get_quotation
        )
        existing = getter(document_id)
        if existing is None:
            st.error("Document not found")
            return

    try:
        if render_priced_document_form(
            services,
            document_type=document_type,
            existing=existing,
            key_prefix=_form_prefix(document_type),
        ):
            _clear(document_type)
            st.rerun()
    except Exception as exc:
        st.error(str(exc))


@st.dialog(
    "Create Estimate",
    width="large",
    on_dismiss=make_dismiss_handler("estimate_document_dialog"),
)
def _create_estimate_dialog(services: dict) -> None:
    _render_dialog(services, "estimate")


@st.dialog(
    "Edit Estimate",
    width="large",
    on_dismiss=make_dismiss_handler("estimate_document_dialog"),
)
def _edit_estimate_dialog(services: dict) -> None:
    _render_dialog(services, "estimate")


@st.dialog(
    "Create Quotation",
    width="large",
    on_dismiss=make_dismiss_handler("quotation_document_dialog"),
)
def _create_quotation_dialog(services: dict) -> None:
    _render_dialog(services, "quotation")


@st.dialog(
    "Edit Quotation",
    width="large",
    on_dismiss=make_dismiss_handler("quotation_document_dialog"),
)
def _edit_quotation_dialog(services: dict) -> None:
    _render_dialog(services, "quotation")


@st.dialog(
    "Convert Estimate to Sales Invoice",
    width="large",
    on_dismiss=make_dismiss_handler(ESTIMATE_INVOICE_DIALOG),
)
def _estimate_invoice_dialog(services: dict) -> None:
    estimate_id = st.session_state.get(ESTIMATE_INVOICE_DIALOG)
    if not estimate_id:
        return
    sales = services["sales"]
    estimate = sales.get_estimate(estimate_id)
    if not estimate:
        st.error("Estimate not found")
        return
    accounting = services["accounting"]
    store_accounts = accounting.get_store_accounts()
    if not store_accounts:
        st.warning("Add a cash or bank store account first.")
        return
    store_by_id = {account.id: account for account in store_accounts}
    store_id = st.selectbox(
        "Receive in",
        list(store_by_id),
        format_func=lambda account_id: store_by_id[account_id].account_name,
        key=f"{ESTIMATE_INVOICE_DIALOG}_store",
    )
    invoice_number = st.text_input(
        "Store invoice number", key=f"{ESTIMATE_INVOICE_DIALOG}_number"
    )
    received = st.number_input(
        "Amount received",
        min_value=0.0,
        value=0.0,
        key=f"{ESTIMATE_INVOICE_DIALOG}_received",
    )
    if st.button(
        "Create invoice", type="primary", key=f"{ESTIMATE_INVOICE_DIALOG}_save"
    ):
        try:
            if not invoice_number.strip():
                raise ValueError("Store invoice number is required")
            voucher = sales.convert_estimate_to_invoice(
                estimate.id,
                store_account_id=store_id,
                store_invoice_number=invoice_number.strip(),
                amount_received=received,
            )
            _clear_estimate_invoice()
            navigation.go_to_detail("sales_detail", voucher.id)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def open_priced_document_dialog_if_armed(
    services: dict, document_type: str
) -> None:
    if document_type == "estimate" and st.session_state.get(ESTIMATE_INVOICE_DIALOG):
        _estimate_invoice_dialog(services)
        return
    document_id = st.session_state.get(_dialog_key(document_type))
    if not document_id:
        return
    if document_type == "estimate":
        dialog = (
            _create_estimate_dialog
            if document_id == "new"
            else _edit_estimate_dialog
        )
    else:
        dialog = (
            _create_quotation_dialog
            if document_id == "new"
            else _edit_quotation_dialog
        )
    dialog(services)
