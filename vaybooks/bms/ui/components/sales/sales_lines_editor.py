"""Shared table-based sales line editor with SKU dropdown and rate defaulting."""

from __future__ import annotations

from typing import Any, Optional

import pandas as pd
import streamlit as st

from vaybooks.bms.domain.shared.enums import PartyRegistrationType
from vaybooks.bms.ui.components.sales.sales_line_ui import (
    line_tax_profile,
    preview_sales_line_gst,
    tax_summary_from_previews,
)


def _sku_label(product) -> str:
    return f"{product.sku} — {product.name}"


def _default_rate_for_product(
    product,
    *,
    customer_id: Optional[str],
    use_customer_pricing: bool,
    sales_service,
) -> float:
    if (
        use_customer_pricing
        and customer_id
        and sales_service is not None
        and hasattr(sales_service, "get_customer_rate")
    ):
        customer_rate = sales_service.get_customer_rate(customer_id, product.id)
        if customer_rate is not None and float(customer_rate) > 0:
            return round(float(customer_rate), 2)
    return round(float(getattr(product, "selling_rate", 0) or 0), 2)


def _blank_row(*, show_discount: bool) -> dict[str, Any]:
    row: dict[str, Any] = {
        "SKU": "",
        "Product": "",
        "HSN/SAC": "",
        "Qty": 1.0,
        "Rate": 0.0,
    }
    if show_discount:
        row["Discount"] = 0.0
    row.update(
        {
            "Taxable": 0.0,
            "GST %": 0.0,
            "CGST": 0.0,
            "SGST": 0.0,
            "UTGST": 0.0,
            "IGST": 0.0,
            "Line Total": 0.0,
        }
    )
    return row


def _rows_from_initial(
    initial_lines: list[dict],
    *,
    product_by_id: dict[str, Any],
    label_by_id: dict[str, str],
    qty_field: str,
    show_discount: bool,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in initial_lines or []:
        product_id = str(raw.get("product_id") or "")
        label = label_by_id.get(product_id, "")
        if not label and product_id in product_by_id:
            label = _sku_label(product_by_id[product_id])
        qty = float(
            raw.get(qty_field) or raw.get("qty") or raw.get("qty_ordered") or 1
        )
        rate = float(raw.get("rate") or 0)
        row: dict[str, Any] = _blank_row(show_discount=show_discount)
        row.update({"SKU": label, "Qty": qty, "Rate": rate})
        if show_discount:
            row["Discount"] = float(raw.get("discount") or 0)
        rows.append(row)
    if not rows:
        rows.append(_blank_row(show_discount=show_discount))
    return rows


def render_sales_lines_editor(
    *,
    key_prefix: str,
    products: list,
    initial_lines: Optional[list[dict]] = None,
    customer_id: Optional[str] = None,
    use_customer_pricing: bool = False,
    show_discount: bool = False,
    sales_service=None,
    inventory_service=None,
    business_registered: bool = False,
    business=None,
    business_state_code: str = "",
    customer_state_code: str = "",
    qty_field: str = "qty",
) -> tuple[list[dict], list[str]]:
    """Render an editable SKU/qty/rate table and return normalized lines + GST errors."""
    product_by_id = {item.id: item for item in products}
    label_by_id = {item.id: _sku_label(item) for item in products}
    product_by_label = {_sku_label(item): item for item in products}
    sku_options = [""] + [_sku_label(item) for item in products]

    df_key = f"{key_prefix}_lines_df"
    snapshot_key = f"{key_prefix}_lines_snapshot"
    editor_key = f"{key_prefix}_lines_editor"

    if df_key not in st.session_state:
        seeded = _rows_from_initial(
            list(initial_lines or []),
            product_by_id=product_by_id,
            label_by_id=label_by_id,
            qty_field=qty_field,
            show_discount=show_discount,
        )
        st.session_state[df_key] = seeded
        st.session_state[snapshot_key] = [
            {"sku": row["SKU"], "rate": float(row["Rate"] or 0)} for row in seeded
        ]

    column_config: dict[str, Any] = {
        "SKU": st.column_config.SelectboxColumn(
            "SKU",
            options=sku_options,
            required=False,
            width="large",
        ),
        "Qty": st.column_config.NumberColumn(
            "Qty", min_value=0.0, step=1.0, format="%.2f"
        ),
        "Rate": st.column_config.NumberColumn(
            "Rate", min_value=0.0, step=0.01, format="%.2f"
        ),
        "Product": st.column_config.TextColumn("Product"),
        "HSN/SAC": st.column_config.TextColumn("HSN/SAC"),
        "Taxable": st.column_config.NumberColumn(
            "Taxable", format="₹ %.2f"
        ),
        "GST %": st.column_config.NumberColumn(
            "GST %", format="%.2f"
        ),
        "CGST": st.column_config.NumberColumn(
            "CGST", format="₹ %.2f"
        ),
        "SGST": st.column_config.NumberColumn(
            "SGST", format="₹ %.2f"
        ),
        "UTGST": st.column_config.NumberColumn(
            "UTGST", format="₹ %.2f"
        ),
        "IGST": st.column_config.NumberColumn(
            "IGST", format="₹ %.2f"
        ),
        "Line Total": st.column_config.NumberColumn(
            "Line Total", format="₹ %.2f"
        ),
    }
    if show_discount:
        column_config["Discount"] = st.column_config.NumberColumn(
            "Discount", min_value=0.0, step=0.01, format="%.2f"
        )

    edited_df = st.data_editor(
        pd.DataFrame(st.session_state[df_key]),
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key=editor_key,
        column_config=column_config,
        disabled=[
            "Product",
            "HSN/SAC",
            "Taxable",
            "GST %",
            "CGST",
            "SGST",
            "UTGST",
            "IGST",
            "Line Total",
        ],
    )
    edited_rows = edited_df.to_dict("records") if edited_df is not None else []
    previous = list(st.session_state.get(snapshot_key) or [])

    display_rows: list[dict[str, Any]] = []
    next_snapshot: list[dict[str, Any]] = []
    lines: list[dict] = []
    gst_previews: list[dict] = []
    gst_errors: list[str] = []
    force_refresh = False

    for index, raw in enumerate(edited_rows):
        label = str(raw.get("SKU") or "").strip()
        qty = float(raw.get("Qty") or 0)
        rate = float(raw.get("Rate") or 0)
        discount = float(raw.get("Discount") or 0) if show_discount else 0.0
        product = product_by_label.get(label)
        prev = previous[index] if index < len(previous) else None
        sku_changed = prev is not None and prev.get("sku") != label
        is_new_sku_row = prev is None and bool(label)

        if product is not None and (sku_changed or is_new_sku_row):
            default_rate = _default_rate_for_product(
                product,
                customer_id=customer_id,
                use_customer_pricing=use_customer_pricing,
                sales_service=sales_service,
            )
            if round(rate, 2) != round(default_rate, 2):
                force_refresh = True
            rate = default_rate

        preview = preview_sales_line_gst(
            qty,
            rate,
            discount,
            line_tax_profile(product),
            business_registered=business_registered,
            business=business,
            business_state_code=business_state_code,
            customer_state_code=customer_state_code,
        )
        display_row = _blank_row(show_discount=show_discount)
        display_row.update(
            {
                "SKU": label,
                "Product": product.name if product else "",
                "HSN/SAC": preview["hsn_sac"] if product else "",
                "Qty": qty,
                "Rate": rate,
                "Taxable": preview["taxable_amount"],
                "GST %": preview["gst_rate"],
                "CGST": preview["cgst_amount"],
                "SGST": preview["sgst_amount"],
                "UTGST": preview["utgst_amount"],
                "IGST": preview["igst_amount"],
                "Line Total": preview["line_total"],
            }
        )
        if show_discount:
            display_row["Discount"] = discount
        for computed_key in (
            "Product",
            "HSN/SAC",
            "Taxable",
            "GST %",
            "CGST",
            "SGST",
            "UTGST",
            "IGST",
            "Line Total",
        ):
            if raw.get(computed_key) != display_row[computed_key]:
                force_refresh = True
                break
        display_rows.append(display_row)
        next_snapshot.append({"sku": label, "rate": rate})

        if product is None or qty <= 0:
            continue
        line: dict[str, Any] = {
            "product_id": product.id,
            "product_name": product.name,
            qty_field: qty,
            "rate": rate,
        }
        if show_discount:
            line["discount"] = discount
        if qty_field != "qty":
            line["qty"] = qty
        lines.append(line)
        gst_previews.append(preview)

        if business_registered:
            if rate <= 0:
                gst_errors.append(f"Selling price is required for {product.name}")
            if not preview["hsn_sac"]:
                gst_errors.append(f"HSN/SAC is required for {product.name}")
            regular_registration = (
                business is None
                or business.registration_type == PartyRegistrationType.REGISTERED
            )
            if (
                regular_registration
                and inventory_service
                and not inventory_service.list_gst_rate_history(product.id)
            ):
                gst_errors.append(
                    f"GST rate configuration is required for {product.name}"
                )

    if not display_rows:
        display_rows = [_blank_row(show_discount=show_discount)]
        next_snapshot = [{"sku": "", "rate": 0.0}]

    st.session_state[df_key] = display_rows
    st.session_state[snapshot_key] = next_snapshot
    if force_refresh:
        st.session_state.pop(editor_key, None)
        st.rerun()

    if gst_previews:
        summary = tax_summary_from_previews(gst_previews)
        with st.container(border=True):
            if business_registered:
                metrics = st.columns(4)
                metrics[0].metric("Taxable", f"₹{summary['taxable']:,.2f}")
                if summary["igst"]:
                    metrics[1].metric("IGST", f"₹{summary['igst']:,.2f}")
                else:
                    metrics[1].metric("CGST", f"₹{summary['cgst']:,.2f}")
                metrics[2].metric(
                    "Total GST", f"₹{summary['total_tax']:,.2f}"
                )
                metrics[3].metric(
                    "Grand total", f"₹{summary['grand_total']:,.2f}"
                )
            else:
                st.metric("Total", f"₹{summary['grand_total']:,.2f}")

    return lines, gst_errors
