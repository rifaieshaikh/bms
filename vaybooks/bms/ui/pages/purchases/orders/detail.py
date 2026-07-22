"""Purchase order detail."""

from __future__ import annotations

import base64

import streamlit as st
import streamlit.components.v1 as components

from vaybooks.bms.domain.shared.enums import PurchaseOrderStatus
from vaybooks.bms.infrastructure.pdf.purchase_order_pdf import generate_purchase_order_pdf
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


def _trigger_pdf_download(file_name: str, pdf_bytes: bytes) -> None:
    """Browser download via parent-frame JS (used for Ctrl+P)."""
    b64 = base64.b64encode(pdf_bytes).decode("ascii")
    safe_name = file_name.replace("\\", "\\\\").replace("'", "\\'")
    html = f"""
<!DOCTYPE html><html><body>
<script>
(function () {{
  try {{
    const a = (window.parent && window.parent.document)
      ? window.parent.document.createElement('a')
      : document.createElement('a');
    a.href = 'data:application/pdf;base64,{b64}';
    a.download = '{safe_name}';
    const doc = (window.parent && window.parent.document) ? window.parent.document : document;
    doc.body.appendChild(a);
    a.click();
    a.remove();
  }} catch (e) {{}}
}})();
</script>
</body></html>
"""
    try:
        components.html(html, height=0, width=0)
    except Exception:
        pass


def render(services: dict) -> None:
    from vaybooks.bms.ui.keyboard.actions import consume_action
    from vaybooks.bms.ui.keyboard.context import set_current_page
    from vaybooks.bms.ui.keyboard.wired import mark_wired

    set_current_page("purchase_order_detail")
    mark_wired("nav.back", "purchases.orders.print")
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

    business = services["business"].get_profile()
    vendor = None
    if services.get("vendors") and order.vendor_id:
        vendor = services["vendors"].get_vendor_detail(order.vendor_id)
    template = None
    if business and getattr(business, "document_templates", None):
        template = business.document_templates.get("sales_order")
    pdf_bytes = None
    try:
        pdf_bytes = generate_purchase_order_pdf(
            order,
            business,
            template.print_settings if template else None,
            vendor=vendor,
        )
    except Exception as exc:
        st.error(f"Could not generate PDF: {exc}")

    if pdf_bytes and consume_action("purchases.orders.print"):
        _trigger_pdf_download(f"{order.po_number}.pdf", pdf_bytes)

    actions = []
    if pdf_bytes is not None:
        actions.append(
            {
                "label": "Download PDF",
                "key": "po_pdf",
                "kind": "download",
                "data": pdf_bytes,
                "file_name": f"{order.po_number}.pdf",
                "mime": "application/pdf",
            }
        )
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
