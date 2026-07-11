"""Create-only store sales invoice dialog (shared by Sales page)."""

from __future__ import annotations

from datetime import date

import streamlit as st

from vaybooks.bms.domain.sales.sales_line_resolver import business_is_registered
from vaybooks.bms.ui.components.sales_invoice_form import (
    default_line_item,
    line_items_discount,
    line_items_gross,
)
from vaybooks.bms.ui.components.sales_line_ui import (
    line_items_total,
    line_tax_profile,
    preview_sales_line_gst,
    tax_summary_from_previews,
)
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler

SALES_RECORD_DIALOG = "sales_record_dialog"
_LINES_KEY = f"{SALES_RECORD_DIALOG}_line_items"
_MOBILE_KEY = f"{SALES_RECORD_DIALOG}_cust_mobile"
_NAME_KEY = f"{SALES_RECORD_DIALOG}_cust_name"
_MATCHED_KEY = f"{SALES_RECORD_DIALOG}_matched_id"


def _index_of(options: dict, target_id, default: int = 0) -> int:
    ids = list(options.values())
    return ids.index(target_id) if target_id in ids else default


def arm_sales_record_dialog() -> None:
    st.session_state[SALES_RECORD_DIALOG] = "new"


def _clear_dialog_session() -> None:
    for key in list(st.session_state.keys()):
        if key.startswith(SALES_RECORD_DIALOG):
            st.session_state.pop(key, None)
    st.session_state.pop(SALES_RECORD_DIALOG, None)
    st.session_state.pop(_LINES_KEY, None)


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

    if _LINES_KEY not in st.session_state:
        st.session_state[_LINES_KEY] = [default_line_item()]

    def _on_mobile_change() -> None:
        mobile = (st.session_state.get(_MOBILE_KEY) or "").strip()
        if not mobile:
            st.session_state.pop(_MATCHED_KEY, None)
            return
        customer = customer_service.lookup_customer_by_phone(mobile)
        if customer:
            st.session_state[_NAME_KEY] = customer.customer_name
            st.session_state[_MATCHED_KEY] = customer.id
        else:
            st.session_state.pop(_MATCHED_KEY, None)

    customer_mobile = st.text_input(
        "Mobile",
        key=_MOBILE_KEY,
        on_change=_on_mobile_change,
    )
    matched_id = st.session_state.get(_MATCHED_KEY)
    matched_customer = None
    if matched_id:
        matched_customer = customer_service.get_customer_detail(matched_id)
        if matched_customer:
            st.caption(f"Existing customer: **{matched_customer.customer_name}**")

    customer_name = st.text_input("Customer name", key=_NAME_KEY)
    customer_state = matched_customer.state_code if matched_customer else ""

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

    st.markdown("**Line items**")
    line_items: list[dict] = list(st.session_state.get(_LINES_KEY, [default_line_item()]))
    product_options: dict[str, str | None] = {"— Manual —": None}
    if inventory_service:
        for product in inventory_service.list_products(active_only=True):
            product_options[f"{product.sku} — {product.name}"] = product.id

    def _product_index(target_id) -> int:
        ids = list(product_options.values())
        return ids.index(target_id) if target_id in ids else 0

    remove_idx = None
    gst_previews: list[dict] = []
    for idx, row in enumerate(line_items):
        with st.container(border=True):
            prod_labels = list(product_options.keys())
            product_label = st.selectbox(
                "Product",
                prod_labels,
                index=_product_index(row.get("product_id")),
                key=f"{SALES_RECORD_DIALOG}_line_product_{idx}",
            )
            product_id = product_options[product_label]
            head = st.columns([4, 1, 1, 1, 1])
            desc = head[0].text_input(
                "Description",
                value=row.get("description", ""),
                key=f"{SALES_RECORD_DIALOG}_line_desc_{idx}",
            )
            qty = head[1].number_input(
                "Qty",
                min_value=0.0,
                value=float(row.get("qty") or 1.0),
                key=f"{SALES_RECORD_DIALOG}_line_qty_{idx}",
            )
            rate = head[2].number_input(
                "Rate (ex-GST)",
                min_value=0.0,
                value=float(row.get("rate") or 0.0),
                key=f"{SALES_RECORD_DIALOG}_line_rate_{idx}",
            )
            line_disc = head[3].number_input(
                "Disc (₹)",
                min_value=0.0,
                value=float(row.get("discount") or 0.0),
                key=f"{SALES_RECORD_DIALOG}_line_disc_{idx}",
            )
            if head[4].button("Remove", key=f"{SALES_RECORD_DIALOG}_line_rm_{idx}"):
                remove_idx = idx
            product = None
            if product_id and inventory_service:
                product = inventory_service.get_product(product_id)
                if product:
                    if not (desc or "").strip():
                        desc = product.name
                    if float(rate or 0) == 0.0:
                        rate = float(product.selling_rate or 0)
            line_gross = round(qty * rate, 2)
            line_disc = round(min(max(line_disc, 0.0), line_gross), 2)
            tax_profile = line_tax_profile(product)
            preview = preview_sales_line_gst(
                qty,
                rate,
                line_disc,
                tax_profile,
                business_registered=business_registered,
                business_state_code=business_state,
                customer_state_code=customer_state,
            )
            gst_previews.append(preview)
            if show_gst and preview["line_total"] > 0:
                gst_bits = []
                if preview["cgst_amount"]:
                    gst_bits.append(f"CGST ₹{preview['cgst_amount']:,.2f}")
                if preview["sgst_amount"]:
                    gst_bits.append(f"SGST ₹{preview['sgst_amount']:,.2f}")
                if preview["utgst_amount"]:
                    gst_bits.append(f"UTGST ₹{preview['utgst_amount']:,.2f}")
                if preview["igst_amount"]:
                    gst_bits.append(f"IGST ₹{preview['igst_amount']:,.2f}")
                hsn = preview.get("hsn_sac") or ""
                hsn_bit = f"HSN {hsn} · " if hsn else ""
                st.caption(
                    f"{hsn_bit}Taxable ₹{preview['taxable_amount']:,.2f}"
                    + (f" · {' · '.join(gst_bits)}" if gst_bits else "")
                    + f" · Line total ₹{preview['line_total']:,.2f}"
                )
            elif preview["line_total"] > 0:
                st.caption(f"Line total ₹{preview['line_total']:,.2f}")

            line_items[idx] = {
                "description": desc,
                "qty": qty,
                "rate": rate,
                "discount": line_disc,
                "product_id": product_id,
            }

    if remove_idx is not None and len(line_items) > 1:
        line_items.pop(remove_idx)
        st.session_state[_LINES_KEY] = line_items
        st.rerun()
    st.session_state[_LINES_KEY] = line_items

    if st.button("+ Add line", key=f"{SALES_RECORD_DIALOG}_add_line"):
        line_items.append(default_line_item())
        st.session_state[_LINES_KEY] = line_items
        st.rerun()

    gross = line_items_gross(line_items)
    line_discount_total = line_items_discount(line_items)
    taxable_sub = round(sum(p.get("taxable_amount", 0) for p in gst_previews), 2)
    tax_summary = tax_summary_from_previews(gst_previews) if gst_previews else {}
    grand_before_inv_disc = tax_summary.get("grand_total", line_items_total(line_items, gst_previews))

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
            net_due = round(grand_before_inv_disc - invoice_discount, 2)
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
            if net_due <= 0:
                raise ValueError("Invoice net amount must be positive")
            if received < 0:
                raise ValueError("Amount received cannot be negative")
            if total_discount > 0 and not show_gst and not discount_account:
                raise ValueError('A "Discount Allowed" account is required for discounts')
            if not (customer_name or "").strip() or not (customer_mobile or "").strip():
                raise ValueError("Customer name and mobile are required")
            customer = customer_service.find_or_create_customer(
                customer_name.strip(),
                customer_mobile.strip(),
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
                from vaybooks.bms.ui.components.sales_invoice_form import serialize_line_items

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
