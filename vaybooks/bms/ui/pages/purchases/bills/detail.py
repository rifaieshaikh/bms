"""Purchase bill detail with edit/delete/return."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.domain.shared.enums import VoucherType
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.common.document_detail import (
    document_actions,
    document_header,
    format_document_date,
    format_money,
    line_items_table,
    totals_ladder,
)
from vaybooks.bms.ui.components.purchases.purchase_bill_edit_dialog import (
    arm_purchase_bill_edit_dialog,
    open_purchase_bill_edit_dialog_if_armed,
)
from vaybooks.bms.ui.components.purchases.purchase_return_dialog import (
    arm_return_dialog,
    open_return_dialog_if_armed,
)
from vaybooks.bms.ui.purchase_display import purchase_line_table_row


def render(services: dict) -> None:
    from vaybooks.bms.ui.keyboard.actions import consume_action
    from vaybooks.bms.ui.keyboard.context import set_current_page
    from vaybooks.bms.ui.keyboard.wired import mark_wired

    set_current_page("purchase_detail")
    mark_wired("nav.back")
    bill_id = st.query_params.get("id")
    if not bill_id:
        st.warning("Purchase bill not specified")
        return

    purchases = services["purchases"]
    accounting = services["accounting"]
    inventory = services.get("inventory")
    vendor_services = services.get("vendor_services")
    row = purchases.get_purchase_bill(bill_id)
    voucher = accounting.get_voucher(bill_id)
    if not row or not voucher:
        st.warning("Purchase bill not found")
        return

    if st.button("← Back", key="purchase_detail_back") or consume_action("nav.back"):
        navigation.go_back_to_list("purchases_list", "purchases")
        return

    product_by_id = {}
    service_by_id = {}
    if inventory:
        product_by_id = {p.id: p for p in inventory.list_products(active_only=False)}
    if vendor_services:
        service_by_id = {
            s.id: s for s in vendor_services.list_services(active_only=False)
        }

    document_header(
        number=row.get("vendor_bill_number") or voucher.voucher_number,
        status=row.get("voucher_type"),
        caption_parts=[
            f"Vendor: {row.get('vendor_name') or '—'}",
            f"Voucher: {voucher.voucher_number}",
        ],
        left_facts=[
            ("Date", format_document_date(row.get("bill_date"))),
            ("Vendor", row.get("vendor_name") or "—"),
        ],
        right_facts=[
            ("Total", format_money(row.get("total"))),
            ("Paid", format_money(row.get("paid"))),
            ("Outstanding", format_money(row.get("outstanding"))),
        ],
        suffix=f"bill_{bill_id}",
    )

    table_rows = [
        purchase_line_table_row(
            item, product_by_id=product_by_id, service_by_id=service_by_id
        )
        for item in (row.get("line_items") or [])
    ]
    taxable = round(sum(float(r.get("taxable_amount") or 0) for r in table_rows), 2)
    cgst = round(sum(float(r.get("cgst_amount") or 0) for r in table_rows), 2)
    sgst = round(sum(float(r.get("sgst_amount") or 0) for r in table_rows), 2)
    igst = round(sum(float(r.get("igst_amount") or 0) for r in table_rows), 2)
    utgst = round(sum(float(r.get("utgst_amount") or 0) for r in table_rows), 2)
    tax = round(cgst + sgst + igst + utgst, 2)
    line_items_table(
        table_rows,
        show_gst=tax > 0,
        suffix=f"bill_{bill_id}",
        item_column_label="Item",
    )
    totals_ladder(
        {
            "taxable": taxable,
            "cgst": cgst,
            "sgst": sgst,
            "igst": igst,
            "utgst": utgst,
            "total_tax": tax,
            "grand_total": float(row.get("total") or 0),
        },
        show_gst=tax > 0,
        grand_total=float(row.get("total") or 0),
        extra_rows=[
            ("Paid", float(row.get("paid") or 0)),
            ("Outstanding", float(row.get("outstanding") or 0)),
        ],
        suffix=f"bill_{bill_id}",
    )

    actions = []
    if voucher.voucher_type == VoucherType.PURCHASE_BILL:
        actions.append({"label": "Edit", "key": "bill_edit", "type": "primary"})
        actions.append({"label": "Record return", "key": "bill_return"})
        actions.append({"label": "Delete bill", "key": "bill_delete"})
    clicked = document_actions(actions, suffix=f"bill_{bill_id}")
    if clicked.get("bill_edit"):
        arm_purchase_bill_edit_dialog(bill_id)
        st.rerun()
    if clicked.get("bill_return"):
        arm_return_dialog(source_bill_id=bill_id)
        st.rerun()
    if clicked.get("bill_delete"):
        try:
            purchases.delete_purchase_bill(bill_id)
            navigation.go_back_to_list("purchases_list", "purchases")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    open_purchase_bill_edit_dialog_if_armed(services)
    open_return_dialog_if_armed(services)
