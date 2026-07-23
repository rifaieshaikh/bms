"""Product line entry: header + repeating searchable product rows (keyboard-friendly).

Used by sales order, invoice, return, and priced-document dialogs.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

import streamlit as st

from vaybooks.bms.domain.shared.enums import PartyRegistrationType
from vaybooks.bms.ui.components.common.dialog_state import ensure_selectbox_option
from vaybooks.bms.ui.components.sales.sales_line_ui import (
    line_tax_profile,
    preview_sales_line_gst,
    tax_summary_from_previews,
)

_COL_WEIGHTS_BASE = [2.4, 0.7, 0.8]
_COL_WEIGHTS_DISCOUNT = [0.7]
_COL_WEIGHTS_MID = [0.8, 0.9]
_COL_WEIGHTS_GST = [0.6, 0.7, 0.7, 0.7, 0.7]
_COL_WEIGHTS_TAIL = [0.9, 0.55]


def _money(value: float) -> str:
    return f"₹{float(value or 0):,.2f}"


def _sku_label(product) -> str:
    """Selectbox label: name · qty · rate · item code (all searchable)."""
    qty = float(getattr(product, "current_qty", 0) or 0)
    rate = float(
        getattr(product, "active_selling_rate", 0)
        or getattr(product, "selling_rate", 0)
        or 0
    )
    sku = str(getattr(product, "sku", "") or "").strip()
    name = str(getattr(product, "name", "") or "").strip() or "Item"
    label = f"{name} · {qty:g} · ₹{rate:,.2f}"
    if sku:
        label = f"{label} · {sku}"
    return label


def _product_lookup_map(products: list) -> dict[str, Any]:
    """Case-insensitive aliases for label / SKU / name / product → product."""
    lookup: dict[str, Any] = {}
    for product in products:
        aliases = [
            _sku_label(product),
            getattr(product, "sku", None),
            getattr(product, "name", None),
            f"{getattr(product, 'sku', '')} {getattr(product, 'name', '')}".strip(),
            f"{getattr(product, 'name', '')} {getattr(product, 'sku', '')}".strip(),
        ]
        for alias in aliases:
            key = str(alias or "").strip().casefold()
            if key:
                lookup[key] = product
    return lookup


def _default_rate_for_product(
    product,
    *,
    customer_id: Optional[str],
    use_customer_pricing: bool,
    sales_service,
    rate_cache: dict[str, float],
) -> float:
    cache_key = f"{customer_id or ''}::{product.id}"
    if cache_key in rate_cache:
        return rate_cache[cache_key]
    rate = 0.0
    if (
        use_customer_pricing
        and customer_id
        and sales_service is not None
        and hasattr(sales_service, "get_customer_rate")
    ):
        customer_rate = sales_service.get_customer_rate(customer_id, product.id)
        if customer_rate is not None and float(customer_rate) > 0:
            rate = round(float(customer_rate), 2)
    if rate <= 0:
        rate = round(float(getattr(product, "selling_rate", 0) or 0), 2)
    rate_cache[cache_key] = rate
    return rate


def _hide_rate_steppers() -> None:
    """Hide +/- steppers on Rate/Discount number inputs."""
    st.markdown(
        """
<style>
div[class*="st-key-"][class*="_rate"] input[type="number"]::-webkit-outer-spin-button,
div[class*="st-key-"][class*="_rate"] input[type="number"]::-webkit-inner-spin-button,
div[class*="st-key-"][class*="_discount"] input[type="number"]::-webkit-outer-spin-button,
div[class*="st-key-"][class*="_discount"] input[type="number"]::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}
div[class*="st-key-"][class*="_rate"] input[type="number"],
div[class*="st-key-"][class*="_discount"] input[type="number"] {
  -moz-appearance: textfield;
  appearance: textfield;
}
div[class*="st-key-"][class*="_rate"] button,
div[class*="st-key-"][class*="_discount"] button {
  display: none !important;
}
</style>
        """,
        unsafe_allow_html=True,
    )


def _col_weights(*, show_gst: bool, show_discount: bool) -> list[float]:
    weights = list(_COL_WEIGHTS_BASE)
    if show_discount:
        weights.extend(_COL_WEIGHTS_DISCOUNT)
    weights.extend(_COL_WEIGHTS_MID)
    if show_gst:
        weights.extend(_COL_WEIGHTS_GST)
    weights.extend(_COL_WEIGHTS_TAIL)
    return weights


def _blank_row(*, show_discount: bool) -> dict[str, Any]:
    row: dict[str, Any] = {
        "uid": uuid.uuid4().hex[:10],
        "item_label": None,
        "qty": 1.0,
        "rate": 0.0,
        "last_item_label": None,
    }
    if show_discount:
        row["discount"] = 0.0
    return row


def _product_key(key_prefix: str, uid: str) -> str:
    return f"{key_prefix}_r{uid}_product"


def _qty_key(key_prefix: str, uid: str) -> str:
    return f"{key_prefix}_r{uid}_qty"


def _rate_key(key_prefix: str, uid: str) -> str:
    return f"{key_prefix}_r{uid}_rate"


def _discount_key(key_prefix: str, uid: str) -> str:
    return f"{key_prefix}_r{uid}_discount"


def _seed_rows(
    initial_lines: list[dict],
    *,
    products: list,
    qty_field: str,
    show_discount: bool,
) -> list[dict[str, Any]]:
    label_by_id = {p.id: _sku_label(p) for p in products}
    rows: list[dict[str, Any]] = []
    for raw in initial_lines or []:
        item_id = str(raw.get("item_id") or raw.get("product_id") or "")
        if not item_id:
            continue
        label = label_by_id.get(item_id) or None
        if label is None:
            product = next((p for p in products if p.id == item_id), None)
            label = _sku_label(product) if product is not None else None
        qty = float(raw.get(qty_field) or raw.get("qty") or raw.get("qty_ordered") or 1)
        rate = float(raw.get("rate") or 0)
        row = _blank_row(show_discount=show_discount)
        row.update(
            {
                "item_label": label,
                "qty": qty if qty > 0 else 1.0,
                "rate": rate,
                "last_item_label": label,
            }
        )
        if show_discount:
            row["discount"] = float(raw.get("discount") or 0)
        rows.append(row)
    rows.append(_blank_row(show_discount=show_discount))
    return rows


def _recompute_line(
    *,
    product,
    qty: float,
    rate: float,
    discount: float,
    qty_field: str,
    show_discount: bool,
    business_registered: bool,
    business=None,
    business_state_code: str = "",
    customer_state_code: str = "",
) -> dict[str, Any]:
    tax_profile = line_tax_profile(product)
    preview = preview_sales_line_gst(
        qty,
        rate,
        discount if show_discount else 0.0,
        tax_profile,
        business_registered=business_registered,
        business=business,
        business_state_code=business_state_code,
        customer_state_code=customer_state_code,
    )
    line: dict[str, Any] = {
        "product_id": product.id,
        "product_name": product.name,
        "item_label": _sku_label(product),
        qty_field: qty,
        "qty": qty,
        "rate": rate,
        "taxable_amount": preview["taxable_amount"],
        "cgst_amount": preview["cgst_amount"] if business_registered else 0.0,
        "sgst_amount": preview["sgst_amount"] if business_registered else 0.0,
        "igst_amount": preview["igst_amount"] if business_registered else 0.0,
        "utgst_amount": preview["utgst_amount"] if business_registered else 0.0,
        "hsn_sac": preview["hsn_sac"] if business_registered else "",
        "gst_rate": preview["gst_rate"] if business_registered else 0.0,
        "line_total": preview["line_total"],
    }
    if show_discount:
        line["discount"] = discount
    if qty_field != "qty":
        line["qty"] = qty
    return line


def _validate_line(
    line: dict[str, Any],
    *,
    business_registered: bool,
    business,
    inventory_service,
    gst_history_cache: dict[str, bool],
) -> list[str]:
    errors: list[str] = []
    name = str(line.get("product_name") or "line")
    if float(line.get("rate") or 0) <= 0 and business_registered:
        errors.append(f"Selling price is required for {name}")
    if business_registered and not line.get("hsn_sac"):
        errors.append(f"HSN/SAC is required for {name}")
    regular_registration = (
        business is None
        or getattr(business, "registration_type", None)
        == PartyRegistrationType.REGISTERED
    )
    product_id = str(line.get("product_id") or "")
    if (
        business_registered
        and regular_registration
        and inventory_service
        and product_id
    ):
        if product_id not in gst_history_cache:
            gst_history_cache[product_id] = bool(
                inventory_service.list_gst_rate_history(product_id)
            )
        if not gst_history_cache[product_id]:
            errors.append(f"GST rate configuration is required for {name}")
    return errors


def _clear_row_widget_keys(key_prefix: str, uid: str, *, show_discount: bool) -> None:
    keys = [
        _product_key(key_prefix, uid),
        _qty_key(key_prefix, uid),
        _rate_key(key_prefix, uid),
    ]
    if show_discount:
        keys.append(_discount_key(key_prefix, uid))
    for key in keys:
        st.session_state.pop(key, None)


def render_sales_lines_entry_table(
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
    focus_restore_key: Optional[str] = None,
) -> tuple[list[dict], list[str]]:
    """Render header + repeating product rows; empty product rows are ignored on save."""
    show_gst = bool(business_registered)
    rows_key = f"{key_prefix}_rows"
    rate_cache_key = f"{key_prefix}_rate_cache"
    gst_history_cache_key = f"{key_prefix}_gst_history_cache"
    customer_snap_key = f"{key_prefix}_entry_customer_snap"
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
            show_discount=show_discount,
        )
        st.session_state[customer_snap_key] = customer_id

    delete_uid = st.session_state.pop(f"{key_prefix}_delete_uid", None)
    if delete_uid is not None:
        rows_before = list(st.session_state.get(rows_key) or [])
        del_idx = next(
            (i for i, r in enumerate(rows_before) if r.get("uid") == delete_uid),
            None,
        )
        rows = [r for r in rows_before if r.get("uid") != delete_uid]
        _clear_row_widget_keys(key_prefix, str(delete_uid), show_discount=show_discount)
        if not rows:
            rows = [_blank_row(show_discount=show_discount)]
        st.session_state[rows_key] = rows
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
        if not rows or rows[-1].get("item_label"):
            rows.append(_blank_row(show_discount=show_discount))
            st.session_state[rows_key] = rows

    if st.session_state.get(customer_snap_key) != customer_id:
        st.session_state[customer_snap_key] = customer_id
        rate_cache.clear()
        for row in list(st.session_state.get(rows_key) or []):
            label = row.get("item_label")
            if not label:
                continue
            product = _product_lookup_map(products).get(str(label).casefold())
            if product is None:
                continue
            new_rate = _default_rate_for_product(
                product,
                customer_id=customer_id,
                use_customer_pricing=use_customer_pricing,
                sales_service=sales_service,
                rate_cache=rate_cache,
            )
            row["rate"] = new_rate
            row["last_item_label"] = None
            st.session_state[_rate_key(key_prefix, row["uid"])] = new_rate

    rows: list[dict[str, Any]] = list(
        st.session_state.get(rows_key) or [_blank_row(show_discount=show_discount)]
    )
    if not rows:
        rows = [_blank_row(show_discount=show_discount)]
        st.session_state[rows_key] = rows

    product_options = [_sku_label(p) for p in products]
    lookup = _product_lookup_map(products)
    weights = _col_weights(show_gst=show_gst, show_discount=show_discount)

    if not products:
        st.warning("No active products in inventory. Add a product before creating lines.")

    _hide_rate_steppers()

    header_labels = ["Product", "Qty", "Rate"]
    if show_discount:
        header_labels.append("Discount")
    header_labels.extend(["HSN", "Taxable"])
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
    col_discount: list[str] = []
    need_trailing_blank = False
    focus_after_product: str | None = None

    for index, row in enumerate(rows):
        uid = str(row["uid"])
        product_widget_key = _product_key(key_prefix, uid)
        qty_widget_key = _qty_key(key_prefix, uid)
        rate_widget_key = _rate_key(key_prefix, uid)
        discount_widget_key = _discount_key(key_prefix, uid) if show_discount else None

        row_keys = [product_widget_key, qty_widget_key, rate_widget_key]
        if discount_widget_key:
            row_keys.append(discount_widget_key)
        kb_chain.extend(row_keys)
        col_product.append(product_widget_key)
        col_qty.append(qty_widget_key)
        col_rate.append(rate_widget_key)
        if discount_widget_key:
            col_discount.append(discount_widget_key)

        ensure_selectbox_option(product_widget_key, product_options)
        if product_widget_key not in st.session_state:
            st.session_state[product_widget_key] = row.get("item_label")
        if qty_widget_key not in st.session_state:
            st.session_state[qty_widget_key] = float(row.get("qty") or 1.0)
        if rate_widget_key not in st.session_state:
            st.session_state[rate_widget_key] = float(row.get("rate") or 0.0)
        if discount_widget_key and discount_widget_key not in st.session_state:
            st.session_state[discount_widget_key] = float(row.get("discount") or 0.0)

        cols = st.columns(weights)
        with cols[0]:
            selected_label = st.selectbox(
                f"Product {index + 1}",
                options=product_options,
                index=None,
                key=product_widget_key,
                placeholder="Search by name, item code, or product…",
                label_visibility="collapsed",
            )

        product = (
            lookup.get(str(selected_label or "").casefold()) if selected_label else None
        )

        if product is not None and selected_label != row.get("last_item_label"):
            default_rate = _default_rate_for_product(
                product,
                customer_id=customer_id,
                use_customer_pricing=use_customer_pricing,
                sales_service=sales_service,
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
                help="Ex-GST selling rate.",
            )

        c = 3
        discount = 0.0
        if show_discount and discount_widget_key:
            with cols[c]:
                discount = st.number_input(
                    f"Discount {index + 1}",
                    min_value=0.0,
                    step=0.01,
                    format="%.2f",
                    key=discount_widget_key,
                    label_visibility="collapsed",
                )
            c += 1

        if product is not None:
            preview = preview_sales_line_gst(
                float(qty or 0),
                float(rate or 0),
                float(discount or 0) if show_discount else 0.0,
                line_tax_profile(product),
                business_registered=business_registered,
                business=business,
                business_state_code=business_state_code,
                customer_state_code=customer_state_code,
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

        cols[c].markdown(preview.get("hsn_sac") or "—")
        cols[c + 1].markdown(_money(float(preview.get("taxable_amount") or 0)))
        c += 2
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
        if show_discount:
            row["discount"] = float(discount or 0)
        rows[index] = row

    st.session_state[rows_key] = rows
    st.session_state[kb_chain_key] = kb_chain
    columns: dict[str, list[str]] = {
        "product": col_product,
        "qty": col_qty,
        "rate": col_rate,
    }
    if show_discount:
        columns["discount"] = col_discount
    st.session_state[f"{key_prefix}_kb_columns"] = columns
    st.session_state[f"{key_prefix}_show_discount"] = show_discount

    if need_trailing_blank:
        st.session_state[f"{key_prefix}_append_blank"] = True
        if focus_restore_key and focus_after_product:
            st.session_state[focus_restore_key] = focus_after_product
        st.rerun()

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
            discount=float(row.get("discount") or 0),
            qty_field=qty_field,
            show_discount=show_discount,
            business_registered=business_registered,
            business=business,
            business_state_code=business_state_code,
            customer_state_code=customer_state_code,
        )
        gst_errors.extend(
            _validate_line(
                recomputed,
                business_registered=business_registered,
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
            if business_registered:
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
    """Widget keys for Product/Qty/Rate(/Discount) across current rows."""
    return list(st.session_state.get(f"{key_prefix}_kb_chain") or [])


def entry_table_focus_columns(key_prefix: str) -> dict[str, list[str]]:
    """Per-column widget keys for vertical ArrowUp/ArrowDown navigation."""
    raw = st.session_state.get(f"{key_prefix}_kb_columns") or {}
    columns = {
        "product": list(raw.get("product") or []),
        "qty": list(raw.get("qty") or []),
        "rate": list(raw.get("rate") or []),
    }
    if raw.get("discount"):
        columns["discount"] = list(raw.get("discount") or [])
    return columns


def entry_table_grid_roles(key_prefix: str) -> list[str]:
    """Grid roles for the focus engine (includes discount when enabled)."""
    if st.session_state.get(f"{key_prefix}_show_discount"):
        return ["product", "qty", "rate", "discount"]
    return ["product", "qty", "rate"]
