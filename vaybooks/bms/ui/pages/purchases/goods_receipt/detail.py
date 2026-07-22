"""GRN detail."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.domain.shared.enums import CatalogItemType, GoodsReceiptStatus
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.common.document_detail import (
    document_actions,
    document_header,
    format_document_date,
    format_money,
    line_items_table,
    totals_ladder,
)
from vaybooks.bms.ui.components.purchases.purchase_bill_dialog import (
    arm_purchase_bill_dialog,
    open_purchase_bill_dialog_if_armed,
)


def _bill_lines_from_grn(grn) -> list[dict]:
    return [
        {
            "item_type": CatalogItemType.PRODUCT.value,
            "item_id": line.product_id,
            "product_id": line.product_id,
            "qty": line.qty_received,
            "rate": line.rate,
        }
        for line in grn.lines
        if line.product_id and float(line.qty_received or 0) > 0
    ]


def render(services: dict) -> None:
    from vaybooks.bms.ui.keyboard.actions import consume_action
    from vaybooks.bms.ui.keyboard.context import set_current_page
    from vaybooks.bms.ui.keyboard.wired import mark_wired

    set_current_page("grn_detail")
    mark_wired("nav.back")
    grn_id = st.query_params.get("id")
    if not grn_id:
        st.warning("GRN not specified")
        return

    grn = services["purchases"].get_goods_receipt(grn_id)
    if not grn:
        st.warning("Goods receipt not found")
        return

    if st.button("← Back", key="grn_detail_back") or consume_action("nav.back"):
        navigation.go_back_to_list("goods_receipt_list", "goods-receipt")
        return

    right_facts = [
        ("Freight", format_money(grn.freight)),
        ("Duty", format_money(grn.duty)),
        ("Other", format_money(grn.other)),
    ]
    if grn.voucher_id:
        right_facts.append(("Purchase bill", f"`{grn.voucher_id[:8]}…`"))

    document_header(
        number=grn.grn_number,
        status=grn.status.value,
        caption_parts=[
            f"Vendor: {grn.vendor_name}",
            f"PO: {grn.po_number}" if grn.po_number else None,
            "Billed" if grn.voucher_id else None,
        ],
        left_facts=[
            ("Receipt date", format_document_date(grn.receipt_date)),
            ("Vendor", grn.vendor_name or "—"),
        ],
        right_facts=right_facts,
        suffix=f"grn_{grn.id}",
    )

    table_rows = [
        {
            "item_name": line.product_name or line.product_id or "—",
            "product": line.product_name or line.product_id or "—",
            "qty": line.qty_received,
            "rate": line.rate,
            "total": line.line_total,
            "line_total": line.line_total,
            "description": f"Unit cost ₹{line.unit_cost:,.2f}"
            + (
                f" · landed extra ₹{line.landed_cost_extra:,.2f}"
                if line.landed_cost_extra
                else ""
            ),
        }
        for line in grn.lines
    ]
    # Put unit cost into name caption via secondary — keep table clean
    for row, line in zip(table_rows, grn.lines):
        row["item_name"] = (
            f"{line.product_name or line.product_id}"
            f" (unit ₹{line.unit_cost:,.2f})"
        )

    line_items_table(
        table_rows,
        show_gst=False,
        suffix=f"grn_{grn.id}",
        item_column_label="Item",
    )
    lines_total = sum(line.line_total for line in grn.lines)
    totals_ladder(
        show_gst=False,
        grand_total=lines_total + grn.freight + grn.duty + grn.other,
        extra_rows=[
            ("Lines", lines_total),
            ("Freight", grn.freight),
            ("Duty", grn.duty),
            ("Other", grn.other),
        ],
        suffix=f"grn_{grn.id}",
    )

    actions = []
    can_bill = (
        grn.status == GoodsReceiptStatus.RECEIVED
        and not grn.voucher_id
        and bool(_bill_lines_from_grn(grn))
    )
    if can_bill:
        actions.append(
            {"label": "Create Purchase Bill", "key": "grn_create_bill", "type": "primary"}
        )
    if grn.voucher_id:
        actions.append({"label": "View bill", "key": "grn_view_bill"})

    clicked = document_actions(actions, suffix=f"grn_{grn.id}")
    if clicked.get("grn_create_bill"):
        prefill = {
            "vendor_id": grn.vendor_id,
            "reference_grn_id": grn.id,
            "lines": _bill_lines_from_grn(grn),
            "apply_stock": False,
        }
        if grn.purchase_order_id:
            prefill["reference_po_id"] = grn.purchase_order_id
        arm_purchase_bill_dialog(**prefill)
        st.rerun()
    if clicked.get("grn_view_bill") and grn.voucher_id:
        navigation.go_to_detail("purchase_detail", grn.voucher_id)
        st.rerun()

    open_purchase_bill_dialog_if_armed(services)
