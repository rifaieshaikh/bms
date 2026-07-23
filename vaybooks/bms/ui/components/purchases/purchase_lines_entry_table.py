"""Product line entry: header + repeating searchable product rows (keyboard-friendly).

Used by purchase order, bill, and return dialogs (products only).
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

import streamlit as st

from vaybooks.bms.domain.shared.enums import CatalogItemType, PartyRegistrationType
from vaybooks.bms.ui.components.common.dialog_state import ensure_selectbox_option
from vaybooks.bms.ui.components.inventory.catalog_item_dialog import CATALOG_ITEM_DIALOG
from vaybooks.bms.ui.components.purchases.purchase_line_ui import (
    default_purchase_rate,
    has_gst_rate_history,
    line_tax_profile,
    preview_line_gst,
    product_label,
    product_lookup_map,
    tax_summary_from_previews,
)

_COL_WEIGHTS_BASE = [2.4, 0.7, 0.8, 0.8, 0.9]
_COL_WEIGHTS_GST = [0.6, 0.7, 0.7, 0.7, 0.7]
_COL_WEIGHTS_TAIL = [0.9, 0.55]


def _money(value: float) -> str:
    return f"₹{float(value or 0):,.2f}"


def _hide_rate_steppers() -> None:
    """Hide +/- steppers on Rate number inputs (keys end with ``_rate``)."""
    st.markdown(
        """
<style>
div[class*="st-key-"][class*="_rate"] input[type="number"]::-webkit-outer-spin-button,
div[class*="st-key-"][class*="_rate"] input[type="number"]::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}
div[class*="st-key-"][class*="_rate"] input[type="number"] {
  -moz-appearance: textfield;
  appearance: textfield;
}
div[class*="st-key-"][class*="_rate"] button {
  display: none !important;
}
</style>
        """,
        unsafe_allow_html=True,
    )


def _col_weights(*, show_gst: bool) -> list[float]:
    weights = list(_COL_WEIGHTS_BASE)
    if show_gst:
        weights.extend(_COL_WEIGHTS_GST)
    weights.extend(_COL_WEIGHTS_TAIL)
    return weights


def _blank_row() -> dict[str, Any]:
    return {
        "uid": uuid.uuid4().hex[:10],
        "item_label": None,
        "qty": 1.0,
        "rate": 0.0,
        "last_item_label": None,
        "landed_cost_alloc": 0.0,
    }


def _product_key(key_prefix: str, uid: str) -> str:
    return f"{key_prefix}_r{uid}_product"


def _qty_key(key_prefix: str, uid: str) -> str:
    return f"{key_prefix}_r{uid}_qty"


def _rate_key(key_prefix: str, uid: str) -> str:
    return f"{key_prefix}_r{uid}_rate"


def _seed_rows(
    initial_lines: list[dict],
    *,
    products: list,
    qty_field: str,
) -> list[dict[str, Any]]:
    label_by_id = {p.id: product_label(p) for p in products}
    rows: list[dict[str, Any]] = []
    for raw in initial_lines or []:
        item_id = str(raw.get("item_id") or raw.get("product_id") or "")
        if not item_id:
            continue
        label = label_by_id.get(item_id) or None
        if label is None:
            product = next((p for p in products if p.id == item_id), None)
            label = product_label(product) if product is not None else None
        qty = float(raw.get(qty_field) or raw.get("qty") or raw.get("qty_ordered") or 1)
        rate = float(raw.get("rate") or 0)
        row = _blank_row()
        row.update(
            {
                "item_label": label,
                "qty": qty if qty > 0 else 1.0,
                "rate": rate,
                "last_item_label": label,
                "landed_cost_alloc": float(raw.get("landed_cost_alloc") or 0),
            }
        )
        rows.append(row)
    rows.append(_blank_row())
    return rows


def _recompute_line(
    *,
    product,
    qty: float,
    rate: float,
    qty_field: str,
    vendor_registered: bool,
    business_state_code: str,
    vendor_state_code: str,
    landed_cost_alloc: float = 0.0,
) -> dict[str, Any]:
    tax_profile = line_tax_profile(product)
    preview = preview_line_gst(
        qty,
        rate,
        tax_profile,
        vendor_registered=vendor_registered,
        business_state_code=business_state_code,
        vendor_state_code=vendor_state_code,
    )
    return {
        "item_type": CatalogItemType.PRODUCT.value,
        "item_id": product.id,
        "item_name": product.name,
        "product_id": product.id,
        "item_label": product_label(product),
        qty_field: qty,
        "qty": qty,
        "rate": rate,
        "taxable_amount": preview["taxable_amount"],
        "cgst_amount": preview["cgst_amount"] if vendor_registered else 0.0,
        "sgst_amount": preview["sgst_amount"] if vendor_registered else 0.0,
        "igst_amount": preview["igst_amount"] if vendor_registered else 0.0,
        "utgst_amount": preview["utgst_amount"] if vendor_registered else 0.0,
        "hsn_sac": preview["hsn_sac"] if vendor_registered else "",
        "gst_rate": preview["gst_rate"] if vendor_registered else 0.0,
        "line_total": preview["line_total"],
        "landed_cost_alloc": landed_cost_alloc,
    }


def _validate_line(
    line: dict[str, Any],
    *,
    vendor_registered: bool,
    business,
    inventory_service,
    gst_history_cache: dict[str, bool],
) -> list[str]:
    errors: list[str] = []
    name = str(line.get("item_name") or "line")
    if float(line.get("rate") or 0) <= 0 and vendor_registered:
        errors.append(f"Purchase rate is required for {name}")
    if vendor_registered and not line.get("hsn_sac"):
        errors.append(f"HSN/SAC is required for {name}")
    regular_registration = (
        business is None
        or getattr(business, "registration_type", None)
        == PartyRegistrationType.REGISTERED
    )
    if (
        vendor_registered
        and regular_registration
        and inventory_service
        and line.get("product_id")
        and not has_gst_rate_history(
            str(line["product_id"]),
            inventory_service=inventory_service,
            gst_history_cache=gst_history_cache,
        )
    ):
        errors.append(f"GST rate configuration is required for {name}")
    return errors


def _clear_row_widget_keys(key_prefix: str, uid: str) -> None:
    for key in (
        _product_key(key_prefix, uid),
        _qty_key(key_prefix, uid),
        _rate_key(key_prefix, uid),
    ):
        st.session_state.pop(key, None)


def render_purchase_lines_entry_table(
    *,
    key_prefix: str,
    products: list,
    initial_lines: Optional[list[dict]] = None,
    vendor_id: Optional[str] = None,
    purchases_service=None,
    inventory_service=None,
    qty_field: str = "qty_ordered",
    vendor_registered: bool = False,
    business=None,
    business_state_code: str = "",
    vendor_state_code: str = "",
    catalog_return_to: Optional[str] = None,
    focus_restore_key: Optional[str] = None,
) -> tuple[list[dict], list[str]]:
    """Render header + repeating product rows; empty product rows are ignored on save."""
    show_gst = bool(vendor_registered)
    rows_key = f"{key_prefix}_rows"
    rate_cache_key = f"{key_prefix}_rate_cache"
    gst_history_cache_key = f"{key_prefix}_gst_history_cache"
    vendor_snap_key = f"{key_prefix}_entry_vendor_snap"
    kb_chain_key = f"{key_prefix}_kb_chain"

    if rate_cache_key not in st.session_state:
        st.session_state[rate_cache_key] = {}
    if gst_history_cache_key not in st.session_state:
        st.session_state[gst_history_cache_key] = {}
    rate_cache: dict[str, float] = st.session_state[rate_cache_key]
    gst_history_cache: dict[str, bool] = st.session_state[gst_history_cache_key]

    if rows_key not in st.session_state:
        st.session_state[rows_key] = _seed_rows(
            list(initial_lines or []),
            products=products,
            qty_field=qty_field,
        )
        st.session_state[vendor_snap_key] = vendor_id

    # Deferred structural mutations (must run before keyed widgets mount).
    delete_uid = st.session_state.pop(f"{key_prefix}_delete_uid", None)
    if delete_uid is not None:
        rows_before = list(st.session_state.get(rows_key) or [])
        del_idx = next(
            (i for i, r in enumerate(rows_before) if r.get("uid") == delete_uid),
            None,
        )
        rows = [r for r in rows_before if r.get("uid") != delete_uid]
        _clear_row_widget_keys(key_prefix, str(delete_uid))
        if not rows:
            rows = [_blank_row()]
        st.session_state[rows_key] = rows
        # After delete, land on the next row's Product (or the new last row).
        if focus_restore_key and rows:
            if del_idx is not None and del_idx < len(rows):
                focus_uid = rows[del_idx]["uid"]
            else:
                focus_uid = rows[-1]["uid"]
            st.session_state[focus_restore_key] = _product_key(
                key_prefix, str(focus_uid)
            )

    append_blank = st.session_state.pop(f"{key_prefix}_append_blank", False)
    if append_blank:
        rows = list(st.session_state.get(rows_key) or [])
        # Ensure a trailing empty row exists; do not steal focus from Qty/Rate.
        if not rows or rows[-1].get("item_label"):
            rows.append(_blank_row())
            st.session_state[rows_key] = rows

    if st.session_state.get(vendor_snap_key) != vendor_id:
        st.session_state[vendor_snap_key] = vendor_id
        rate_cache.clear()
        for row in list(st.session_state.get(rows_key) or []):
            label = row.get("item_label")
            if not label:
                continue
            product = product_lookup_map(products).get(str(label).casefold())
            if product is None:
                continue
            new_rate = default_purchase_rate(
                product,
                item_type=CatalogItemType.PRODUCT.value,
                vendor_id=vendor_id or "",
                purchases_service=purchases_service,
                rate_cache=rate_cache,
            )
            row["rate"] = new_rate
            row["last_item_label"] = None
            st.session_state[_rate_key(key_prefix, row["uid"])] = new_rate

    rows: list[dict[str, Any]] = list(st.session_state.get(rows_key) or [_blank_row()])
    if not rows:
        rows = [_blank_row()]
        st.session_state[rows_key] = rows

    product_options = [product_label(p) for p in products]
    lookup = product_lookup_map(products)
    weights = _col_weights(show_gst=show_gst)

    if catalog_return_to:
        add_cols = st.columns([1, 5])
        if add_cols[0].button("+ Add catalog item", key=f"{key_prefix}_add_catalog"):
            last = rows[-1] if rows else _blank_row()
            st.session_state[CATALOG_ITEM_DIALOG] = {
                "mode": "product",
                "return_to": catalog_return_to,
                "line_index": 0,
                "draft_product_key": _product_key(key_prefix, last["uid"]),
            }
            st.rerun()

    if not products:
        st.warning("No active products in inventory. Add a product before creating lines.")

    _hide_rate_steppers()

    header_labels = ["Product", "Qty", "Rate", "HSN", "Taxable"]
    if show_gst:
        header_labels.extend(["GST %", "CGST", "SGST", "IGST", "UTGST"])
    header_labels.extend(["Total", ""])
    header_cols = st.columns(weights)
    for col, title in zip(header_cols, header_labels):
        col.markdown(f"**{title}**")

    kb_chain: list[str] = []
    col_product: list[str] = []
    col_qty: list[str] = []
    col_rate: list[str] = []
    need_trailing_blank = False
    focus_after_product: str | None = None

    for index, row in enumerate(rows):
        uid = str(row["uid"])
        product_widget_key = _product_key(key_prefix, uid)
        qty_widget_key = _qty_key(key_prefix, uid)
        rate_widget_key = _rate_key(key_prefix, uid)
        kb_chain.extend([product_widget_key, qty_widget_key, rate_widget_key])
        col_product.append(product_widget_key)
        col_qty.append(qty_widget_key)
        col_rate.append(rate_widget_key)

        ensure_selectbox_option(product_widget_key, product_options)
        if product_widget_key not in st.session_state:
            st.session_state[product_widget_key] = row.get("item_label")
        if qty_widget_key not in st.session_state:
            st.session_state[qty_widget_key] = float(row.get("qty") or 1.0)
        if rate_widget_key not in st.session_state:
            st.session_state[rate_widget_key] = float(row.get("rate") or 0.0)

        cols = st.columns(weights)
        with cols[0]:
            selected_label = st.selectbox(
                f"Product {index + 1}",
                options=product_options,
                index=None,
                key=product_widget_key,
                placeholder="Search product by SKU or name…",
                label_visibility="collapsed",
            )

        product = (
            lookup.get(str(selected_label or "").casefold()) if selected_label else None
        )

        if product is not None and selected_label != row.get("last_item_label"):
            default_rate = default_purchase_rate(
                product,
                item_type=CatalogItemType.PRODUCT.value,
                vendor_id=vendor_id or "",
                purchases_service=purchases_service,
                rate_cache=rate_cache,
            )
            if default_rate > 0:
                st.session_state[rate_widget_key] = default_rate
            if float(st.session_state.get(qty_widget_key) or 0) <= 0:
                st.session_state[qty_widget_key] = 1.0
            row["last_item_label"] = selected_label
            row["item_label"] = selected_label
            if index == len(rows) - 1:
                need_trailing_blank = True
                focus_after_product = qty_widget_key

        with cols[1]:
            qty = st.number_input(
                f"Qty {index + 1}",
                min_value=0.0,
                step=1.0,
                format="%.2f",
                key=qty_widget_key,
                label_visibility="collapsed",
            )
        with cols[2]:
            rate = st.number_input(
                f"Rate {index + 1}",
                min_value=0.0,
                step=0.01,
                format="%.2f",
                key=rate_widget_key,
                label_visibility="collapsed",
                help="Ex-GST. Defaults to this vendor's latest purchase rate.",
            )

        if product is not None:
            preview = _recompute_line(
                product=product,
                qty=float(qty or 0),
                rate=float(rate or 0),
                qty_field=qty_field,
                vendor_registered=vendor_registered,
                business_state_code=business_state_code,
                vendor_state_code=vendor_state_code,
                landed_cost_alloc=float(row.get("landed_cost_alloc") or 0),
            )
        else:
            preview = {
                "hsn_sac": "",
                "taxable_amount": 0.0,
                "gst_rate": 0.0,
                "cgst_amount": 0.0,
                "sgst_amount": 0.0,
                "igst_amount": 0.0,
                "utgst_amount": 0.0,
                "line_total": 0.0,
            }

        cols[3].markdown(preview.get("hsn_sac") or "—")
        cols[4].markdown(_money(float(preview.get("taxable_amount") or 0)))
        c = 5
        if show_gst:
            cols[c].markdown(f"{float(preview.get('gst_rate') or 0):.2f}")
            cols[c + 1].markdown(_money(float(preview.get("cgst_amount") or 0)))
            cols[c + 2].markdown(_money(float(preview.get("sgst_amount") or 0)))
            cols[c + 3].markdown(_money(float(preview.get("igst_amount") or 0)))
            cols[c + 4].markdown(_money(float(preview.get("utgst_amount") or 0)))
            c += 5
        cols[c].markdown(_money(float(preview.get("line_total") or 0)))

        if cols[c + 1].button(
            "",
            key=f"{key_prefix}_del_{uid}",
            help="Remove row",
            icon=":material/delete:",
            disabled=product is None,
        ):
            if product is not None:
                st.session_state[f"{key_prefix}_delete_uid"] = uid
                st.rerun()

        row["item_label"] = selected_label
        row["qty"] = float(qty or 0)
        row["rate"] = float(rate or 0)
        rows[index] = row

    st.session_state[rows_key] = rows
    st.session_state[kb_chain_key] = kb_chain
    st.session_state[f"{key_prefix}_kb_columns"] = {
        "product": col_product,
        "qty": col_qty,
        "rate": col_rate,
    }

    if need_trailing_blank:
        st.session_state[f"{key_prefix}_append_blank"] = True
        if focus_restore_key and focus_after_product:
            st.session_state[focus_restore_key] = focus_after_product
        st.rerun()

    # Normalize for save: ignore rows without a selected product.
    gst_errors: list[str] = []
    normalized: list[dict] = []
    previews: list[dict] = []
    for row in rows:
        label = row.get("item_label")
        if not label:
            continue
        product = lookup.get(str(label).casefold())
        if product is None:
            continue
        qty = float(row.get("qty") or 0)
        if qty <= 0:
            continue
        recomputed = _recompute_line(
            product=product,
            qty=qty,
            rate=float(row.get("rate") or 0),
            qty_field=qty_field,
            vendor_registered=vendor_registered,
            business_state_code=business_state_code,
            vendor_state_code=vendor_state_code,
            landed_cost_alloc=float(row.get("landed_cost_alloc") or 0),
        )
        gst_errors.extend(
            _validate_line(
                recomputed,
                vendor_registered=vendor_registered,
                business=business,
                inventory_service=inventory_service,
                gst_history_cache=gst_history_cache,
            )
        )
        normalized.append(recomputed)
        previews.append(
            {
                "taxable_amount": recomputed["taxable_amount"],
                "cgst_amount": recomputed["cgst_amount"],
                "sgst_amount": recomputed["sgst_amount"],
                "igst_amount": recomputed["igst_amount"],
                "utgst_amount": recomputed["utgst_amount"],
                "line_total": recomputed["line_total"],
            }
        )

    if previews:
        summary = tax_summary_from_previews(previews)
        with st.container(border=True):
            if vendor_registered:
                metrics = st.columns(4)
                metrics[0].metric("Taxable", _money(summary["taxable"]))
                if summary["igst"]:
                    metrics[1].metric("IGST", _money(summary["igst"]))
                else:
                    metrics[1].metric("CGST", _money(summary["cgst"]))
                metrics[2].metric("Total GST", _money(summary["total_tax"]))
                metrics[3].metric("Grand total", _money(summary["grand_total"]))
            else:
                st.metric("Total", _money(summary["grand_total"]))

    return normalized, gst_errors


def entry_table_focus_chain(key_prefix: str) -> list[str]:
    """Widget keys for Product/Qty/Rate across current rows (for focus manager)."""
    return list(st.session_state.get(f"{key_prefix}_kb_chain") or [])


def entry_table_focus_columns(key_prefix: str) -> dict[str, list[str]]:
    """Per-column widget keys for vertical ArrowUp/ArrowDown navigation."""
    raw = st.session_state.get(f"{key_prefix}_kb_columns") or {}
    return {
        "product": list(raw.get("product") or []),
        "qty": list(raw.get("qty") or []),
        "rate": list(raw.get("rate") or []),
    }
