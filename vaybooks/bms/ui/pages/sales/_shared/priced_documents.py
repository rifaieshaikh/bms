from __future__ import annotations

import streamlit as st

from vaybooks.bms.domain.sales.sales_line_resolver import business_is_registered
from vaybooks.bms.domain.shared.enums import QuotationStatus
from vaybooks.bms.infrastructure.pdf.sales_doc_pdf import generate_sales_document_pdf
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.common.list_view import render_list as render_standard_list
from vaybooks.bms.ui.components.sales.priced_document_card import (
    priced_document_cards,
    priced_document_row,
)
from vaybooks.bms.ui.components.sales.priced_document_dialog import (
    arm_priced_document_dialog,
    open_priced_document_dialog_if_armed,
)
from vaybooks.bms.ui.sales_list_schemas import ESTIMATES, QUOTATIONS


def render_list(services: dict, document_type: str) -> None:
    is_estimate = document_type == "estimate"
    title = "Estimates" if is_estimate else "Quotations"
    list_method = (
        services["sales"].list_estimates
        if is_estimate
        else services["sales"].list_quotations
    )
    detail_key = "estimate_detail" if is_estimate else "quotation_detail"
    schema = ESTIMATES if is_estimate else QUOTATIONS

    def _load(_services, _filters, _sort):
        try:
            return [
                priced_document_row(document, document_type)
                for document in list_method()
            ]
        except Exception:
            return []

    bar = render_standard_list(
        schema,
        services=services,
        load_fn=_load,
        card_renderer=lambda rows, _services: priced_document_cards(
            rows,
            document_type=document_type,
            suffix=f"{document_type}_list",
        ),
        primary_label=f"+ Create {'Estimate' if is_estimate else 'Quotation'}",
        primary_key=f"{document_type}_create_btn",
        title=title,
        empty_text=f"No {title.lower()} yet.",
        count_label=title.lower(),
        page_key_nav=f"{title.lower()}_list",
    )

    if bar["primary_clicked"]:
        arm_priced_document_dialog(document_type)
        st.rerun()
    if bar["view_nth"]:
        navigation.go_to_detail(detail_key, bar["view_nth"])
        return
    if bar["edit_nth"]:
        arm_priced_document_dialog(
            document_type, document_id=bar["edit_nth"]
        )
        st.rerun()

    open_priced_document_dialog_if_armed(services, document_type)


def render_detail(services: dict, document_type: str) -> None:
    from vaybooks.bms.ui.keyboard.actions import consume_action
    from vaybooks.bms.ui.keyboard.context import set_current_page
    from vaybooks.bms.ui.keyboard.wired import mark_wired

    from vaybooks.bms.ui.components.common.document_detail import (
        document_actions,
        document_header,
        format_document_date,
        line_items_table,
        sales_line_row_from_entity,
        secondary_sections,
        totals_ladder,
    )

    is_estimate = document_type == "estimate"
    detail_key = "estimate_detail" if is_estimate else "quotation_detail"
    list_key = "estimates_list" if is_estimate else "quotations_list"
    entity_key = "estimates" if is_estimate else "quotations"
    page_key = detail_key

    set_current_page(page_key)
    mark_wired("nav.back")

    document_id = navigation.current_detail_id(detail_key)
    getter = (
        services["sales"].get_estimate
        if is_estimate
        else services["sales"].get_quotation
    )
    document = getter(document_id) if document_id else None
    if not document:
        st.error("Document not found")
        return
    if st.button("← Back", key=f"{document_type}_detail_back") or consume_action(
        "nav.back"
    ):
        navigation.go_back_to_list(entity_key, list_key)
        return

    number = (
        document.estimate_number if is_estimate else document.quotation_number
    )
    document_date = (
        document.estimate_date if is_estimate else document.quotation_date
    )
    business = services["business"].get_profile()
    customer = services["customers"].get_customer_detail(document.customer_id)
    summary = document.tax_summary
    show_gst = business_is_registered(business) or bool(
        summary["total_tax"] or any(line.gst_rate for line in document.lines)
    )

    caption_parts = [
        document.customer_name,
        format_document_date(document_date),
    ]
    if document.valid_until:
        caption_parts.append(f"Valid until {format_document_date(document.valid_until)}")
    if document.supply_type:
        caption_parts.append(document.supply_type)

    left_facts = [("Customer", document.customer_name)]
    if customer and customer.phone_number:
        left_facts.append(("Mobile", customer.phone_number))
    if customer and customer.gstin:
        left_facts.append(("GSTIN", customer.gstin))
    right_facts = [
        ("Document date", format_document_date(document_date)),
        ("Valid until", format_document_date(document.valid_until)),
    ]
    if document.supply_type:
        right_facts.append(("Supply type", document.supply_type))
    if (
        not is_estimate
        and getattr(document, "converted_sales_order_id", None)
    ):
        order = services["sales"].get_sales_order(document.converted_sales_order_id)
        if order:
            right_facts.append(("Converted to", order.so_number))

    document_header(
        number=number,
        status=document.status.value,
        caption_parts=caption_parts,
        left_facts=left_facts,
        right_facts=right_facts,
        suffix=f"{document_type}_{document.id}",
    )

    template = business.document_templates.get(document_type)
    settings = template.print_settings if template else None
    pdf_bytes = None
    try:
        pdf_bytes = generate_sales_document_pdf(
            document_type, document, business, settings
        )
    except Exception as exc:
        st.error(f"Could not generate PDF: {exc}")

    terminal = {"Cancelled", "Expired"}
    if not is_estimate:
        terminal.update({"Converted", "Rejected"})
    can_edit = document.status.value not in terminal
    can_convert = (
        not is_estimate
        and document.status == QuotationStatus.ACCEPTED
        and not document.converted_sales_order_id
    )

    actions = []
    if pdf_bytes is not None:
        actions.append(
            {
                "label": "Download PDF",
                "key": "pdf",
                "kind": "download",
                "data": pdf_bytes,
                "file_name": f"{number}.pdf",
                "mime": "application/pdf",
            }
        )
    if can_edit:
        actions.append({"label": "Edit", "key": "edit"})
    if can_convert:
        actions.append(
            {
                "label": "Convert to Sales Order",
                "key": "convert",
                "type": "primary",
            }
        )
    clicked = document_actions(actions, suffix=f"{document_type}_{document.id}")

    if clicked.get("edit"):
        arm_priced_document_dialog(document_type, document_id=document.id)
        st.rerun()
    if clicked.get("convert"):
        try:
            order = services["sales"].convert_quotation_to_sales_order(document.id)
            st.success(f"Created {order.so_number}")
            navigation.go_to_detail("sales_order_detail", order.id)
            return
        except Exception as exc:
            st.error(str(exc))

    inventory = services.get("inventory")
    line_items_table(
        [
            sales_line_row_from_entity(line, inventory=inventory)
            for line in document.lines
        ],
        show_gst=show_gst,
        suffix=f"{document_type}_{document.id}",
    )
    totals_ladder(
        summary,
        show_gst=show_gst,
        grand_total=document.total_amount,
        suffix=f"{document_type}_{document.id}",
    )
    secondary_sections(
        notes=document.notes,
        document_content=document.document_content,
    )

    open_priced_document_dialog_if_armed(services, document_type)
