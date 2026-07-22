"""Purchase order detail."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.domain.shared.enums import PurchaseOrderStatus
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.common.document_detail import (
    document_actions,
    document_header,
    format_document_date,
    format_money,
    line_items_table,
    totals_ladder,
)
from vaybooks.bms.ui.components.purchases.grn_dialog import arm_grn_dialog, open_grn_dialog_if_armed
from vaybooks.bms.ui.components.purchases.purchase_order_edit_dialog import (
    arm_po_edit_dialog,
    open_po_edit_dialog_if_armed,
)


def render(services: dict) -> None:
    from vaybooks.bms.ui.keyboard.actions import consume_action
    from vaybooks.bms.ui.keyboard.context import set_current_page
    from vaybooks.bms.ui.keyboard.wired import mark_wired

    set_current_page("purchase_order_detail")
    mark_wired("nav.back")
    order_id = st.query_params.get("id")
    if not order_id:
        st.warning("Purchase order not specified")
        return

    purchases = services["purchases"]
    order = purchases.get_purchase_order(order_id)
    if not order:
        st.warning("Purchase order not found")
        return

    if st.button("← Back", key="po_detail_back") or consume_action("nav.back"):
        navigation.go_back_to_list("purchase_orders_list", "purchase-orders")
        return

    document_header(
        number=order.po_number,
        status=order.status.value,
        caption_parts=[f"Vendor: {order.vendor_name}"],
        left_facts=[
            ("Order date", format_document_date(order.order_date)),
            ("Expected", format_document_date(order.expected_date)),
        ],
        right_facts=[
            ("Status", order.status.value),
            ("Total", format_money(order.total_amount)),
        ],
        suffix=f"po_{order.id}",
    )

    table_rows = [
        {
            "item_name": line.product_name or line.product_id or "—",
            "product": line.product_name or line.product_id or "—",
            "qty": line.qty_ordered,
            "qty_ordered": line.qty_ordered,
            "qty_received": line.qty_received,
            "rate": line.rate,
            "total": line.line_total,
            "line_total": line.line_total,
        }
        for line in order.lines
    ]
    line_items_table(
        table_rows,
        show_gst=False,
        suffix=f"po_{order.id}",
        item_column_label="Item",
    )
    totals_ladder(
        show_gst=False,
        grand_total=order.total_amount,
        suffix=f"po_{order.id}",
    )
    if order.notes:
        st.caption(f"Notes: {order.notes}")

    actions = []
    editable = order.status not in (
        PurchaseOrderStatus.CANCELLED,
        PurchaseOrderStatus.CLOSED,
    )
    if editable:
        actions.append({"label": "Edit", "key": "po_edit", "type": "primary"})
    if order.status.value not in ("Cancelled", "Closed", "Received"):
        mark_wired("purchases.orders.receive")
        actions.append(
            {"label": "Receive against PO", "key": "po_receive", "type": "primary"}
        )
    if editable and order.status != PurchaseOrderStatus.CANCELLED:
        if not any(line.qty_received > 0 for line in order.lines):
            actions.append({"label": "Cancel", "key": "po_cancel"})
        actions.append({"label": "Close", "key": "po_close"})

    clicked = document_actions(actions, suffix=f"po_{order.id}")
    if clicked.get("po_edit"):
        arm_po_edit_dialog(order.id)
        st.rerun()
    if clicked.get("po_receive") or consume_action("purchases.orders.receive"):
        arm_grn_dialog(po_id=order.id)
        st.rerun()
    if clicked.get("po_cancel"):
        try:
            purchases.cancel_purchase_order(order.id)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if clicked.get("po_close"):
        try:
            purchases.close_purchase_order(order.id)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    open_po_edit_dialog_if_armed(services)
    open_grn_dialog_if_armed(services)
