"""Delivery note detail."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.domain.sales.sales_line_resolver import business_is_registered
from vaybooks.bms.domain.shared.enums import DeliveryNoteStatus
from vaybooks.bms.infrastructure.pdf.sales_doc_pdf import generate_sales_document_pdf
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.delivery_note_edit_dialog import (
    arm_dn_edit_dialog,
    arm_dn_invoice_dialog,
    open_dn_detail_dialogs_if_armed,
)
from vaybooks.bms.ui.components.document_detail import (
    document_actions,
    document_header,
    format_document_date,
    line_items_table,
    secondary_sections,
    totals_ladder,
)
from vaybooks.bms.ui.components.sales_line_ui import (
    line_tax_profile,
    preview_sales_line_gst,
    tax_summary_from_previews,
)


def render(services: dict) -> None:
    from vaybooks.bms.ui.keyboard.actions import consume_action
    from vaybooks.bms.ui.keyboard.context import set_current_page
    from vaybooks.bms.ui.keyboard.wired import mark_wired

    set_current_page("delivery_note_detail")
    mark_wired("nav.back")
    dn_id = navigation.current_detail_id("delivery_note_detail")
    if not dn_id:
        st.warning("Delivery note not specified")
        return

    sales = services["sales"]
    inventory = services.get("inventory")
    business_service = services.get("business")
    dn = sales.get_delivery_note(dn_id)
    if not dn:
        st.warning("Delivery note not found")
        return

    if st.button("← Back", key="dn_detail_back") or consume_action("nav.back"):
        navigation.go_back_to_list("delivery_notes", "delivery_notes_list")
        return

    business = business_service.get_profile() if business_service else None
    business_registered = business_is_registered(business)
    business_state = business.state_code if business else ""
    customers = services.get("customers")
    customer = customers.get_customer_detail(dn.customer_id) if customers else None
    customer_state = (customer.state_code if customer else "") or ""

    caption_parts = [
        dn.customer_name,
        format_document_date(dn.delivery_date),
    ]
    if dn.so_number:
        caption_parts.append(f"SO {dn.so_number}")

    left_facts = [("Customer", dn.customer_name)]
    if customer and customer.phone_number:
        left_facts.append(("Mobile", customer.phone_number))
    if customer and customer.gstin:
        left_facts.append(("GSTIN", customer.gstin))
    right_facts = [("Delivery date", format_document_date(dn.delivery_date))]
    if dn.so_number:
        right_facts.append(("Sales order", dn.so_number))
    if dn.voucher_id:
        right_facts.append(("Invoice", "Created"))

    document_header(
        number=dn.dn_number,
        status=dn.status.value,
        caption_parts=caption_parts,
        left_facts=left_facts,
        right_facts=right_facts,
        suffix=f"dn_{dn.id}",
    )

    item_rows = []
    gst_previews = []
    for line in dn.lines:
        product = inventory.get_product(line.product_id) if inventory else None
        tax_profile = line_tax_profile(product)
        preview = preview_sales_line_gst(
            line.qty_delivered,
            line.rate,
            0.0,
            tax_profile,
            business_registered=business_registered,
            business=business,
            business_state_code=business_state,
            customer_state_code=customer_state,
        )
        gst_previews.append(preview)
        item_rows.append(
            {
                "sku": getattr(product, "sku", "") if product else "",
                "product": line.product_name or line.product_id,
                "hsn_sac": preview.get("hsn_sac") or "",
                "qty": line.qty_delivered,
                "rate": line.rate,
                "taxable": preview.get("taxable_amount") or 0,
                "gst_rate": preview.get("gst_rate") or 0,
                "cgst": preview.get("cgst_amount") or 0,
                "sgst": preview.get("sgst_amount") or 0,
                "utgst": preview.get("utgst_amount") or 0,
                "igst": preview.get("igst_amount") or 0,
                "total": preview.get("line_total") or round(
                    line.qty_delivered * line.rate, 2
                ),
            }
        )
    summary = (
        tax_summary_from_previews(gst_previews)
        if gst_previews
        else {"grand_total": dn.total_amount}
    )

    template = business.document_templates.get("delivery_note") if business else None
    pdf_bytes = None
    try:
        pdf_bytes = generate_sales_document_pdf(
            "delivery_note",
            dn,
            business,
            template.print_settings if template else None,
        )
    except Exception as exc:
        st.error(f"Could not generate PDF: {exc}")

    can_edit = dn.status == DeliveryNoteStatus.DRAFT
    can_invoice = dn.status == DeliveryNoteStatus.DELIVERED and not dn.voucher_id

    actions = []
    if pdf_bytes is not None:
        actions.append(
            {
                "label": "Download PDF",
                "key": "pdf",
                "kind": "download",
                "data": pdf_bytes,
                "file_name": f"{dn.dn_number}.pdf",
                "mime": "application/pdf",
            }
        )
    if can_edit:
        actions.append({"label": "Edit", "key": "edit"})
    if can_invoice:
        actions.append(
            {
                "label": "Create invoice from DN",
                "key": "invoice",
                "type": "primary",
            }
        )
    if dn.voucher_id:
        actions.append({"label": "View invoice →", "key": "view_invoice"})

    clicked = document_actions(actions, suffix=f"dn_{dn.id}")
    if clicked.get("edit"):
        arm_dn_edit_dialog(dn.id)
        st.rerun()
    if clicked.get("invoice"):
        arm_dn_invoice_dialog(dn.id)
        st.rerun()
    if clicked.get("view_invoice") and dn.voucher_id:
        navigation.go_to_detail("sales_detail", dn.voucher_id)
        return

    line_items_table(
        item_rows,
        show_gst=business_registered,
        suffix=f"dn_{dn.id}",
    )
    totals_ladder(
        summary,
        show_gst=business_registered,
        grand_total=summary.get("grand_total", dn.total_amount),
        suffix=f"dn_{dn.id}",
    )
    secondary_sections(
        notes=dn.notes,
        document_content=dn.document_content,
    )

    default_received = float(
        summary.get("grand_total")
        if business_registered and gst_previews
        else dn.total_amount or 0
    )
    open_dn_detail_dialogs_if_armed(
        services, default_received=default_received
    )
