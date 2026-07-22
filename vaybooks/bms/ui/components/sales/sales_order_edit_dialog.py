"""Edit and create-invoice dialogs for sales orders."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.domain.sales.sales_line_resolver import business_is_registered
from vaybooks.bms.domain.shared.enums import PartyRegistrationType
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.common.document_custom_fields import (
    render_document_custom_fields,
)
from vaybooks.bms.ui.components.sales.sales_lines_editor import render_sales_lines_editor
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler

SO_EDIT_DIALOG = "so_edit_dialog"
SO_INVOICE_DIALOG = "so_invoice_dialog"


def arm_so_edit_dialog(order_id: str) -> None:
    st.session_state[SO_EDIT_DIALOG] = order_id


def arm_so_invoice_dialog(order_id: str) -> None:
    st.session_state[SO_INVOICE_DIALOG] = order_id


def _clear_prefix(prefix: str) -> None:
    for key in list(st.session_state.keys()):
        if key == prefix or key.startswith(f"{prefix}_"):
            st.session_state.pop(key, None)


@st.dialog(
    "Edit Sales Order",
    width="large",
    on_dismiss=make_dismiss_handler(SO_EDIT_DIALOG),
)
def _so_edit_dialog(services: dict) -> None:
    order_id = st.session_state.get(SO_EDIT_DIALOG)
    if not order_id:
        return
    sales = services["sales"]
    order = sales.get_sales_order(order_id)
    if not order:
        st.error("Sales order not found")
        return
    business = services["business"].get_profile()
    template = business.document_templates.get("sales_order")
    inventory = services.get("inventory")
    products = inventory.list_products(active_only=True) if inventory else []
    customers = services.get("customers")
    customer = (
        customers.get_customer_detail(order.customer_id) if customers else None
    )
    registered = business_is_registered(business)
    business_state = business.state_code or ""
    customer_state = (customer.state_code if customer else "") or ""
    if customer is None or (
        customer.registration_type != PartyRegistrationType.REGISTERED
        and not (customer.gstin or "").strip()
    ):
        if not customer_state:
            customer_state = business_state

    edit_date = st.date_input(
        "Order date", value=order.order_date, key=f"{SO_EDIT_DIALOG}_date"
    )
    edit_expected = st.date_input(
        "Expected date",
        value=order.expected_date or order.order_date,
        key=f"{SO_EDIT_DIALOG}_expected",
    )
    edit_notes = st.text_area(
        "Notes", value=order.notes, key=f"{SO_EDIT_DIALOG}_notes"
    )
    initial_lines = [
        {
            "product_id": line.product_id,
            "product_name": line.product_name,
            "qty_ordered": line.qty_ordered,
            "rate": line.rate,
        }
        for line in order.lines
    ]
    st.markdown("**Line items**")
    lines, gst_errors = render_sales_lines_editor(
        key_prefix=SO_EDIT_DIALOG,
        products=products,
        initial_lines=initial_lines,
        customer_id=order.customer_id,
        use_customer_pricing=True,
        show_discount=False,
        sales_service=sales,
        inventory_service=inventory,
        business_registered=registered,
        business=business,
        business_state_code=business_state,
        customer_state_code=customer_state,
        qty_field="qty_ordered",
    )
    initial_custom = {
        item.key: item.value for item in order.document_content.custom_fields
    }
    custom_values = render_document_custom_fields(
        template.custom_fields if template else [],
        key_prefix=f"{SO_EDIT_DIALOG}_custom",
        initial_values=initial_custom,
    )
    account_by_id = {
        item.id: item for item in business.bank_accounts if item.is_active
    }
    bank_ids = [""] + list(account_by_id)
    current_bank = getattr(order.document_content.bank_account, "id", "")
    bank_index = bank_ids.index(current_bank) if current_bank in bank_ids else 0
    bank_id = st.selectbox(
        "Bank account on document",
        bank_ids,
        index=bank_index,
        format_func=lambda item_id: (
            "None" if not item_id else account_by_id[item_id].account_name
        ),
        key=f"{SO_EDIT_DIALOG}_bank",
    )
    terms = st.text_area(
        "Terms & Conditions",
        value=order.document_content.terms_and_conditions,
        key=f"{SO_EDIT_DIALOG}_terms",
    )
    if st.button("Update Sales Order", type="primary", key=f"{SO_EDIT_DIALOG}_save"):
        try:
            if gst_errors:
                raise ValueError(gst_errors[0])
            if not lines:
                raise ValueError("Add at least one product line")
            sales.update_sales_order(
                order.id,
                customer_id=order.customer_id,
                order_date=edit_date,
                expected_date=edit_expected,
                lines=lines,
                notes=edit_notes,
                custom_values=custom_values,
                bank_account_id=bank_id,
                terms_and_conditions=terms,
            )
            _clear_prefix(SO_EDIT_DIALOG)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


@st.dialog(
    "Create Sales Invoice",
    width="large",
    on_dismiss=make_dismiss_handler(SO_INVOICE_DIALOG),
)
def _so_invoice_dialog(services: dict) -> None:
    order_id = st.session_state.get(SO_INVOICE_DIALOG)
    if not order_id:
        return
    sales = services["sales"]
    order = sales.get_sales_order(order_id)
    if not order:
        st.error("Sales order not found")
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
        key=f"{SO_INVOICE_DIALOG}_store",
    )
    invoice_number = st.text_input(
        "Store invoice number", key=f"{SO_INVOICE_DIALOG}_number"
    )
    received = st.number_input(
        "Amount received",
        min_value=0.0,
        value=0.0,
        key=f"{SO_INVOICE_DIALOG}_received",
    )
    if st.button("Create invoice", type="primary", key=f"{SO_INVOICE_DIALOG}_save"):
        try:
            if not invoice_number.strip():
                raise ValueError("Store invoice number is required")
            voucher = sales.convert_sales_order_to_invoice(
                order.id,
                store_account_id=store_id,
                store_invoice_number=invoice_number.strip(),
                amount_received=received,
            )
            _clear_prefix(SO_INVOICE_DIALOG)
            navigation.go_to_detail("sales_detail", voucher.id)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def open_so_detail_dialogs_if_armed(services: dict) -> None:
    if st.session_state.get(SO_EDIT_DIALOG):
        _so_edit_dialog(services)
    if st.session_state.get(SO_INVOICE_DIALOG):
        _so_invoice_dialog(services)
