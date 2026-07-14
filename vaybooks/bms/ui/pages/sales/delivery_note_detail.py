"""Delivery note detail."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.domain.sales.sales_line_resolver import business_is_registered
from vaybooks.bms.domain.shared.enums import DeliveryNoteStatus
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.sales_line_ui import (
    line_tax_profile,
    preview_sales_line_gst,
    tax_summary_from_previews,
)

INVOICE_FROM_DN_KEY = "invoice_from_dn_dialog"


def arm_invoice_from_dn(dn_id: str) -> None:
    st.session_state[INVOICE_FROM_DN_KEY] = dn_id


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
    accounting = services["accounting"]
    inventory = services.get("inventory")
    business_service = services.get("business")
    dn = sales.get_delivery_note(dn_id)
    if not dn:
        st.warning("Delivery note not found")
        return

    if st.button("← Back", key="dn_detail_back") or consume_action("nav.back"):
        navigation.go_back_to_list("delivery_notes", "delivery_notes_list")
        return

    st.title(dn.dn_number)
    st.caption(f"Customer: {dn.customer_name}")
    if dn.so_number:
        st.caption(f"SO: {dn.so_number}")
    st.caption(f"Status: {dn.status.value}")
    st.caption(f"Delivery date: {dn.delivery_date}")

    business = business_service.get_profile() if business_service else None
    business_registered = business_is_registered(business)
    business_state = business.state_code if business else ""
    customer_state = ""
    customers = services.get("customers")
    if customers:
        customer = customers.get_customer_detail(dn.customer_id)
        if customer:
            customer_state = customer.state_code or ""

    gst_previews: list[dict] = []
    for line in dn.lines:
        with st.container(border=True):
            st.write(line.product_name or line.product_id)
            product = inventory.get_product(line.product_id) if inventory else None
            tax_profile = line_tax_profile(product)
            preview = preview_sales_line_gst(
                line.qty_delivered,
                line.rate,
                0.0,
                tax_profile,
                business_registered=business_registered,
                business_state_code=business_state,
                customer_state_code=customer_state,
            )
            gst_previews.append(preview)
            if business_registered and preview["line_total"] > 0:
                gst_bits = []
                if preview["cgst_amount"]:
                    gst_bits.append(f"CGST ₹{preview['cgst_amount']:,.2f}")
                if preview["sgst_amount"]:
                    gst_bits.append(f"SGST ₹{preview['sgst_amount']:,.2f}")
                if preview["utgst_amount"]:
                    gst_bits.append(f"UTGST ₹{preview['utgst_amount']:,.2f}")
                if preview["igst_amount"]:
                    gst_bits.append(f"IGST ₹{preview['igst_amount']:,.2f}")
                st.caption(
                    f"Qty {line.qty_delivered:g} @ ₹{line.rate:,.2f} (ex-GST)"
                    f" · Taxable ₹{preview['taxable_amount']:,.2f}"
                    + (f" · {' · '.join(gst_bits)}" if gst_bits else "")
                    + f" · Line total ₹{preview['line_total']:,.2f}"
                )
            else:
                st.caption(f"Qty {line.qty_delivered:g} @ ₹{line.rate:,.2f}")

    if gst_previews and business_registered:
        summary = tax_summary_from_previews(gst_previews)
        st.caption(
            f"Invoice taxable ₹{summary['taxable']:,.2f}"
            f" · GST ₹{summary['total_tax']:,.2f}"
            f" · Grand total ₹{summary['grand_total']:,.2f}"
        )

    if dn.status == DeliveryNoteStatus.DELIVERED and not dn.voucher_id:
        if st.button("Create invoice from DN", type="primary", key="dn_invoice_btn"):
            arm_invoice_from_dn(dn.id)
            st.rerun()

    pending_dn = st.session_state.get(INVOICE_FROM_DN_KEY)
    if pending_dn == dn.id:
        store_accounts = accounting.get_store_accounts()
        if not store_accounts:
            st.error("Need at least one cash/bank store account.")
        else:
            store_opts = {a.account_name: a.id for a in store_accounts}
            store_name = st.selectbox(
                "Received in",
                list(store_opts.keys()),
                key=f"dn_inv_store_{dn.id}",
            )
            inv_no = st.text_input(
                "Invoice number",
                value=dn.dn_number,
                key=f"dn_inv_no_{dn.id}",
            )
            received = st.number_input(
                "Amount received",
                min_value=0.0,
                value=float(
                    tax_summary_from_previews(gst_previews)["grand_total"]
                    if gst_previews and business_registered
                    else dn.total_amount
                ),
                key=f"dn_inv_recv_{dn.id}",
            )
            discount = st.number_input(
                "Discount",
                min_value=0.0,
                value=0.0,
                key=f"dn_inv_disc_{dn.id}",
            )
            if st.button("Post invoice", type="primary", key=f"dn_inv_save_{dn.id}"):
                try:
                    sales.create_sales_invoice_from_dn(
                        dn_id=dn.id,
                        store_account_id=store_opts[store_name],
                        store_invoice_number=inv_no,
                        discount_amount=discount,
                        amount_received=received,
                    )
                    st.session_state.pop(INVOICE_FROM_DN_KEY, None)
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
            if st.button("Cancel", key=f"dn_inv_cancel_{dn.id}"):
                st.session_state.pop(INVOICE_FROM_DN_KEY, None)
                st.rerun()

    if dn.voucher_id:
        if st.button("View invoice →", key=f"dn_view_inv_{dn.id}"):
            navigation.go_to_detail("sales_detail", dn.voucher_id)
