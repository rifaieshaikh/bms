"""Store sale detail route (`?id=<voucher_id>`)."""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import streamlit as st

from vaybooks.bms.domain.shared.enums import VoucherType
from vaybooks.bms.domain.shared.india import state_name_for_code
from vaybooks.bms.ui import navigation
from vaybooks.bms.domain.accounting.sales_parsing import sales_row_from_voucher
from vaybooks.bms.ui.components.sales_invoice_form import (
    line_items_grand_total,
    line_items_tax_total,
    line_items_taxable,
    parse_cash_sales_voucher,
)
from vaybooks.bms.ui.components.voucher_card import voucher_receiving_account
from vaybooks.bms.ui.styles import metric_grid, panel


def _fmt_date(value) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime("%d %b %Y")
    return str(value) if value else "—"


def _line_items_table(line_items: list[dict], inventory=None) -> pd.DataFrame:
    rows = []
    has_tax = any(
        "taxable_amount" in item or "cgst_amount" in item for item in line_items
    )
    for item in line_items:
        desc = (item.get("description") or "").strip()
        if not desc:
            continue
        qty = float(item.get("qty") or 1.0)
        rate = float(item.get("rate") or 0.0)
        discount = float(item.get("discount") or 0.0)
        gross = round(qty * rate, 2)
        discount = round(min(max(discount, 0.0), gross), 2)
        sku = ""
        product_id = item.get("product_id")
        if inventory and product_id:
            product = inventory.get_product(str(product_id))
            if product:
                sku = product.sku
        if has_tax:
            row = {
                "Description": desc,
                "HSN": item.get("hsn_sac") or "",
                "Qty": qty,
                "Rate": rate,
                "Discount": discount,
                "Taxable": float(item.get("taxable_amount") or round(gross - discount, 2)),
                "CGST": float(item.get("cgst_amount") or 0),
                "SGST": float(item.get("sgst_amount") or 0),
                "IGST": float(item.get("igst_amount") or 0),
                "Total": float(
                    item.get("line_total") or round(gross - discount, 2)
                ),
            }
        else:
            row = {
                "Description": desc,
                "Qty": qty,
                "Rate": rate,
                "Discount": discount,
                "Total": round(gross - discount, 2),
            }
        if sku:
            row["SKU"] = sku
        rows.append(row)
    return pd.DataFrame(rows)


def render(services: dict) -> None:
    from vaybooks.bms.ui.keyboard.actions import consume_action
    from vaybooks.bms.ui.keyboard.context import set_current_page
    from vaybooks.bms.ui.keyboard.wired import mark_wired

    set_current_page("sales_detail")
    mark_wired("nav.back")
    accounting = services["accounting"]
    sale_id = navigation.current_detail_id("sales_detail")

    if st.button("← Back to sales", key="sales_detail_back") or consume_action("nav.back"):
        navigation.go_back_to_list("store_sales", "sales_invoices_list")
        return

    if not sale_id:
        st.error("Sale not found.")
        return

    voucher = accounting.get_voucher(sale_id)
    if not voucher or voucher.voucher_type != VoucherType.SALES_INVOICE:
        st.error("Sale not found.")
        return

    discount = accounting.get_discount_account()
    discount_id = discount.id if discount else None
    row = sales_row_from_voucher(voucher, discount_id)
    parsed = parse_cash_sales_voucher(voucher, discount_id)
    tax_summary = parsed.get("tax_summary")
    line_items = parsed.get("line_items") or []

    store_no = row.get("store_invoice_number") or voucher.voucher_number
    st.title(f"Sale {store_no}")
    ref_so = getattr(voucher, "reference_so_id", None)
    ref_dn = getattr(voucher, "reference_dn_id", None)
    caption_parts = [
        f"Sale date: {_fmt_date(row.get('sale_date'))}",
        f"Voucher {voucher.voucher_number}",
    ]
    if ref_so:
        so = services.get("sales")
        if so:
            order = so.get_sales_order(ref_so)
            if order:
                caption_parts.append(f"SO {order.so_number}")
    if ref_dn:
        sales_svc = services.get("sales")
        if sales_svc:
            dn = sales_svc.get_delivery_note(ref_dn)
            if dn:
                caption_parts.append(f"DN {dn.dn_number}")
    st.caption(" · ".join(caption_parts))

    customer_name = row.get("party_name") or "Customer"
    customer_gstin = ""
    customer_state = ""
    customers = services.get("customers")
    customer_account_id = row.get("customer_account_id")
    if customers and customer_account_id:
        account = accounting.get_account(customer_account_id)
        if account and account.linked_customer_id:
            detail = customers.get_customer_detail(account.linked_customer_id)
            if detail:
                customer_gstin = detail.gstin or ""
                customer_state = detail.state_code or ""

    with panel(f"sale_head_{voucher.id}"):
        with st.container(border=True):
            info = st.columns(2)
            info[0].write(f"**Customer:** {customer_name}")
            if customer_gstin:
                info[0].caption(f"GSTIN: {customer_gstin}")
            if customer_state:
                info[0].caption(
                    f"Place of supply: {state_name_for_code(customer_state)}"
                )
            receiving = voucher_receiving_account(voucher)
            store_account = None
            if parsed.get("store_id"):
                store_account = accounting.get_account(parsed["store_id"])
            pay_label = (
                store_account.account_name
                if store_account
                else (receiving or "—")
            )
            info[1].write(f"**Received in:** {pay_label}")

            if customer_account_id:
                account = accounting.get_account(customer_account_id)
                if account and account.linked_customer_id:
                    if st.button(
                        "View customer →",
                        key=f"sale_view_customer_{voucher.id}",
                    ):
                        navigation.go_to_detail(
                            "customer_detail", account.linked_customer_id
                        )
                        return

    taxable = line_items_taxable(line_items, tax_summary)
    total_gst = line_items_tax_total(line_items, tax_summary)
    grand_total = line_items_grand_total(line_items, tax_summary)
    if tax_summary or total_gst > 0:
        metric_grid(
            [
                ("Taxable", f"₹{taxable:,.0f}"),
                ("Total GST", f"₹{total_gst:,.0f}"),
                ("Grand total", f"₹{grand_total:,.0f}"),
                ("Collected", f"₹{row.get('collected', 0):,.0f}"),
                ("Balance", f"₹{row.get('outstanding', 0):,.0f}"),
            ],
            suffix=f"sale_{voucher.id}",
        )
    else:
        metric_grid(
            [
                ("Gross", f"₹{row.get('gross', 0):,.0f}"),
                ("Discount", f"₹{row.get('discount', 0):,.0f}"),
                ("Net", f"₹{row.get('net', 0):,.0f}"),
                ("Collected", f"₹{row.get('collected', 0):,.0f}"),
                ("Balance", f"₹{row.get('outstanding', 0):,.0f}"),
            ],
            suffix=f"sale_{voucher.id}",
        )

    st.subheader("Line items")
    inventory = services.get("inventory")
    items_df = _line_items_table(line_items, inventory)
    if items_df.empty:
        st.info("No line items recorded.")
    else:
        st.dataframe(items_df, use_container_width=True, hide_index=True)

    invoice_discount = float(parsed.get("invoice_discount") or 0.0)
    if invoice_discount > 0:
        st.caption(f"Invoice-level discount: ₹{invoice_discount:,.0f}")
