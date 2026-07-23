"""Sales return dialog."""

from __future__ import annotations

from datetime import date

import streamlit as st

from vaybooks.bms.domain.sales.line_items import parse_sales_line_items_note
from vaybooks.bms.domain.sales.sales_line_resolver import business_is_registered
from vaybooks.bms.domain.shared.enums import (
    PartyRegistrationType,
    SalesReturnStatus,
)
from vaybooks.bms.ui.components.common.customer_identity_selector import (
    render_customer_identity_selector,
    resolve_customer_identity,
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

SALES_RETURN_DIALOG = "sales_return_dialog"
SALES_RETURN_SUBMIT_KEY = "sales_return_dialog_submit"
SALES_RETURN_FOCUS_KEY = f"{SALES_RETURN_DIALOG}_focus"


def arm_sales_return_dialog(source_invoice_id: str | None = None) -> None:
    for key in list(st.session_state.keys()):
        if key.startswith(SALES_RETURN_DIALOG):
            st.session_state.pop(key, None)
    open_dialog(
        SALES_RETURN_DIALOG,
        submit_key=SALES_RETURN_SUBMIT_KEY,
        value="new",
        clear_others=True,
    )
    st.session_state[SALES_RETURN_FOCUS_KEY] = f"{SALES_RETURN_DIALOG}_customer_name"
    if source_invoice_id:
        st.session_state[f"{SALES_RETURN_DIALOG}_invoice_id"] = source_invoice_id
    mark_wired("dialog.save")


def _clear() -> None:
    for key in list(st.session_state.keys()):
        if key.startswith(SALES_RETURN_DIALOG):
            st.session_state.pop(key, None)
    st.session_state.pop(SALES_RETURN_SUBMIT_KEY, None)


@st.dialog("Record Sales Return", width="large", on_dismiss=make_dismiss_handler(SALES_RETURN_DIALOG))
def sales_return_dialog(services: dict) -> None:
    if st.session_state.get(SALES_RETURN_DIALOG) != "new":
        return

    register_armed_dialog(SALES_RETURN_DIALOG)
    mark_wired("dialog.save")

    sales = services["sales"]
    accounting = services["accounting"]
    customers = services["customers"]
    inventory = services.get("inventory")
    business_service = services.get("business")
    business = business_service.get_profile() if business_service else None

    reserved_number_key = f"{SALES_RETURN_DIALOG}_reserved_number"
    if reserved_number_key not in st.session_state:
        try:
            st.session_state[reserved_number_key] = (
                sales.reserve_sales_return_number()
            )
        except Exception as exc:
            st.error(f"Could not generate return number: {exc}")
            return
    return_number = st.session_state[reserved_number_key]
    st.text_input(
        "Return number",
        value=return_number,
        disabled=True,
        key=f"{SALES_RETURN_DIALOG}_number",
    )
    customer_selection = render_customer_identity_selector(
        customers, key_prefix=SALES_RETURN_DIALOG
    )
    matched_customer = customer_selection.customer

    return_date = st.date_input(
        "Return date", value=date.today(), key=f"{SALES_RETURN_DIALOG}_date"
    )
    returned_invoice_ids = {
        item.source_invoice_id
        for item in sales.list_sales_returns()
        if (
            item.source_invoice_id
            and item.status != SalesReturnStatus.REJECTED
        )
    }
    invoices = [
        row
        for row in sales.list_sales_invoices()
        if row.get("id") not in returned_invoice_ids
    ]
    if matched_customer:
        def _belongs_to_customer(row: dict) -> bool:
            account = accounting.get_account(row.get("customer_account_id"))
            return bool(
                account and account.linked_customer_id == matched_customer.id
            )

        invoices = [
            row
            for row in invoices
            if _belongs_to_customer(row)
        ]
    invoice_by_label = {
        (
            f"{row.get('store_invoice_number') or row.get('voucher_number')} — "
            f"{row.get('sale_date')} — ₹{float(row.get('net') or 0):,.2f}"
        ): row
        for row in invoices
    }
    invoice_labels = ["No linked invoice"] + list(invoice_by_label)
    source_key = f"{SALES_RETURN_DIALOG}_invoice_label"
    preset_id = st.session_state.get(f"{SALES_RETURN_DIALOG}_invoice_id")
    default_index = 0
    if preset_id:
        for index, label in enumerate(invoice_labels):
            if invoice_by_label.get(label, {}).get("id") == preset_id:
                default_index = index
                break

    def _invoice_changed() -> None:
        st.session_state.pop(f"{SALES_RETURN_DIALOG}_rows", None)
        for key in list(st.session_state.keys()):
            if key.startswith(f"{SALES_RETURN_DIALOG}_r"):
                st.session_state.pop(key, None)

    invoice_label = st.selectbox(
        "Original invoice number",
        invoice_labels,
        index=default_index,
        key=source_key,
        on_change=_invoice_changed,
    )
    selected_invoice = invoice_by_label.get(invoice_label)
    source_invoice_id = selected_invoice.get("id") if selected_invoice else None
    initial_lines: list[dict] = []
    if source_invoice_id:
        voucher = accounting.get_voucher(source_invoice_id)
        parsed_lines, _, _ = parse_sales_line_items_note(
            voucher.description if voucher else ""
        )
        initial_lines = [
            {
                "product_id": item.get("product_id"),
                "product_name": item.get("product_name")
                or item.get("description")
                or "",
                "qty": float(item.get("qty") or 0),
                "rate": float(item.get("rate") or 0),
            }
            for item in parsed_lines
        ]

    products = inventory.list_products(active_only=True) if inventory else []
    customer_state = (matched_customer.state_code if matched_customer else "") or ""
    business_state = business.state_code if business else ""
    if matched_customer is None or (
        matched_customer.registration_type != PartyRegistrationType.REGISTERED
        and not (matched_customer.gstin or "").strip()
    ):
        customer_state = customer_state or business_state
    line_items, gst_errors = render_sales_lines_entry_table(
        key_prefix=SALES_RETURN_DIALOG,
        products=products,
        initial_lines=initial_lines,
        customer_id=matched_customer.id if matched_customer else None,
        use_customer_pricing=True,
        show_discount=False,
        sales_service=sales,
        inventory_service=inventory,
        business_registered=business_is_registered(business),
        business=business,
        business_state_code=business_state,
        customer_state_code=customer_state,
        qty_field="qty",
        focus_restore_key=SALES_RETURN_FOCUS_KEY,
    )

    return_reason = st.text_input(
        "Return reason", key=f"{SALES_RETURN_DIALOG}_reason"
    )
    notes = st.text_area("Notes", key=f"{SALES_RETURN_DIALOG}_notes")
    uploaded_files = st.file_uploader(
        "Document attachments",
        accept_multiple_files=True,
        key=f"{SALES_RETURN_DIALOG}_attachments",
    )
    restock_items = st.checkbox(
        "Restock goods when received",
        value=True,
        key=f"{SALES_RETURN_DIALOG}_restock",
    )

    refund_option = st.selectbox(
        "Refund option",
        ["Customer credit", "Cash / bank refund"],
        key=f"{SALES_RETURN_DIALOG}_refund_option",
    )
    refund = 0.0
    refund_acct = None
    if refund_option == "Cash / bank refund":
        refund = st.number_input(
            "Refund amount",
            min_value=0.0,
            value=0.0,
            key=f"{SALES_RETURN_DIALOG}_refund",
        )
        store_accounts = accounting.get_store_accounts()
        if not store_accounts:
            st.error("No cash/bank account found for refund.")
            return
        account_by_id = {account.id: account for account in store_accounts}
        refund_acct = st.selectbox(
            "Refund account",
            list(account_by_id),
            format_func=lambda account_id: account_by_id[account_id].account_name,
            key=f"{SALES_RETURN_DIALOG}_refund_acct",
        )

    save_key = f"{SALES_RETURN_DIALOG}_save"
    submit_clicked = st.button(
        "Submit for approval", type="primary", use_container_width=True, key=save_key
    ) or consume_submit(SALES_RETURN_SUBMIT_KEY)

    row_chain = entry_table_focus_chain(SALES_RETURN_DIALOG)
    row_columns = entry_table_focus_columns(SALES_RETURN_DIALOG)
    grid_roles = entry_table_grid_roles(SALES_RETURN_DIALOG)
    date_key = f"{SALES_RETURN_DIALOG}_date"
    restore = st.session_state.pop(SALES_RETURN_FOCUS_KEY, None)
    get_strategy(SALES_RETURN_DIALOG).inject(
        chain=[
            f"{SALES_RETURN_DIALOG}_customer_name",
            date_key,
            *row_chain,
            f"{SALES_RETURN_DIALOG}_reason",
            save_key,
        ],
        restore_key=restore,
        columns=row_columns,
        above_first=date_key,
        below_last=save_key,
        grid_roles=grid_roles,
        component_key=f"sales_ret_entry_{len(row_chain)}",
    )

    if submit_clicked:
        try:
            if gst_errors:
                raise ValueError(gst_errors[0])
            if not line_items:
                raise ValueError("Add at least one return line")
            if not return_reason.strip():
                raise ValueError("Return reason is required")
            customer = resolve_customer_identity(customers, customer_selection)
            attachments = []
            for uploaded in uploaded_files or []:
                data = uploaded.getvalue()
                if len(data) > 10 * 1024 * 1024:
                    raise ValueError(f"{uploaded.name} exceeds the 10 MB limit")
                attachments.append(
                    {
                        "name": uploaded.name,
                        "content_type": uploaded.type or "application/octet-stream",
                        "data": data,
                    }
                )
            sales.create_sales_return(
                customer_id=customer.id,
                return_date=return_date,
                lines=line_items,
                return_number=return_number,
                source_invoice_id=source_invoice_id,
                amount_refunded=refund,
                refund_account_id=refund_acct,
                notes=notes,
                return_reason=return_reason,
                refund_option=refund_option,
                restock_items=restock_items,
                attachments=attachments,
            )
            _clear()
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def open_sales_return_dialog_if_armed(services: dict) -> None:
    if st.session_state.get(SALES_RETURN_DIALOG) == "new":
        sales_return_dialog(services)
