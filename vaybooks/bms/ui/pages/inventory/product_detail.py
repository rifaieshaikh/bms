"""Product detail with per-product stock ledger."""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import streamlit as st

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
    st.caption(f"{product.sku} · {product.category_name or '—'}")

    with panel(f"inv_prod_head_{product.id}"):
        with st.container(border=True):
            metric_grid(
                [
                    ("Current stock", f"{product.current_qty:g} {product.unit}"),
                    ("Opening qty", f"{product.opening_qty:g}"),
                    ("Selling rate", f"₹{product.selling_rate:,.0f}"),
                    ("Status", "Active" if product.is_active else "Inactive"),
                ],
                suffix=f"inv_prod_{product.id}",
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
