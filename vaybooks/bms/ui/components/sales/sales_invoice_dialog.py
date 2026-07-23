"""Create-only store sales invoice dialog (shared by Sales page)."""

from __future__ import annotations

from datetime import date

import streamlit as st

from vaybooks.bms.domain.sales.sales_line_resolver import business_is_registered
from vaybooks.bms.domain.shared.enums import PartyRegistrationType
from vaybooks.bms.ui.components.common.customer_identity_selector import (
    render_customer_identity_selector,
    resolve_customer_identity,
)
from vaybooks.bms.ui.components.sales.sales_invoice_form import (
    line_items_discount,
    line_items_gross,
)
from vaybooks.bms.ui.components.sales.sales_line_ui import (
    line_items_total,
    line_tax_profile,
    preview_sales_line_gst,
    tax_summary_from_previews,
)
from vaybooks.bms.ui.components.sales.sales_lines_editor import render_sales_lines_editor
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler

SALES_RECORD_DIALOG = "sales_record_dialog"
SALES_RECORD_PRESELECT = "sales_record_dialog_preselect_customer_id"


def _index_of(options: dict, target_id, default: int = 0) -> int:
    ids = list(options.values())
    return ids.index(target_id) if target_id in ids else default


def arm_sales_record_dialog(customer_id: str | None = None) -> None:
    for key in list(st.session_state.keys()):
        if key.startswith(SALES_RECORD_DIALOG):
            st.session_state.pop(key, None)
    st.session_state[SALES_RECORD_DIALOG] = "new"
    if customer_id:
        st.session_state[SALES_RECORD_PRESELECT] = customer_id
    else:
        st.session_state.pop(SALES_RECORD_PRESELECT, None)


def _clear_dialog_session() -> None:
    for key in list(st.session_state.keys()):
        if key.startswith(SALES_RECORD_DIALOG):
            st.session_state.pop(key, None)
    st.session_state.pop(SALES_RECORD_DIALOG, None)
    st.session_state.pop(SALES_RECORD_PRESELECT, None)


@st.dialog(
    "Record Sale",
    width="large",
    on_dismiss=make_dismiss_handler(SALES_RECORD_DIALOG),
)
def sales_record_dialog(services: dict) -> None:
    if st.session_state.get(SALES_RECORD_DIALOG) != "new":
        return

    accounting_service = services["accounting"]
    customer_service = services["customers"]
    inventory_service = services.get("inventory")
    business_service = services.get("business")
    sales_account = accounting_service.get_sales_account()
    store_accounts = accounting_service.get_store_accounts()
    discount_account = accounting_service.get_discount_account()

    business = business_service.get_profile() if business_service else None
    business_registered = business_is_registered(business)
    business_state = business.state_code if business else ""
    show_gst = business_registered

    if not sales_account:
        st.error('No "Sales" revenue account found.')
        if st.button("Close"):
            _clear_dialog_session()
            st.rerun()
        return
    if not store_accounts:
        st.error("Need at least one cash/bank store account.")
        if st.button("Close"):
            _clear_dialog_session()
            st.rerun()
        return

    customer_selection = render_customer_identity_selector(
        customer_service,
        key_prefix=SALES_RECORD_DIALOG,
        initial_customer=(
            customer_service.get_customer_detail(
                st.session_state.get(SALES_RECORD_PRESELECT)
            )
            if st.session_state.get(SALES_RECORD_PRESELECT)
            else None
        ),
    )
    matched_customer = customer_selection.customer
    customer_state = matched_customer.state_code if matched_customer else ""
    customer_registered = bool(
        matched_customer
        and (
            matched_customer.registration_type == PartyRegistrationType.REGISTERED
            or (matched_customer.gstin or "").strip()
        )
    )
    if not customer_registered and not customer_state:
        customer_state = business_state

    store_opts = {a.account_name: a.id for a in store_accounts}
    store_names = list(store_opts.keys())
    default_store = store_accounts[0].id

    inv_cols = st.columns(2)
    store_number = inv_cols[0].text_input(
        "Store invoice number",
        key=f"{SALES_RECORD_DIALOG}_store_no",
    )
    inv_date = inv_cols[1].date_input(
        "Date",
        value=date.today(),
        key=f"{SALES_RECORD_DIALOG}_date",
    )
    store_name = st.selectbox(
        "Cash / Bank account",
        store_names,
        index=_index_of(store_opts, default_store),
        key=f"{SALES_RECORD_DIALOG}_store",
    )

    products = inventory_service.list_products(active_only=True) if inventory_service else []
    if not products:
        st.error("Add inventory products first.")
        return

    st.markdown("**Line items**")
    editor_lines, gst_errors = render_sales_lines_editor(
        key_prefix=SALES_RECORD_DIALOG,
        products=products,
        initial_lines=None,
        customer_id=matched_customer.id if matched_customer else None,
        use_customer_pricing=True,
        show_discount=True,
        sales_service=services.get("sales"),
        inventory_service=inventory_service,
        business_registered=business_registered,
        business=business,
        business_state_code=business_state,
        customer_state_code=customer_state or "",
        qty_field="qty",
    )

    line_items = [
        {
            "description": row.get("product_name") or "",
            "qty": float(row.get("qty") or 0),
            "rate": float(row.get("rate") or 0),
            "discount": float(row.get("discount") or 0),
            "product_id": row.get("product_id"),
        }
        for row in editor_lines
    ]

    gst_previews: list[dict] = []
    for row in line_items:
        product = (
            inventory_service.get_product(row["product_id"])
            if inventory_service and row.get("product_id")
            else None
        )
        gst_previews.append(
            preview_sales_line_gst(
                float(row["qty"] or 0),
                float(row["rate"] or 0),
                float(row["discount"] or 0),
                line_tax_profile(product),
                business_registered=business_registered,
                business=business,
                business_state_code=business_state,
                customer_state_code=customer_state or "",
            )
        )

    gross = line_items_gross(line_items)
    line_discount_total = line_items_discount(line_items)
    taxable_sub = round(sum(p.get("taxable_amount", 0) for p in gst_previews), 2)
    tax_summary = tax_summary_from_previews(gst_previews) if gst_previews else {}
    grand_before_inv_disc = tax_summary.get(
        "grand_total", line_items_total(line_items, gst_previews)
    )

    inv_disc_cols = st.columns(2)
    invoice_discount = inv_disc_cols[0].number_input(
        "Invoice-level discount (₹)",
        min_value=0.0,
        value=0.0,
        key=f"{SALES_RECORD_DIALOG}_inv_disc",
    )
    max_inv_disc = max(taxable_sub - line_discount_total, 0.0) if taxable_sub else max(
        gross - line_discount_total, 0.0
    )
    invoice_discount = round(min(max(invoice_discount, 0.0), max_inv_disc), 2)
    total_discount = round(line_discount_total + invoice_discount, 2)

    if invoice_discount > 0 and show_gst and taxable_sub > 0:
        factor = round((taxable_sub - invoice_discount) / taxable_sub, 6)
        adjusted_grand = round(grand_before_inv_disc * factor, 2)
        if tax_summary:
            adjusted_tax = round(tax_summary.get("total_tax", 0) * factor, 2)
            net_due = round(taxable_sub - invoice_discount + adjusted_tax, 2)
        else:
            net_due = round(adjusted_grand - invoice_discount, 2)
    else:
        net_due = round(max(grand_before_inv_disc - invoice_discount, 0.0), 2)

    received = st.number_input(
        "Amount received now",
        min_value=0.0,
        max_value=float(net_due) if net_due > 0 else 0.0,
        value=float(net_due),
        key=f"{SALES_RECORD_DIALOG}_received",
    )
    balance = round(net_due - received, 2)

    with st.container(border=True):
        st.markdown("**Summary**")
        if show_gst:
            m = st.columns(6)
            m[0].metric("Subtotal (taxable)", f"₹{taxable_sub:,.0f}")
            m[1].metric("CGST", f"₹{tax_summary.get('cgst', 0):,.0f}")
            m[2].metric("SGST", f"₹{tax_summary.get('sgst', 0):,.0f}")
            m[3].metric("IGST", f"₹{tax_summary.get('igst', 0):,.0f}")
            m[4].metric("Grand total", f"₹{grand_before_inv_disc:,.0f}")
            m[5].metric("Net due", f"₹{net_due:,.0f}")
            if total_discount > 0:
                st.caption(f"Discount (line + invoice): ₹{total_discount:,.0f}")
        else:
            m = st.columns(4)
            m[0].metric("Subtotal", f"₹{gross:,.0f}")
            m[1].metric("Total discount", f"₹{total_discount:,.0f}")
            m[2].metric("Net due", f"₹{net_due:,.0f}")
            m[3].metric("Customer balance", f"₹{balance:,.0f}")

    if total_discount > 0 and not discount_account and not show_gst:
        st.warning('No "Discount Allowed" account found. Create one to post discounts.')

    st.caption(f"Revenue credited to: **{sales_account.account_name}**")

    cols = st.columns(2)
    if cols[0].button("Save", type="primary", use_container_width=True):
        try:
            if gst_errors:
                raise ValueError(gst_errors[0])
            if not line_items:
                raise ValueError("Add at least one product line")
            if net_due <= 0:
                raise ValueError("Invoice net amount must be positive")
            if received < 0:
                raise ValueError("Amount received cannot be negative")
            if total_discount > 0 and not show_gst and not discount_account:
                raise ValueError('A "Discount Allowed" account is required for discounts')
            customer = resolve_customer_identity(
                customer_service,
                customer_selection,
            )
            customer_account = accounting_service.get_customer_account(customer.id)
            if not customer_account:
                raise ValueError("No ledger account for this customer")
            sales_service = services.get("sales")
            if sales_service:
                sales_service.create_direct_sale(
                    customer_account.id,
                    store_opts[store_name],
                    gross,
                    total_discount,
                    received,
                    store_number,
                    line_items,
                    voucher_date=inv_date,
                    invoice_discount=invoice_discount,
                )
            else:
                from vaybooks.bms.ui.components.sales.sales_invoice_form import serialize_line_items

                note = serialize_line_items(line_items, invoice_discount)
                voucher = accounting_service.create_cash_sales_invoice(
                    customer_account.id,
                    store_opts[store_name],
                    gross,
                    total_discount,
                    received,
                    store_number,
                    line_items_note=note,
                    voucher_date=inv_date,
                )
                if inventory_service:
                    inventory_service.apply_sales_movements(voucher.id, line_items)
            _clear_dialog_session()
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if cols[1].button("Cancel", use_container_width=True):
        _clear_dialog_session()
        st.rerun()


def open_sales_record_dialog_if_armed(services: dict) -> None:
    if st.session_state.get(SALES_RECORD_DIALOG):
        sales_record_dialog(services)
