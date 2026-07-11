"""Product detail with per-product stock ledger."""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import streamlit as st

from vaybooks.bms.domain.shared.enums import CatalogItemType
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.styles import metric_grid, panel


def _fmt_date(value) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime("%d %b %Y")
    return str(value) if value else "—"


def render(services: dict):
    inventory = services["inventory"]
    product_id = navigation.current_detail_id("inventory_product_detail")

    if st.button("← Back to products", key="inv_product_detail_back"):
        navigation.go_back_to_list("inventory_products", "inventory_products_list")
        return

    if not product_id:
        st.error("Product not found.")
        return

    product = inventory.get_product(product_id)
    if not product:
        st.error("Product not found.")
        return

    st.title(product.name)
    st.caption(
        f"{product.sku} · "
        + (" · ".join(product.category_names) if product.category_names else product.category_name or "—")
    )

    active_gst = product.active_gst_slab()
    active_mrp = product.active_mrp_slab()

    with panel(f"inv_prod_head_{product.id}"):
        with st.container(border=True):
            metric_grid(
                [
                    ("Current stock", f"{product.current_qty:g} {product.unit}"),
                    ("Opening qty", f"{product.opening_qty:g}"),
                    ("Selling rate", f"₹{product.selling_rate:,.0f}"),
                    ("HSN", product.hsn_sac or "—"),
                    ("Active GST", f"{active_gst.gst_rate:g}%" if active_gst else "—"),
                    ("Active MRP", f"₹{active_mrp.mrp:,.2f}" if active_mrp else "—"),
                    ("Status", "Active" if product.is_active else "Inactive"),
                ],
                suffix=f"inv_prod_{product.id}",
            )

    with st.expander("GST rate history", expanded=False):
        gst_rows = []
        for slab in sorted(product.gst_rates, key=lambda s: s.effective_from, reverse=True):
            gst_rows.append(
                {
                    "Rate (%)": slab.gst_rate,
                    "Effective from": _fmt_date(slab.effective_from),
                    "Active": "Yes" if slab.is_active else "No",
                }
            )
        if gst_rows:
            st.dataframe(pd.DataFrame(gst_rows), use_container_width=True, hide_index=True)
        else:
            st.caption("No GST rates recorded.")

    with st.expander("MRP history", expanded=False):
        mrp_rows = []
        for entry in sorted(product.mrp_entries, key=lambda e: e.effective_from, reverse=True):
            mrp_rows.append(
                {
                    "MRP (₹)": entry.mrp,
                    "Effective from": _fmt_date(entry.effective_from),
                    "Active": "Yes" if entry.is_active else "No",
                }
            )
        if mrp_rows:
            st.dataframe(pd.DataFrame(mrp_rows), use_container_width=True, hide_index=True)
        else:
            st.caption("No MRP history recorded.")

    if product.specifications:
        st.subheader("Specifications")
        spec_rows = [{"Name": k, "Value": v} for k, v in product.specifications.items()]
        st.dataframe(pd.DataFrame(spec_rows), use_container_width=True, hide_index=True)

    if product.custom_fields:
        st.subheader("Custom fields")
        cf_rows = [{"Field": k, "Value": v} for k, v in product.custom_fields.items()]
        st.dataframe(pd.DataFrame(cf_rows), use_container_width=True, hide_index=True)

    st.subheader("Purchase price history")
    history = services["purchases"].list_purchase_price_history(
        CatalogItemType.PRODUCT, product_id
    )
    if not history:
        st.caption("No purchase history yet.")
    else:
        for row in history[:20]:
            st.caption(
                f"{row.purchase_date} · Qty {row.qty:g} @ ₹{row.rate:,.2f} "
                f"(₹{row.line_total:,.2f}) · Bill {row.vendor_bill_number or '—'}"
            )

    st.subheader("Stock ledger")
    ledger = inventory.get_product_ledger(product_id)
    if not ledger:
        st.info("No movements for this product yet.")
        return

    rows = []
    for entry in ledger:
        rows.append(
            {
                "Date": _fmt_date(entry.get("movement_date")),
                "Type": entry.get("movement_type", ""),
                "Qty In": entry.get("qty_in") or "",
                "Qty Out": entry.get("qty_out") or "",
                "Balance": entry.get("balance", ""),
                "Reference": entry.get("reference_id") or entry.get("reference_type", ""),
                "Notes": entry.get("notes", ""),
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
