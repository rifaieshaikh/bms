"""Shared table-based purchase line editor (sibling of sales_lines_editor).

The Item cell accepts a SKU, product name, service name, or the canonical
``SKU — Product`` label. Existing catalog entries resolve immediately. Unknown
text remains in the row and offers a row-specific catalog creation action.
"""

from __future__ import annotations

import math
from typing import Any, Optional

import pandas as pd
import streamlit as st

from vaybooks.bms.domain.shared.enums import CatalogItemType, PartyRegistrationType
from vaybooks.bms.ui.components.inventory.catalog_item_dialog import CATALOG_ITEM_DIALOG
from vaybooks.bms.ui.components.purchases.purchase_line_ui import (
    line_tax_profile,
    preview_line_gst,
    tax_summary_from_previews,
)


def _product_label(product) -> str:
    return f"{product.sku} — {product.name}"


def _service_label(service) -> str:
    return str(service.service_name or "")


def _lookup_key(value: object) -> str:
    return _as_text(value).casefold()


def _as_float(value: object, default: float = 0.0) -> float:
    """Coerce editor/pandas values to float; treat blank/NaN/Inf as default."""
    try:
        if value is None or (isinstance(value, str) and not value.strip()):
            return default
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    if math.isnan(number) or math.isinf(number):
        return default
    return number


def _as_text(value: object) -> str:
    """Coerce editor/pandas cell values to a clean string."""
    try:
        if value is None or pd.isna(value):
            return ""
    except (TypeError, ValueError):
        if value is None:
            return ""
    text = str(value).strip()
    if text.casefold() in {"nan", "none", "<na>"}:
        return ""
    return text


def _looks_numeric(value: object) -> bool:
    """True for ints/floats/blanks/NaN and numeric strings (editor number cells)."""
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    try:
        if value is None or pd.isna(value):
            return True
    except (TypeError, ValueError):
        if value is None:
            return True
    text = _as_text(value)
    if text == "":
        return True
    try:
        float(text)
        return True
    except ValueError:
        return False


def _values_equal(left: object, right: object) -> bool:
    """Equality that treats blank/NaN as empty and compares numerics loosely."""
    if _looks_numeric(left) and _looks_numeric(right):
        return abs(_as_float(left) - _as_float(right)) < 1e-9
    return _as_text(left) == _as_text(right)


def _item_lookup_maps(products: list, services: list) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build case-insensitive aliases for SKU/name/canonical item labels."""
    product_lookup: dict[str, Any] = {}
    for product in products:
        for alias in (_product_label(product), product.sku, product.name):
            key = _lookup_key(alias)
            if key:
                product_lookup[key] = product

    service_lookup: dict[str, Any] = {}
    for service in services:
        key = _lookup_key(_service_label(service))
        if key:
            service_lookup[key] = service
    return product_lookup, service_lookup


def _blank_row(*, show_type: bool, show_gst: bool = True) -> dict[str, Any]:
    row: dict[str, Any] = {}
    if show_type:
        row["Type"] = CatalogItemType.PRODUCT.value
    row.update(
        {
            "Item": "",
            "Name": "",
            "HSN/SAC": "",
            "Qty": 1.0,
            "Rate": 0.0,
            "Taxable": 0.0,
        }
    )
    if show_gst:
        row.update(
            {
                "GST %": 0.0,
                "CGST": 0.0,
                "SGST": 0.0,
                "UTGST": 0.0,
                "IGST": 0.0,
            }
        )
    row["Line Total"] = 0.0
    return row


def _rows_from_initial(
    initial_lines: list[dict],
    *,
    label_by_id: dict[str, str],
    qty_field: str,
    show_type: bool,
    show_gst: bool,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in initial_lines or []:
        item_type = str(raw.get("item_type") or CatalogItemType.PRODUCT.value)
        item_id = str(raw.get("item_id") or raw.get("product_id") or "")
        label = label_by_id.get(item_id, "")
        qty = _as_float(
            raw.get(qty_field) or raw.get("qty") or raw.get("qty_ordered"),
            1.0,
        )
        rate = _as_float(raw.get("rate"))
        row = _blank_row(show_type=show_type, show_gst=show_gst)
        if show_type:
            row["Type"] = item_type
        row.update({"Item": label, "Qty": qty, "Rate": rate})
        rows.append(row)
    if not rows:
        rows.append(_blank_row(show_type=show_type, show_gst=show_gst))
    return rows


def _default_purchase_rate(
    item,
    *,
    item_type: str,
    vendor_id: str,
    purchases_service,
) -> float:
    """Resolve default ex-GST rate: vendor history → last purchase → selling."""
    if (
        purchases_service is not None
        and hasattr(purchases_service, "get_latest_purchase_rate")
    ):
        latest = purchases_service.get_latest_purchase_rate(
            CatalogItemType(item_type),
            item.id,
            vendor_id or "",
        )
        if latest is not None and float(latest) > 0:
            return round(float(latest), 2)

    if item_type == CatalogItemType.PRODUCT.value:
        for attr in ("last_purchase_rate", "active_selling_rate", "selling_rate"):
            value = float(getattr(item, attr, 0) or 0)
            if value > 0:
                return round(value, 2)
    return 0.0


def render_purchase_lines_editor(
    *,
    key_prefix: str,
    products: list,
    services: Optional[list] = None,
    initial_lines: Optional[list[dict]] = None,
    vendor_id: Optional[str] = None,
    purchases_service=None,
    inventory_service=None,
    allow_services: bool = True,
    qty_field: str = "qty",
    vendor_registered: bool = False,
    business=None,
    business_state_code: str = "",
    vendor_state_code: str = "",
    catalog_return_to: Optional[str] = None,
) -> tuple[list[dict], list[str]]:
    """Render editable purchase lines; return normalized dicts + validation errors.

    When ``allow_services`` is False (PO / return), Type is omitted, Item is a
    selectbox of active products, and only products appear as options.
    When ``allow_services`` is True (bills), Item stays free-text so unknown
    catalog names can be created inline.
    """
    services = list(services or [])
    show_type = allow_services
    show_gst = bool(vendor_registered)

    product_label_by_id = {item.id: _product_label(item) for item in products}
    service_label_by_id = {item.id: _service_label(item) for item in services}
    label_by_id = {**product_label_by_id, **service_label_by_id}

    product_lookup, service_lookup = _item_lookup_maps(products, services)

    df_key = f"{key_prefix}_lines_df"
    snapshot_key = f"{key_prefix}_lines_snapshot"
    editor_key = f"{key_prefix}_lines_editor"
    vendor_snap_key = f"{key_prefix}_vendor_snap"
    gst_snap_key = f"{key_prefix}_gst_snap"

    if df_key not in st.session_state:
        seeded = _rows_from_initial(
            list(initial_lines or []),
            label_by_id=label_by_id,
            qty_field=qty_field,
            show_type=show_type,
            show_gst=show_gst,
        )
        st.session_state[df_key] = seeded
        st.session_state[snapshot_key] = [
            {
                "type": row.get("Type", CatalogItemType.PRODUCT.value),
                "item": row["Item"],
                "rate": float(row["Rate"] or 0),
            }
            for row in seeded
        ]
        st.session_state[vendor_snap_key] = vendor_id
        st.session_state[gst_snap_key] = show_gst

    # Vendor change: refresh rates for selected items
    if st.session_state.get(vendor_snap_key) != vendor_id:
        st.session_state[vendor_snap_key] = vendor_id
        force_vendor_rate = True
    else:
        force_vendor_rate = False

    # Registration change: rebuild columns (GST visible only for registered vendors)
    if st.session_state.get(gst_snap_key) != show_gst:
        rebuilt = []
        for row in list(st.session_state.get(df_key) or []):
            rebuilt_row = _blank_row(show_type=show_type, show_gst=show_gst)
            if show_type:
                rebuilt_row["Type"] = row.get("Type", CatalogItemType.PRODUCT.value)
            rebuilt_row.update(
                {
                    "Item": _as_text(row.get("Item")),
                    "Name": _as_text(row.get("Name")),
                    "HSN/SAC": _as_text(row.get("HSN/SAC")) if show_gst else "",
                    "Qty": _as_float(row.get("Qty"), 1.0),
                    "Rate": _as_float(row.get("Rate")),
                }
            )
            rebuilt.append(rebuilt_row)
        if not rebuilt:
            rebuilt = [_blank_row(show_type=show_type, show_gst=show_gst)]
        st.session_state[df_key] = rebuilt
        st.session_state[gst_snap_key] = show_gst
        st.session_state.pop(editor_key, None)
        st.rerun()

    # Product-only editors (PO / return) use a searchable select of active products.
    # Bill editors keep free-text Item so unknown catalog names can be created inline.
    use_item_select = not allow_services
    item_select_options = [""] + [_product_label(item) for item in products]

    if use_item_select:
        # Drop stale Item values that are no longer in the option list (Streamlit
        # SelectboxColumn errors or blanks when the cell value is not in options).
        sanitized_rows = []
        changed_options = False
        for row in list(st.session_state.get(df_key) or []):
            sanitized = dict(row)
            item_label = _as_text(sanitized.get("Item"))
            if item_label and item_label not in item_select_options:
                sanitized["Item"] = ""
                changed_options = True
            sanitized_rows.append(sanitized)
        if changed_options:
            st.session_state[df_key] = sanitized_rows or [
                _blank_row(show_type=show_type, show_gst=show_gst)
            ]
            st.session_state.pop(editor_key, None)
        if not products:
            st.warning("No active products in inventory. Add a product before creating lines.")


    column_config: dict[str, Any] = {}
    if show_type:
        column_config["Type"] = st.column_config.SelectboxColumn(
            "Type",
            options=[CatalogItemType.PRODUCT.value, CatalogItemType.SERVICE.value],
            required=True,
            width="small",
        )
    if use_item_select:
        item_column = st.column_config.SelectboxColumn(
            "Item",
            options=item_select_options,
            required=False,
            width="large",
            help="Select an active product (SKU — name). Use + Add catalog item for a new product.",
        )
    else:
        item_column = st.column_config.TextColumn(
            "Item",
            required=False,
            width="large",
            help="Type an existing SKU/name, or enter a new item and create it below.",
        )
    column_config.update(
        {
            "Item": item_column,
            "Qty": st.column_config.NumberColumn(
                "Qty", min_value=0.0, step=1.0, format="%.2f"
            ),
            "Rate": st.column_config.NumberColumn(
                "Rate",
                min_value=0.0,
                step=0.01,
                format="%.2f",
                help="Ex-GST. Defaults to this vendor's latest purchase rate.",
            ),
            "Name": st.column_config.TextColumn("Name"),
            "HSN/SAC": st.column_config.TextColumn("HSN/SAC"),
            "Taxable": st.column_config.NumberColumn("Taxable", format="₹ %.2f"),
            "Line Total": st.column_config.NumberColumn(
                "Line Total", format="₹ %.2f"
            ),
        }
    )
    if show_gst:
        column_config.update(
            {
                "GST %": st.column_config.NumberColumn("GST %", format="%.2f"),
                "CGST": st.column_config.NumberColumn("CGST", format="₹ %.2f"),
                "SGST": st.column_config.NumberColumn("SGST", format="₹ %.2f"),
                "UTGST": st.column_config.NumberColumn("UTGST", format="₹ %.2f"),
                "IGST": st.column_config.NumberColumn("IGST", format="₹ %.2f"),
            }
        )

    if catalog_return_to:
        add_cols = st.columns([1, 4])
        if add_cols[0].button("+ Add catalog item", key=f"{key_prefix}_add_catalog"):
            st.session_state[CATALOG_ITEM_DIALOG] = {
                "mode": "product",
                "return_to": catalog_return_to,
                "line_index": 0,
                "editor_df_key": df_key,
                "editor_key": editor_key,
            }
            st.rerun()

    disabled_cols = ["Name", "HSN/SAC", "Taxable", "Line Total"]
    if show_gst:
        disabled_cols.extend(["GST %", "CGST", "SGST", "UTGST", "IGST"])

    edited_df = st.data_editor(
        pd.DataFrame(st.session_state[df_key]),
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key=editor_key,
        column_config=column_config,
        disabled=disabled_cols,
    )
    edited_rows = edited_df.to_dict("records") if edited_df is not None else []
    previous = list(st.session_state.get(snapshot_key) or [])

    display_rows: list[dict[str, Any]] = []
    next_snapshot: list[dict[str, Any]] = []
    lines: list[dict] = []
    gst_previews: list[dict] = []
    gst_errors: list[str] = []
    unknown_items: list[dict[str, Any]] = []
    force_refresh = force_vendor_rate

    for index, raw in enumerate(edited_rows):
        item_type = (
            (_as_text(raw.get("Type")) or CatalogItemType.PRODUCT.value)
            if show_type
            else CatalogItemType.PRODUCT.value
        )
        label = _as_text(raw.get("Item"))
        qty = _as_float(raw.get("Qty"))
        rate = _as_float(raw.get("Rate"))

        lookup_key = _lookup_key(label)
        product = product_lookup.get(lookup_key)
        service = service_lookup.get(lookup_key) if allow_services else None
        item = None
        if (
            item_type == CatalogItemType.PRODUCT.value
            and product is not None
        ):
            item = product
        elif (
            item_type == CatalogItemType.SERVICE.value
            and service is not None
        ):
            item = service

        if item is not None:
            canonical_label = (
                _product_label(item)
                if item_type == CatalogItemType.PRODUCT.value
                else _service_label(item)
            )
            if label != canonical_label:
                label = canonical_label
                force_refresh = True
        elif label:
            unknown_items.append(
                {"index": index, "item_type": item_type, "text": label}
            )
            gst_errors.append(
                f'Create or select the {item_type.lower()} "{label}" on row {index + 1}'
            )

        prev = previous[index] if index < len(previous) else None
        item_changed = prev is not None and (
            prev.get("item") != label or prev.get("type") != item_type
        )
        is_new_item_row = prev is None and bool(label)

        if item is not None and (
            item_changed or is_new_item_row or force_vendor_rate
        ):
            if qty <= 0:
                qty = 1.0
                force_refresh = True
            default_rate = _default_purchase_rate(
                item,
                item_type=item_type,
                vendor_id=vendor_id or "",
                purchases_service=purchases_service,
            )
            if default_rate > 0 and round(rate, 2) != round(default_rate, 2):
                rate = default_rate
                force_refresh = True
            elif default_rate == 0.0 and (item_changed or is_new_item_row):
                # No purchase/selling history: leave rate as user typed, or 0
                pass

        tax_profile = line_tax_profile(item)
        preview = preview_line_gst(
            qty,
            rate,
            tax_profile,
            vendor_registered=vendor_registered,
            business_state_code=business_state_code,
            vendor_state_code=vendor_state_code,
        )
        name = ""
        if item is not None:
            name = (
                item.name
                if item_type == CatalogItemType.PRODUCT.value
                else getattr(item, "service_name", "")
            )

        display_row = _blank_row(show_type=show_type, show_gst=show_gst)
        if show_type:
            display_row["Type"] = item_type
        # Always surface HSN/SAC from the catalog item (even when GST columns are hidden).
        hsn_sac = tax_profile.hsn_sac if item is not None else ""
        display_row.update(
            {
                "Item": label,
                "Name": name,
                "HSN/SAC": hsn_sac,
                "Qty": qty,
                "Rate": rate,
                "Taxable": preview["taxable_amount"],
                "Line Total": preview["line_total"],
            }
        )
        if show_gst:
            display_row.update(
                {
                    "GST %": preview["gst_rate"],
                    "CGST": preview["cgst_amount"],
                    "SGST": preview["sgst_amount"],
                    "UTGST": preview["utgst_amount"],
                    "IGST": preview["igst_amount"],
                }
            )
        computed_keys = ["Name", "HSN/SAC", "Taxable", "Line Total", "Item", "Rate"]
        if show_gst:
            computed_keys.extend(["GST %", "CGST", "SGST", "UTGST", "IGST"])
        for computed_key in computed_keys:
            if not _values_equal(raw.get(computed_key), display_row.get(computed_key)):
                force_refresh = True
                break
        display_rows.append(display_row)
        next_snapshot.append({"type": item_type, "item": label, "rate": rate})

        if item is None or qty <= 0:
            continue

        line: dict[str, Any] = {
            "item_type": item_type,
            "item_id": item.id,
            "item_name": name,
            "product_id": item.id if item_type == CatalogItemType.PRODUCT.value else None,
            qty_field: qty,
            "qty": qty,
            "rate": rate,
            "taxable_amount": preview["taxable_amount"],
            "cgst_amount": preview["cgst_amount"] if show_gst else 0.0,
            "sgst_amount": preview["sgst_amount"] if show_gst else 0.0,
            "igst_amount": preview["igst_amount"] if show_gst else 0.0,
            "utgst_amount": preview["utgst_amount"] if show_gst else 0.0,
            "hsn_sac": preview["hsn_sac"] if show_gst else "",
            "line_total": preview["line_total"],
            "landed_cost_alloc": 0.0,
        }
        if qty_field == "qty_ordered":
            line["qty_ordered"] = qty
        # Preserve landed_cost_alloc from seeded initial by item key when possible
        if initial_lines:
            for seeded in initial_lines:
                seeded_id = str(seeded.get("item_id") or seeded.get("product_id") or "")
                if seeded_id == item.id:
                    line["landed_cost_alloc"] = _as_float(
                        seeded.get("landed_cost_alloc")
                    )
                    break
        lines.append(line)
        gst_previews.append(preview)

        if vendor_registered:
            if rate <= 0:
                gst_errors.append(f"Purchase rate is required for {name}")
            if not preview["hsn_sac"]:
                gst_errors.append(f"HSN/SAC is required for {name}")
            regular_registration = (
                business is None
                or getattr(business, "registration_type", None)
                == PartyRegistrationType.REGISTERED
            )
            if (
                regular_registration
                and item_type == CatalogItemType.PRODUCT.value
                and inventory_service
                and not inventory_service.list_gst_rate_history(item.id)
            ):
                gst_errors.append(
                    f"GST rate configuration is required for {name}"
                )

    if not display_rows:
        display_rows = [_blank_row(show_type=show_type, show_gst=show_gst)]
        next_snapshot = [
            {"type": CatalogItemType.PRODUCT.value, "item": "", "rate": 0.0}
        ]

    st.session_state[df_key] = display_rows
    st.session_state[snapshot_key] = next_snapshot

    if unknown_items:
        st.warning("Some entered items do not exist in the catalog yet.")
        for unknown in unknown_items:
            item_type = unknown["item_type"]
            text = unknown["text"]
            if not catalog_return_to:
                continue
            mode = (
                "service"
                if item_type == CatalogItemType.SERVICE.value
                else "product"
            )
            if st.button(
                f'Create {item_type}: {text}',
                key=f"{key_prefix}_create_unknown_{unknown['index']}",
            ):
                st.session_state[CATALOG_ITEM_DIALOG] = {
                    "mode": mode,
                    "return_to": catalog_return_to or key_prefix,
                    "line_index": unknown["index"],
                    "editor_df_key": df_key,
                    "editor_key": editor_key,
                    "prefill_text": text,
                }
                st.rerun()

    if force_refresh:
        st.session_state.pop(editor_key, None)
        st.rerun()

    if gst_previews:
        summary = tax_summary_from_previews(gst_previews)
        with st.container(border=True):
            if vendor_registered:
                metrics = st.columns(4)
                metrics[0].metric("Taxable", f"₹{summary['taxable']:,.2f}")
                if summary["igst"]:
                    metrics[1].metric("IGST", f"₹{summary['igst']:,.2f}")
                else:
                    metrics[1].metric("CGST", f"₹{summary['cgst']:,.2f}")
                metrics[2].metric("Total GST", f"₹{summary['total_tax']:,.2f}")
                metrics[3].metric(
                    "Grand total", f"₹{summary['grand_total']:,.2f}"
                )
            else:
                st.metric("Total", f"₹{summary['grand_total']:,.2f}")

    return lines, gst_errors
