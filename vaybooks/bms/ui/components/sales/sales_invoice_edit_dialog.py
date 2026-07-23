"""Edit dialog for sales invoices with calendar-month lock gating."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.domain.sales.line_items import parse_sales_document_content
from vaybooks.bms.domain.sales.sales_line_resolver import business_is_registered
from vaybooks.bms.domain.shared.enums import PartyRegistrationType
from vaybooks.bms.ui.components.common.document_custom_fields import (
    render_document_custom_fields,
)
from vaybooks.bms.ui.components.sales.sales_lines_entry_table import (
    entry_table_focus_chain,
    entry_table_focus_columns,
    entry_table_grid_roles,
    render_sales_lines_entry_table,
)
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler, register_armed_dialog
from vaybooks.bms.ui.keyboard.dialog_actions import consume_submit, open_dialog
from vaybooks.bms.ui.keyboard.focus.registry import get_strategy
from vaybooks.bms.ui.keyboard.wired import mark_wired

INVOICE_EDIT_DIALOG = "invoice_edit_dialog"
INVOICE_EDIT_FOCUS_STRATEGY = "sales_invoice_edit_dialog"
INVOICE_EDIT_SUBMIT_KEY = "invoice_edit_dialog_submit"
INVOICE_EDIT_FOCUS_KEY = f"{INVOICE_EDIT_DIALOG}_focus"


def arm_invoice_edit_dialog(voucher_id: str) -> None:
    open_dialog(
        INVOICE_EDIT_DIALOG,
        submit_key=INVOICE_EDIT_SUBMIT_KEY,
        value=voucher_id,
        clear_others=True,
    )
    st.session_state[INVOICE_EDIT_FOCUS_KEY] = f"{INVOICE_EDIT_DIALOG}_date"
    mark_wired("dialog.save")


def _clear() -> None:
    for key in list(st.session_state.keys()):
        if key == INVOICE_EDIT_DIALOG or key.startswith(f"{INVOICE_EDIT_DIALOG}_"):
            st.session_state.pop(key, None)
    st.session_state.pop(INVOICE_EDIT_SUBMIT_KEY, None)


@st.dialog(
    "Edit invoice",
    width="large",
    on_dismiss=make_dismiss_handler(INVOICE_EDIT_DIALOG),
)
def _invoice_edit_dialog(
    services: dict,
    *,
    row: dict,
    parsed: dict,
    line_items: list,
    customer_account_id: str,
    invoice_discount: float,
) -> None:
    voucher_id = st.session_state.get(INVOICE_EDIT_DIALOG)
    if not voucher_id:
        return
    register_armed_dialog(INVOICE_EDIT_DIALOG)
    mark_wired("dialog.save")

    accounting = services["accounting"]
    sales = services["sales"]
    business_service = services.get("business")
    business = business_service.get_profile() if business_service else None
    template = (
        business.document_templates.get("sales_invoice") if business else None
    )
    inventory = services.get("inventory")
    products = inventory.list_products(active_only=True) if inventory else []
    customers = services.get("customers")
    customer = None
    linked = accounting.get_account(customer_account_id)
    if customers and linked and linked.linked_customer_id:
        customer = customers.get_customer_detail(linked.linked_customer_id)

    registered = business_is_registered(business)
    business_state = business.state_code if business else ""
    customer_state = (customer.state_code if customer else "") or ""
    if customer is None or (
        customer.registration_type != PartyRegistrationType.REGISTERED
        and not (customer.gstin or "").strip()
    ):
        if not customer_state:
            customer_state = business_state

    store_accounts = accounting.get_store_accounts()
    store_by_id = {item.id: item for item in store_accounts}
    current_store = parsed.get("store_id")
    store_ids = list(store_by_id)
    if not store_ids:
        st.error("Need at least one cash/bank store account.")
        return
    store_index = store_ids.index(current_store) if current_store in store_ids else 0
    edit_store_id = st.selectbox(
        "Cash / Bank account",
        store_ids,
        index=store_index,
        format_func=lambda item_id: store_by_id[item_id].account_name,
        key=f"{INVOICE_EDIT_DIALOG}_store",
    )
    edit_number = st.text_input(
        "Store invoice number",
        value=row.get("store_invoice_number") or "",
        key=f"{INVOICE_EDIT_DIALOG}_number",
    )
    edit_date = st.date_input(
        "Invoice date",
        value=row.get("sale_date"),
        key=f"{INVOICE_EDIT_DIALOG}_date",
    )
    initial_lines = [
        {
            "product_id": item.get("product_id"),
            "product_name": item.get("product_name") or item.get("description") or "",
            "qty": float(item.get("qty") or 0),
            "rate": float(item.get("rate") or 0),
            "discount": float(item.get("discount") or 0),
        }
        for item in line_items
    ]
    updated_items, gst_errors = render_sales_lines_entry_table(
        key_prefix=INVOICE_EDIT_DIALOG,
        products=products,
        initial_lines=initial_lines,
        customer_id=customer.id if customer else None,
        use_customer_pricing=True,
        show_discount=True,
        sales_service=sales,
        inventory_service=inventory,
        business_registered=registered,
        business=business,
        business_state_code=business_state or "",
        customer_state_code=customer_state or "",
        qty_field="qty",
        focus_restore_key=INVOICE_EDIT_FOCUS_KEY,
    )
    edit_received = st.number_input(
        "Amount received",
        min_value=0.0,
        value=float(row.get("collected") or 0),
        key=f"{INVOICE_EDIT_DIALOG}_received",
    )
    voucher = accounting.get_voucher(voucher_id)
    current_content = parse_sales_document_content(
        voucher.description if voucher else ""
    )
    initial_custom = {
        item.get("key"): item.get("value")
        for item in current_content.get("custom_fields", [])
    }
    definitions = template.custom_fields if business and template else []
    custom_values = render_document_custom_fields(
        definitions,
        key_prefix=f"{INVOICE_EDIT_DIALOG}_custom",
        initial_values=initial_custom,
    )
    active_accounts = (
        [item for item in business.bank_accounts if item.is_active]
        if business
        else []
    )
    account_by_id = {item.id: item for item in active_accounts}
    bank_ids = [""] + list(account_by_id)
    current_bank = (current_content.get("bank_account") or {}).get("id", "")
    bank_index = bank_ids.index(current_bank) if current_bank in bank_ids else 0
    edit_bank = st.selectbox(
        "Bank account on invoice",
        bank_ids,
        index=bank_index,
        format_func=lambda item_id: (
            "None" if not item_id else account_by_id[item_id].account_name
        ),
        key=f"{INVOICE_EDIT_DIALOG}_bank",
    )
    edit_terms = st.text_area(
        "Terms & Conditions",
        value=current_content.get("terms_and_conditions", ""),
        key=f"{INVOICE_EDIT_DIALOG}_terms",
    )
    if st.button("Update invoice", type="primary", key=f"{INVOICE_EDIT_DIALOG}_save") or consume_submit(
        INVOICE_EDIT_SUBMIT_KEY
    ):
        try:
            if gst_errors:
                raise ValueError(gst_errors[0])
            if not updated_items:
                raise ValueError("Add at least one product line")
            sales.update_sales_invoice(
                voucher_id,
                customer_account_id=customer_account_id,
                store_account_id=edit_store_id,
                store_invoice_number=edit_number,
                line_items=updated_items,
                amount_received=edit_received,
                voucher_date=edit_date,
                invoice_discount=invoice_discount,
                custom_values=custom_values,
                bank_account_id=edit_bank,
                terms_and_conditions=edit_terms,
            )
            _clear()
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    row_chain = entry_table_focus_chain(INVOICE_EDIT_DIALOG)
    row_columns = entry_table_focus_columns(INVOICE_EDIT_DIALOG)
    grid_roles = entry_table_grid_roles(INVOICE_EDIT_DIALOG)
    date_key = f"{INVOICE_EDIT_DIALOG}_date"
    save_key = f"{INVOICE_EDIT_DIALOG}_save"
    restore = st.session_state.pop(INVOICE_EDIT_FOCUS_KEY, None)
    get_strategy(INVOICE_EDIT_FOCUS_STRATEGY).inject(
        chain=[date_key, *row_chain, f"{INVOICE_EDIT_DIALOG}_received", save_key],
        restore_key=restore,
        columns=row_columns,
        above_first=date_key,
        below_last=save_key,
        grid_roles=grid_roles,
        component_key=f"inv_edit_entry_{len(row_chain)}",
    )


def open_invoice_edit_dialog_if_armed(
    services: dict,
    *,
    row: dict,
    parsed: dict,
    line_items: list,
    customer_account_id: str,
    invoice_discount: float,
) -> None:
    if st.session_state.get(INVOICE_EDIT_DIALOG):
        _invoice_edit_dialog(
            services,
            row=row,
            parsed=parsed,
            line_items=line_items,
            customer_account_id=customer_account_id,
            invoice_discount=invoice_discount,
        )
