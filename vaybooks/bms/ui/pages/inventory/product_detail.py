"""Product detail with per-product stock ledger and rate history tabs."""

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


def _render_history_tab(
    inventory,
    product_id: str,
    *,
    rate_type: str,
    title: str,
    list_fn,
    value_label: str,
    key_prefix: str,
    is_percent: bool = False,
):
    periods = list_fn(product_id)
    rows = []
    for period in sorted(periods, key=lambda p: p.start_date, reverse=True):
        status = inventory.rate_period_status(period)
        display_value = f"{period.value:g}%" if is_percent else f"₹{period.value:,.2f}"
        rows.append(
            {
                value_label: display_value,
                "Start": _fmt_date(period.start_date),
                "End": _fmt_date(period.end_date),
                "Status": status.value if hasattr(status, "value") else status,
            }
        )
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.caption(f"No {title.lower()} recorded.")

    with st.expander(f"Add future {title.lower()}", expanded=False):
        with st.form(f"{key_prefix}_add_form"):
            val = st.number_input(
                value_label,
                min_value=0.0,
                max_value=100.0 if is_percent else None,
                key=f"{key_prefix}_val",
            )
            start = st.date_input("Start date", value=date.today(), key=f"{key_prefix}_start")
            use_end = st.checkbox("Set end date", key=f"{key_prefix}_use_end")
            end = None
            if use_end:
                end = st.date_input("End date", value=start, key=f"{key_prefix}_end")
            if st.form_submit_button(f"Add {title}", type="primary"):
                try:
                    inventory.add_scheduled_rate_period(
                        rate_type,
                        product_id,
                        value=val,
                        start_date=start,
                        end_date=end,
                    )
                    st.success(f"{title} scheduled.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))


def render(services: dict):
    from vaybooks.bms.ui.keyboard.actions import consume_action
    from vaybooks.bms.ui.keyboard.context import set_current_page
    from vaybooks.bms.ui.keyboard.wired import mark_wired

    set_current_page("inventory_product_detail")
    mark_wired("nav.back")
    inventory = services["inventory"]
    product_id = navigation.current_detail_id("inventory_product_detail")

    if st.button("← Back to products", key="inv_product_detail_back") or consume_action(
        "nav.back"
    ):
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

    with panel(f"inv_prod_head_{product.id}"):
        with st.container(border=True):
            metric_grid(
                [
                    ("Current stock", f"{product.current_qty:g} {product.unit}"),
                    ("Opening qty", f"{product.opening_qty:g}"),
                    ("Selling price", f"₹{product.active_selling_rate:,.2f}"),
                    ("MRP", f"₹{product.active_mrp:,.2f}"),
                    ("HSN", product.hsn_sac or "—"),
                    ("GST", f"{product.active_gst_rate:g}%"),
                    ("Status", "Active" if product.is_active else "Inactive"),
                ],
                suffix=f"inv_prod_{product.id}",
            )

    sell_tab, mrp_tab, gst_tab = st.tabs(
        ["Selling price history", "MRP history", "GST rate history"]
    )
    with sell_tab:
        _render_history_tab(
            inventory,
            product_id,
            rate_type="selling",
            title="Selling price",
            list_fn=inventory.list_selling_rate_history,
            value_label="Selling price (₹)",
            key_prefix=f"inv_prod_sell_{product.id}",
        )
    with mrp_tab:
        _render_history_tab(
            inventory,
            product_id,
            rate_type="mrp",
            title="MRP",
            list_fn=inventory.list_mrp_history,
            value_label="MRP (₹)",
            key_prefix=f"inv_prod_mrp_{product.id}",
        )
    with gst_tab:
        _render_history_tab(
            inventory,
            product_id,
            rate_type="gst",
            title="GST rate",
            list_fn=inventory.list_gst_rate_history,
            value_label="GST rate (%)",
            key_prefix=f"inv_prod_gst_{product.id}",
            is_percent=True,
        )

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
