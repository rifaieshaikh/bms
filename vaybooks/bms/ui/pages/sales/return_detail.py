"""Sales return detail and approval actions."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.domain.shared.enums import SalesReturnStatus
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.document_detail import (
    document_actions,
    format_document_date,
    line_items_table,
    sales_line_row_from_entity,
    secondary_sections,
    totals_ladder,
)
from vaybooks.bms.ui.components.sales_return_edit_dialog import (
    arm_sales_return_edit_dialog,
    open_sales_return_edit_dialog_if_armed,
)


def render(services: dict) -> None:
    return_id = navigation.current_detail_id("sales_return_detail")
    if not return_id:
        st.warning("Sales return not specified")
        return
    sales = services["sales"]
    sales_return = sales.get_sales_return(return_id)
    if not sales_return:
        st.warning("Sales return not found")
        return

    if st.button("← Back", key="sales_return_detail_back"):
        navigation.go_back_to_list("sales_returns", "sales_returns_list")
        return

    customer_service = services.get("customers")
    customer = (
        customer_service.get_customer_detail(sales_return.customer_id)
        if customer_service
        else None
    )
    invoice_number = sales_return.source_invoice_number or ""
    if sales_return.source_invoice_id:
        invoice = sales.get_sales_invoice(sales_return.source_invoice_id)
        if invoice:
            invoice_number = invoice_number or (
                invoice.get("store_invoice_number")
                or invoice.get("voucher_number")
                or sales_return.source_invoice_id
            )

    st.subheader("Sales Return")
    number_col, status_col = st.columns(2)
    number_col.text_input(
        "Return number",
        value=sales_return.return_number,
        disabled=True,
        key=f"return_view_number_{sales_return.id}",
    )
    # Include status in the widget key so Streamlit does not keep a stale
    # session value after Approve / Reject / Close transitions.
    status_col.text_input(
        "Status",
        value=sales_return.status.value,
        disabled=True,
        key=f"return_view_status_{sales_return.id}_{sales_return.status.value}",
    )
    customer_col, phone_col = st.columns(2)
    customer_col.text_input(
        "Customer name",
        value=sales_return.customer_name,
        disabled=True,
        key=f"return_view_customer_{sales_return.id}",
    )
    phone_col.text_input(
        "Phone number",
        value=(customer.phone_number if customer else "") or "—",
        disabled=True,
        key=f"return_view_phone_{sales_return.id}",
    )
    date_col, invoice_col = st.columns(2)
    date_col.text_input(
        "Return date",
        value=format_document_date(sales_return.return_date),
        disabled=True,
        key=f"return_view_date_{sales_return.id}",
    )
    invoice_col.text_input(
        "Original invoice number",
        value=invoice_number or "Not linked",
        disabled=True,
        key=f"return_view_invoice_{sales_return.id}",
    )
    reason_col, refund_col = st.columns(2)
    reason_col.text_input(
        "Return reason",
        value=sales_return.return_reason or "—",
        disabled=True,
        key=f"return_view_reason_{sales_return.id}",
    )
    refund_col.text_input(
        "Refund option",
        value=sales_return.refund_option,
        disabled=True,
        key=f"return_view_refund_{sales_return.id}",
    )
    st.text_input(
        "Inventory handling",
        value=(
            "Restock when goods are received"
            if sales_return.restock_items
            else "Do not restock"
        ),
        disabled=True,
        key=f"return_view_restock_{sales_return.id}",
    )

    actions = []
    if sales_return.status == SalesReturnStatus.PENDING:
        actions.extend(
            [
                {"label": "Edit", "key": "edit"},
                {"label": "Approve", "key": "approve", "type": "primary"},
                {"label": "Reject", "key": "reject"},
            ]
        )
    elif sales_return.status == SalesReturnStatus.APPROVED:
        actions.append(
            {
                "label": "Mark Goods Received",
                "key": "goods_received",
                "type": "primary",
            }
        )
    elif sales_return.status == SalesReturnStatus.GOODS_RECEIVED:
        actions.append(
            {
                "label": "Process Refund",
                "key": "process_refund",
                "type": "primary",
            }
        )
    elif sales_return.status == SalesReturnStatus.REFUND_PROCESSED:
        actions.append({"label": "Close", "key": "close", "type": "primary"})
    clicked = document_actions(actions, suffix=f"sales_return_{sales_return.id}")
    if clicked.get("edit"):
        arm_sales_return_edit_dialog(sales_return.id)
        st.rerun()
    if clicked.get("approve"):
        try:
            sales.approve_sales_return(sales_return.id)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if clicked.get("reject"):
        try:
            sales.reject_sales_return(sales_return.id)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if clicked.get("goods_received"):
        try:
            sales.mark_sales_return_goods_received(sales_return.id)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if clicked.get("process_refund"):
        try:
            sales.process_sales_return_refund(sales_return.id)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if clicked.get("close"):
        try:
            sales.close_sales_return(sales_return.id)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    inventory = services.get("inventory")
    line_items_table(
        [
            sales_line_row_from_entity(line, inventory=inventory)
            for line in sales_return.lines
        ],
        show_gst=False,
        suffix=f"sales_return_{sales_return.id}",
    )
    extras = []
    if sales_return.amount_refunded:
        extras.append(("Cash / bank refund", sales_return.amount_refunded))
    totals_ladder(
        show_gst=False,
        grand_total=sales_return.total_amount,
        extra_rows=extras,
        suffix=f"sales_return_{sales_return.id}",
    )

    secondary_sections(notes=sales_return.notes)
    if sales_return.attachments:
        st.subheader("Attachments")
        for index, attachment in enumerate(sales_return.attachments):
            st.download_button(
                attachment.get("name") or f"Attachment {index + 1}",
                data=attachment.get("data") or b"",
                file_name=attachment.get("name") or f"attachment-{index + 1}",
                mime=attachment.get("content_type") or "application/octet-stream",
                key=f"return_attachment_{sales_return.id}_{index}",
            )

    open_sales_return_edit_dialog_if_armed(services)
