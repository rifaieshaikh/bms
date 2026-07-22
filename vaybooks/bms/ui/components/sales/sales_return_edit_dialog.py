"""Edit dialog for draft and pending sales returns."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.domain.sales.sales_line_resolver import business_is_registered
from vaybooks.bms.domain.shared.enums import (
    PartyRegistrationType,
    SalesReturnStatus,
)
from vaybooks.bms.ui.components.common.customer_identity_selector import (
    render_customer_identity_selector,
    resolve_customer_identity,
)
from vaybooks.bms.ui.components.sales.sales_lines_editor import render_sales_lines_editor
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler

SALES_RETURN_EDIT_DIALOG = "sales_return_edit_dialog"


def arm_sales_return_edit_dialog(return_id: str) -> None:
    for key in list(st.session_state):
        if key == SALES_RETURN_EDIT_DIALOG or key.startswith(
            f"{SALES_RETURN_EDIT_DIALOG}_"
        ):
            st.session_state.pop(key, None)
    st.session_state[SALES_RETURN_EDIT_DIALOG] = return_id


def _clear() -> None:
    for key in list(st.session_state):
        if key == SALES_RETURN_EDIT_DIALOG or key.startswith(
            f"{SALES_RETURN_EDIT_DIALOG}_"
        ):
            st.session_state.pop(key, None)


@st.dialog(
    "Edit Sales Return",
    width="large",
    on_dismiss=make_dismiss_handler(SALES_RETURN_EDIT_DIALOG),
)
def _edit_dialog(services: dict) -> None:
    return_id = st.session_state.get(SALES_RETURN_EDIT_DIALOG)
    sales = services["sales"]
    sales_return = sales.get_sales_return(return_id)
    if not sales_return:
        st.error("Sales return not found")
        return

    customers = services["customers"]
    customer = customers.get_customer_detail(sales_return.customer_id)
    source_invoice = (
        sales.get_sales_invoice(sales_return.source_invoice_id)
        if sales_return.source_invoice_id
        else None
    )
    source_invoice_number = (
        sales_return.source_invoice_number
        or (source_invoice or {}).get("store_invoice_number")
        or (source_invoice or {}).get("voucher_number")
        or "No linked invoice"
    )
    st.text_input(
        "Return number",
        value=sales_return.return_number,
        disabled=True,
        key=f"{SALES_RETURN_EDIT_DIALOG}_number",
    )

    if sales_return.status != SalesReturnStatus.PENDING:
        st.warning("Only pending returns can be edited.")
        return

    selection = render_customer_identity_selector(
        customers,
        key_prefix=SALES_RETURN_EDIT_DIALOG,
        initial_customer=customer,
    )
    edit_date = st.date_input(
        "Return date",
        value=sales_return.return_date,
        key=f"{SALES_RETURN_EDIT_DIALOG}_date",
    )
    st.text_input(
        "Original invoice",
        value=source_invoice_number,
        disabled=True,
        key=f"{SALES_RETURN_EDIT_DIALOG}_invoice",
    )

    inventory = services.get("inventory")
    products = inventory.list_products(active_only=True) if inventory else []
    business_service = services.get("business")
    business = business_service.get_profile() if business_service else None
    selected_customer = selection.customer
    business_state = business.state_code if business else ""
    customer_state = (
        selected_customer.state_code if selected_customer else ""
    ) or ""
    if selected_customer is None or (
        selected_customer.registration_type != PartyRegistrationType.REGISTERED
        and not (selected_customer.gstin or "").strip()
    ):
        customer_state = customer_state or business_state
    initial_lines = [
        {
            "product_id": line.product_id,
            "product_name": line.product_name,
            "qty": line.qty,
            "rate": line.rate,
        }
        for line in sales_return.lines
    ]
    st.markdown("**Product details**")
    lines, gst_errors = render_sales_lines_editor(
        key_prefix=SALES_RETURN_EDIT_DIALOG,
        products=products,
        initial_lines=initial_lines,
        customer_id=selected_customer.id if selected_customer else None,
        use_customer_pricing=True,
        show_discount=False,
        sales_service=sales,
        inventory_service=inventory,
        business_registered=business_is_registered(business),
        business=business,
        business_state_code=business_state,
        customer_state_code=customer_state,
        qty_field="qty",
    )
    reason = st.text_input(
        "Return reason",
        value=sales_return.return_reason,
        key=f"{SALES_RETURN_EDIT_DIALOG}_reason",
    )
    notes = st.text_area(
        "Notes",
        value=sales_return.notes,
        key=f"{SALES_RETURN_EDIT_DIALOG}_notes",
    )
    if sales_return.attachments:
        st.caption(
            "Current attachments: "
            + ", ".join(item.get("name", "Document") for item in sales_return.attachments)
        )
    uploads = st.file_uploader(
        "Add document attachments",
        accept_multiple_files=True,
        key=f"{SALES_RETURN_EDIT_DIALOG}_attachments",
    )
    restock_items = st.checkbox(
        "Restock goods when received",
        value=sales_return.restock_items,
        key=f"{SALES_RETURN_EDIT_DIALOG}_restock",
    )

    options = ["Customer credit", "Cash / bank refund"]
    option_index = (
        options.index(sales_return.refund_option)
        if sales_return.refund_option in options
        else 0
    )
    refund_option = st.selectbox(
        "Refund option",
        options,
        index=option_index,
        key=f"{SALES_RETURN_EDIT_DIALOG}_refund_option",
    )
    refund = 0.0
    refund_account_id = None
    if refund_option == "Cash / bank refund":
        refund = st.number_input(
            "Refund amount",
            min_value=0.0,
            value=float(sales_return.amount_refunded or 0),
            key=f"{SALES_RETURN_EDIT_DIALOG}_refund",
        )
        accounts = services["accounting"].get_store_accounts()
        account_by_id = {account.id: account for account in accounts}
        account_ids = list(account_by_id)
        if not account_ids:
            st.error("No cash/bank account found for refund.")
            return
        account_index = (
            account_ids.index(sales_return.refund_account_id)
            if sales_return.refund_account_id in account_ids
            else 0
        )
        refund_account_id = st.selectbox(
            "Refund account",
            account_ids,
            index=account_index,
            format_func=lambda account_id: account_by_id[account_id].account_name,
            key=f"{SALES_RETURN_EDIT_DIALOG}_refund_account",
        )

    if st.button(
        "Update Sales Return",
        type="primary",
        key=f"{SALES_RETURN_EDIT_DIALOG}_save",
    ):
        try:
            if gst_errors:
                raise ValueError(gst_errors[0])
            if not lines:
                raise ValueError("Add at least one return line")
            if not reason.strip():
                raise ValueError("Return reason is required")
            resolved_customer = resolve_customer_identity(customers, selection)
            attachments = list(sales_return.attachments)
            for uploaded in uploads or []:
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
            sales.update_sales_return(
                sales_return.id,
                customer_id=resolved_customer.id,
                return_date=edit_date,
                lines=lines,
                source_invoice_id=sales_return.source_invoice_id,
                notes=notes,
                return_reason=reason,
                refund_option=refund_option,
                amount_refunded=refund,
                refund_account_id=refund_account_id,
                restock_items=restock_items,
                attachments=attachments,
            )
            _clear()
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def open_sales_return_edit_dialog_if_armed(services: dict) -> None:
    if st.session_state.get(SALES_RETURN_EDIT_DIALOG):
        _edit_dialog(services)
