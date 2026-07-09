"""Store sale detail route (`?id=<voucher_id>`)."""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import streamlit as st

from vaybooks.bms.domain.shared.enums import VoucherType
from vaybooks.bms.ui import navigation
from vaybooks.bms.domain.accounting.sales_parsing import sales_row_from_voucher
from vaybooks.bms.ui.components.sales_invoice_form import parse_cash_sales_voucher
from vaybooks.bms.ui.components.voucher_card import voucher_receiving_account
from vaybooks.bms.ui.styles import metric_grid, panel


def _fmt_date(value) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime("%d %b %Y")
    return str(value) if value else "—"


def _line_items_table(line_items: list[dict]) -> pd.DataFrame:
    rows = []
    for item in line_items:
        desc = (item.get("description") or "").strip()
        if not desc:
            continue
        qty = float(item.get("qty") or 1.0)
        rate = float(item.get("rate") or 0.0)
        discount = float(item.get("discount") or 0.0)
        gross = round(qty * rate, 2)
        discount = round(min(max(discount, 0.0), gross), 2)
        rows.append(
            {
                "Description": desc,
                "Qty": qty,
                "Rate": rate,
                "Discount": discount,
                "Total": round(gross - discount, 2),
            }
        )
    return pd.DataFrame(rows)


def render(services: dict) -> None:
    accounting = services["accounting"]
    sale_id = navigation.current_detail_id("sales_detail")

    if st.button("← Back to sales", key="sales_detail_back"):
        navigation.go_back_to_list("store_sales", "sales_dashboard")
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

    store_no = row.get("store_invoice_number") or voucher.voucher_number
    st.title(f"Sale {store_no}")
    st.caption(
        f"Sale date: {_fmt_date(row.get('sale_date'))} · "
        f"Voucher {voucher.voucher_number}"
    )

    customer_name = row.get("party_name") or "Customer"
    with panel(f"sale_head_{voucher.id}"):
        with st.container(border=True):
            info = st.columns(2)
            info[0].write(f"**Customer:** {customer_name}")
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

            customer_account_id = row.get("customer_account_id")
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
    items_df = _line_items_table(parsed.get("line_items") or [])
    if items_df.empty:
        st.info("No line items recorded.")
    else:
        st.dataframe(items_df, use_container_width=True, hide_index=True)

    invoice_discount = float(parsed.get("invoice_discount") or 0.0)
    if invoice_discount > 0:
        st.caption(f"Invoice-level discount: ₹{invoice_discount:,.0f}")
