"""Sales order detail."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.domain.sales.sales_line_resolver import business_is_registered
from vaybooks.bms.infrastructure.pdf.sales_doc_pdf import generate_sales_document_pdf
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.delivery_note_dialog import (
    arm_dn_dialog,
    open_dn_dialog_if_armed,
)
from vaybooks.bms.ui.components.document_detail import (
    document_actions,
    document_header,
    format_document_date,
    line_items_table,
    sales_line_row_from_entity,
    secondary_sections,
    totals_ladder,
)
from vaybooks.bms.ui.components.sales_order_edit_dialog import (
    arm_so_edit_dialog,
    arm_so_invoice_dialog,
    open_so_detail_dialogs_if_armed,
)


def render(services: dict) -> None:
    from vaybooks.bms.ui.keyboard.actions import consume_action
    from vaybooks.bms.ui.keyboard.context import set_current_page
    from vaybooks.bms.ui.keyboard.wired import mark_wired

    set_current_page("sales_order_detail")
    mark_wired("nav.back")
    order_id = navigation.current_detail_id("sales_order_detail")
    if not order_id:
        st.warning("Sales order not specified")
        return

    sales = services["sales"]
    order = sales.get_sales_order(order_id)
    if not order:
        st.warning("Sales order not found")
        return

    if st.button("← Back", key="so_detail_back") or consume_action("nav.back"):
        navigation.go_back_to_list("sales_orders", "sales_orders_list")
        return

    business = services["business"].get_profile()
    customers = services.get("customers")
    customer = (
        customers.get_customer_detail(order.customer_id) if customers else None
    )
    summary = order.tax_summary
    show_gst = business_is_registered(business) or bool(summary["total_tax"])

    caption_parts = [
        order.customer_name,
        format_document_date(order.order_date),
    ]
    if order.supply_type:
        caption_parts.append(order.supply_type)

    left_facts = [("Customer", order.customer_name)]
    if customer and customer.phone_number:
        left_facts.append(("Mobile", customer.phone_number))
    if customer and customer.gstin:
        left_facts.append(("GSTIN", customer.gstin))
    right_facts = [("Order date", format_document_date(order.order_date))]
    if order.expected_date:
        right_facts.append(
            ("Expected date", format_document_date(order.expected_date))
        )
    if order.supply_type:
        right_facts.append(("Supply type", order.supply_type))

    document_header(
        number=order.so_number,
        status=order.status.value,
        caption_parts=caption_parts,
        left_facts=left_facts,
        right_facts=right_facts,
        suffix=f"so_{order.id}",
    )

    template = business.document_templates.get("sales_order")
    pdf_bytes = None
    try:
        pdf_bytes = generate_sales_document_pdf(
            "sales_order",
            order,
            business,
            template.print_settings if template else None,
        )
    except Exception as exc:
        st.error(f"Could not generate PDF: {exc}")

    can_edit = order.status.value not in ("Cancelled", "Closed")
    can_direct_invoice = (
        can_edit
        and not any(line.qty_delivered > 0 for line in order.lines)
        and any(line.qty_invoiced < line.qty_ordered for line in order.lines)
    )
    can_deliver = order.status.value not in ("Cancelled", "Closed", "Delivered")

    actions = []
    if pdf_bytes is not None:
        actions.append(
            {
                "label": "Download PDF",
                "key": "pdf",
                "kind": "download",
                "data": pdf_bytes,
                "file_name": f"{order.so_number}.pdf",
                "mime": "application/pdf",
            }
        )
    if can_edit:
        actions.append({"label": "Edit", "key": "edit"})
    if can_direct_invoice:
        actions.append({"label": "Create Sales Invoice", "key": "invoice"})
    if can_deliver:
        actions.append(
            {
                "label": "Deliver against SO",
                "key": "deliver",
                "type": "primary",
            }
        )
    clicked = document_actions(actions, suffix=f"so_{order.id}")

    if clicked.get("edit"):
        arm_so_edit_dialog(order.id)
        st.rerun()
    if clicked.get("invoice"):
        arm_so_invoice_dialog(order.id)
        st.rerun()
    if clicked.get("deliver"):
        arm_dn_dialog(so_id=order.id)
        st.rerun()

    inventory = services.get("inventory")
    line_items_table(
        [
            sales_line_row_from_entity(line, inventory=inventory)
            for line in order.lines
        ],
        show_gst=show_gst,
        suffix=f"so_{order.id}",
    )
    totals_ladder(
        summary,
        show_gst=show_gst,
        grand_total=order.total_amount,
        suffix=f"so_{order.id}",
    )
    secondary_sections(
        notes=order.notes,
        document_content=order.document_content,
    )

    open_so_detail_dialogs_if_armed(services)
    open_dn_dialog_if_armed(services)
