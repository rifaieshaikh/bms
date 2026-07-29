"""Delivery note detail with lifecycle actions and timeline."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.domain.sales.sales_line_resolver import business_is_registered
from vaybooks.bms.domain.shared.enums import DeliveryNoteStatus
from vaybooks.bms.infrastructure.pdf.sales_doc_pdf import generate_sales_document_pdf
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.sales.delivery_note_edit_dialog import (
    arm_dn_edit_dialog,
    arm_dn_invoice_dialog,
    open_dn_detail_dialogs_if_armed,
)
from vaybooks.bms.ui.components.common.document_detail import (
    document_actions,
    document_header,
    format_document_date,
    line_items_table,
    secondary_sections,
    totals_ladder,
)
from vaybooks.bms.ui.components.sales.sales_line_ui import (
    line_tax_profile,
    preview_sales_line_gst,
    tax_summary_from_previews,
)


_TIMELINE = ("Draft", "Confirmed", "Dispatched", "Delivered")


def _timeline(status_value: str) -> None:
    current = status_value
    if current == "Partially Delivered":
        current = "Delivered"
    if current == "Cancelled":
        st.warning("Cancelled")
        return
    cols = st.columns(len(_TIMELINE))
    reached = True
    for i, step in enumerate(_TIMELINE):
        if step == current:
            cols[i].markdown(f"**● {step}**")
            reached = False
        elif reached:
            cols[i].markdown(f"✓ {step}")
        else:
            cols[i].markdown(f"○ {step}")


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
        dn.reference_label,
    ]

    left_facts = [("Customer", dn.customer_name)]
    if dn.contact_phone or (customer and customer.phone_number):
        left_facts.append(
            ("Mobile", dn.contact_phone or (customer.phone_number if customer else ""))
        )
    if dn.gstin or (customer and customer.gstin):
        left_facts.append(("GSTIN", dn.gstin or (customer.gstin if customer else "")))
    if dn.delivery_address:
        left_facts.append(("Delivery address", dn.delivery_address))
    right_facts = [("Delivery date", format_document_date(dn.delivery_date))]
    if dn.so_number:
        right_facts.append(("Sales order", dn.so_number))
    if dn.invoice_number:
        right_facts.append(("Invoice", dn.invoice_number))
    if dn.voucher_id:
        right_facts.append(("Linked invoice", "Created"))
    if dn.delivery_partner_name:
        right_facts.append(("Partner", dn.delivery_partner_name))
    if dn.vehicle_number:
        right_facts.append(("Vehicle", dn.vehicle_number))

    document_header(
        number=dn.dn_number,
        status=dn.status.value,
        caption_parts=caption_parts,
        left_facts=left_facts,
        right_facts=right_facts,
        suffix=f"dn_{dn.id}",
    )
    _timeline(dn.status.value)

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
                "ordered": line.qty_ordered,
                "prev": line.qty_previously_delivered,
                "qty": line.qty_delivered,
                "remaining": line.qty_remaining,
                "rate": line.rate,
                "taxable": preview.get("taxable_amount") or 0,
                "gst_rate": preview.get("gst_rate") or 0,
                "cgst": preview.get("cgst_amount") or 0,
                "sgst": preview.get("sgst_amount") or 0,
                "utgst": preview.get("utgst_amount") or 0,
                "igst": preview.get("igst_amount") or 0,
                "total": preview.get("line_total")
                or round(line.qty_delivered * line.rate, 2),
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
    can_confirm = dn.status == DeliveryNoteStatus.DRAFT
    can_dispatch = dn.status in (
        DeliveryNoteStatus.DRAFT,
        DeliveryNoteStatus.CONFIRMED,
    )
    can_deliver = dn.status in (
        DeliveryNoteStatus.DRAFT,
        DeliveryNoteStatus.CONFIRMED,
        DeliveryNoteStatus.DISPATCHED,
        DeliveryNoteStatus.PARTIALLY_DELIVERED,
    )
    can_cancel = dn.status != DeliveryNoteStatus.CANCELLED
    can_invoice = dn.status in (
        DeliveryNoteStatus.CONFIRMED,
        DeliveryNoteStatus.DISPATCHED,
        DeliveryNoteStatus.DELIVERED,
        DeliveryNoteStatus.PARTIALLY_DELIVERED,
    ) and not dn.voucher_id
    can_pay_partner = (
        dn.charges.paid_by_us
        and dn.charges.amount > 0
        and not dn.charges.payment_voucher_id
        and dn.status != DeliveryNoteStatus.CANCELLED
    )
    if can_invoice:
        mark_wired("sales.deliveries.create_invoice")

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
        actions.append({"label": "Edit Draft", "key": "edit"})
    if can_confirm:
        actions.append({"label": "Confirm", "key": "confirm", "type": "primary"})
    if can_dispatch and dn.status != DeliveryNoteStatus.DRAFT:
        actions.append({"label": "Mark Dispatched", "key": "dispatch"})
    if can_deliver and dn.status not in (
        DeliveryNoteStatus.DELIVERED,
    ):
        actions.append({"label": "Mark Delivered", "key": "deliver"})
    if can_invoice:
        actions.append({"label": "Create Invoice", "key": "invoice"})
    if can_pay_partner:
        actions.append({"label": "Record Partner Payment", "key": "pay_partner"})
    if can_cancel:
        actions.append({"label": "Cancel", "key": "cancel"})
    if dn.voucher_id:
        actions.append({"label": "View invoice →", "key": "view_invoice"})

    clicked = document_actions(actions, suffix=f"dn_{dn.id}")
    try:
        if clicked.get("edit"):
            arm_dn_edit_dialog(dn.id)
            st.rerun()
        if clicked.get("confirm"):
            sales.confirm_delivery_note(dn.id)
            st.rerun()
        if clicked.get("dispatch"):
            sales.dispatch_delivery_note(dn.id)
            st.rerun()
        if clicked.get("deliver"):
            sales.deliver_delivery_note(dn.id)
            st.rerun()
        if clicked.get("cancel"):
            sales.cancel_delivery_note(dn.id)
            st.rerun()
        if clicked.get("pay_partner"):
            st.session_state[f"dn_pay_{dn.id}"] = True
        if clicked.get("invoice") or (
            can_invoice and consume_action("sales.deliveries.create_invoice")
        ):
            arm_dn_invoice_dialog(dn.id)
            st.rerun()
        if clicked.get("view_invoice") and dn.voucher_id:
            navigation.go_to_detail("sales_detail", dn.voucher_id)
            return
    except Exception as exc:
        st.error(str(exc))

    if st.session_state.get(f"dn_pay_{dn.id}"):
        with st.expander("Record delivery partner payment", expanded=True):
            from vaybooks.bms.ui.components.sales.delivery_charge_payment import (
                render_pay_delivery_charges,
            )

            # Pre-select this DN by scoping to partner; user picks if multiple.
            render_pay_delivery_charges(
                services,
                partner_id=dn.delivery_partner_id or None,
                key_prefix=f"dn_pay_{dn.id[:8]}",
            )
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

    st.subheader("Delivery charges")
    st.write(
        f"Paid by us: {'Yes' if dn.charges.paid_by_us else 'No'} · "
        f"Recoverable: {'Yes' if dn.charges.recoverable_from_customer else 'No'} · "
        f"Amount ₹{dn.charges.amount:,.2f} · "
        f"Status {dn.charges.payment_status.value if hasattr(dn.charges.payment_status, 'value') else dn.charges.payment_status}"
    )
    if dn.charges.expense_voucher_id:
        st.caption(f"Expense voucher: {dn.charges.expense_voucher_id}")
    if dn.charges.payment_voucher_id:
        st.caption(f"Payment voucher: {dn.charges.payment_voucher_id}")

    with st.expander("Transport & proof of delivery"):
        c1, c2, c3 = st.columns(3)
        vehicle = c1.text_input(
            "Vehicle number", value=dn.vehicle_number, key=f"dn_tr_veh_{dn.id}"
        )
        driver = c2.text_input(
            "Driver name", value=dn.driver_name, key=f"dn_tr_drv_{dn.id}"
        )
        dphone = c3.text_input(
            "Driver phone", value=dn.driver_phone, key=f"dn_tr_dph_{dn.id}"
        )
        lr = st.text_input(
            "LR / Consignment no.",
            value=dn.lr_consignment_number,
            key=f"dn_tr_lr_{dn.id}",
        )
        eway = st.text_input(
            "E-way bill", value=dn.eway_bill_number, key=f"dn_tr_ew_{dn.id}"
        )
        recv = st.text_input(
            "Receiver name", value=dn.receiver_name, key=f"dn_tr_recv_{dn.id}"
        )
        rphone = st.text_input(
            "Receiver phone", value=dn.receiver_phone, key=f"dn_tr_rph_{dn.id}"
        )
        pod = st.file_uploader(
            "POD attachment",
            accept_multiple_files=True,
            key=f"dn_tr_pod_{dn.id}",
        )
        if st.button("Save transport / POD", key=f"dn_tr_save_{dn.id}"):
            attachments = list(dn.attachments or [])
            if pod:
                for uploaded in pod:
                    data = uploaded.getvalue()
                    if len(data) <= 10 * 1024 * 1024:
                        attachments.append(
                            {
                                "name": uploaded.name,
                                "content_type": uploaded.type
                                or "application/octet-stream",
                                "data": data,
                            }
                        )
            try:
                sales.update_delivery_logistics(
                    dn.id,
                    vehicle_number=vehicle,
                    driver_name=driver,
                    driver_phone=dphone,
                    lr_consignment_number=lr,
                    eway_bill_number=eway,
                    receiver_name=recv,
                    receiver_phone=rphone,
                    attachments=attachments,
                )
                st.success("Saved")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    if dn.attachments:
        st.subheader("Proof of delivery")
        for i, att in enumerate(dn.attachments):
            data = att.get("data")
            if data:
                st.download_button(
                    att.get("name") or f"POD {i+1}",
                    data=data,
                    file_name=att.get("name") or f"pod_{i+1}",
                    mime=att.get("content_type") or "application/octet-stream",
                    key=f"dn_pod_{dn.id}_{i}",
                )

    if dn.receiver_name or dn.received_at:
        st.caption(
            f"Received by {dn.receiver_name or '—'} "
            f"({dn.receiver_phone or '—'}) at {dn.received_at or '—'}"
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
