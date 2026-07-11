"""Shared product create/edit form with GST and MRP history."""

from __future__ import annotations

from datetime import date
from typing import Any, Optional
from uuid import uuid4

import streamlit as st

from vaybooks.bms.domain.inventory.entities import InventoryProduct
from vaybooks.bms.domain.shared.item_tax import ProductGstSlab, ProductMrpSlab
from vaybooks.bms.ui.components.custom_fields_renderer import render_custom_fields
from vaybooks.bms.ui.components.unit_picker import render_unit_picker


def _gst_row(gst_rate: float = 0.0, effective_from: date | None = None, is_active: bool = True) -> dict:
    return {
        "id": uuid4().hex,
        "gst_rate": float(gst_rate),
        "effective_from": (effective_from or date.today()).isoformat(),
        "is_active": is_active,
    }


def _mrp_row(mrp: float = 0.0, effective_from: date | None = None, is_active: bool = True) -> dict:
    return {
        "id": uuid4().hex,
        "mrp": float(mrp),
        "effective_from": (effective_from or date.today()).isoformat(),
        "is_active": is_active,
    }


def _spec_row(name: str = "", value: str = "") -> dict:
    return {"name": name, "value": value}


def _init_gst_rows(key: str, existing: list[ProductGstSlab]) -> None:
    if key in st.session_state:
        return
    if existing:
        st.session_state[key] = [
            {
                "id": row.id,
                "gst_rate": float(row.gst_rate),
                "effective_from": row.effective_from.isoformat(),
                "is_active": bool(row.is_active),
            }
            for row in existing
        ]
    else:
        st.session_state[key] = [_gst_row()]


def _init_mrp_rows(key: str, existing: list[ProductMrpSlab]) -> None:
    if key in st.session_state:
        return
    if existing:
        st.session_state[key] = [
            {
                "id": row.id,
                "mrp": float(row.mrp),
                "effective_from": row.effective_from.isoformat(),
                "is_active": bool(row.is_active),
            }
            for row in existing
        ]
    else:
        st.session_state[key] = [_mrp_row()]


def _init_spec_rows(key: str, existing: dict[str, str]) -> None:
    if key in st.session_state:
        return
    if existing:
        st.session_state[key] = [
            {"name": k, "value": v} for k, v in existing.items()
        ]
    else:
        st.session_state[key] = [_spec_row()]


def _set_active(rows: list[dict], active_idx: int) -> None:
    for i, row in enumerate(rows):
        row["is_active"] = i == active_idx


def _parse_rows_to_gst_slabs(rows: list[dict]) -> list[ProductGstSlab]:
    return [
        ProductGstSlab(
            id=row.get("id") or uuid4().hex,
            gst_rate=float(row["gst_rate"]),
            effective_from=date.fromisoformat(str(row["effective_from"])[:10]),
            is_active=bool(row.get("is_active")),
        )
        for row in rows
    ]


def _parse_rows_to_mrp_entries(rows: list[dict]) -> list[ProductMrpSlab]:
    return [
        ProductMrpSlab(
            id=row.get("id") or uuid4().hex,
            mrp=float(row["mrp"]),
            effective_from=date.fromisoformat(str(row["effective_from"])[:10]),
            is_active=bool(row.get("is_active")),
        )
        for row in rows
    ]


def _category_path_options(inventory, categories: list) -> tuple[list[str], dict[str, str]]:
    labels: list[str] = []
    id_by_label: dict[str, str] = {}
    for category in categories:
        path = inventory.get_category_path(category.id)
        label = path or category.name
        if label in id_by_label:
            label = f"{label} [{category.id[:8]}]"
        labels.append(label)
        id_by_label[label] = category.id
    return sorted(labels), id_by_label


def render_product_form(
    *,
    inventory,
    key_prefix: str,
    categories: list,
    existing: Optional[InventoryProduct] = None,
    show_opening_qty: bool = False,
    show_active: bool = False,
    submit_label: str = "Save Product",
) -> Optional[dict[str, Any]]:
    """Render product fields. Returns form payload when submit is clicked."""
    path_labels, id_by_label = _category_path_options(inventory, categories)
    default_paths: list[str] = []
    if existing:
        for cid in existing.category_ids:
            for label, cat_id in id_by_label.items():
                if cat_id == cid:
                    default_paths.append(label)
                    break

    gst_key = f"{key_prefix}_gst_rows"
    mrp_key = f"{key_prefix}_mrp_rows"
    spec_key = f"{key_prefix}_spec_rows"
    _init_gst_rows(gst_key, list(existing.gst_rates) if existing else [])
    _init_mrp_rows(mrp_key, list(existing.mrp_entries) if existing else [])
    _init_spec_rows(spec_key, dict(existing.specifications) if existing else {})

    st.markdown("**Basic**")
    cols = st.columns(2)
    sku = cols[0].text_input(
        "SKU",
        value=existing.sku if existing else "",
        key=f"{key_prefix}_sku",
    )
    name = cols[1].text_input(
        "Product name",
        value=existing.name if existing else "",
        key=f"{key_prefix}_name",
    )

    selected_paths = st.multiselect(
        "Categories",
        path_labels,
        default=default_paths,
        key=f"{key_prefix}_categories",
    )
    category_ids = [id_by_label[p] for p in selected_paths if p in id_by_label]

    unit_id = render_unit_picker(
        inventory,
        key_prefix=key_prefix,
        selected_unit_id=existing.unit_id if existing else "",
    )

    st.markdown("**Specifications**")
    spec_rows = list(st.session_state[spec_key])
    spec_remove = None
    for i, row in enumerate(spec_rows):
        s_cols = st.columns([2, 2, 1])
        row["name"] = s_cols[0].text_input(
            "Name",
            value=row.get("name", ""),
            key=f"{key_prefix}_spec_name_{i}",
            label_visibility="collapsed",
            placeholder="Name",
        )
        row["value"] = s_cols[1].text_input(
            "Value",
            value=row.get("value", ""),
            key=f"{key_prefix}_spec_val_{i}",
            label_visibility="collapsed",
            placeholder="Value",
        )
        if len(spec_rows) > 1 and s_cols[2].button("Remove", key=f"{key_prefix}_spec_rm_{i}"):
            spec_remove = i
        spec_rows[i] = row
    if spec_remove is not None:
        spec_rows.pop(spec_remove)
        st.session_state[spec_key] = spec_rows or [_spec_row()]
        st.rerun()
    if st.button("+ Add specification", key=f"{key_prefix}_spec_add"):
        spec_rows.append(_spec_row())
        st.session_state[spec_key] = spec_rows
        st.rerun()
    st.session_state[spec_key] = spec_rows

    field_defs = inventory.list_field_definitions(active_only=True)
    custom_values = render_custom_fields(
        field_defs,
        category_ids=category_ids,
        values=existing.custom_fields if existing else {},
        key_prefix=key_prefix,
    )

    st.markdown("**Tax**")
    hsn_sac = st.text_input(
        "HSN",
        value=existing.hsn_sac if existing else "",
        key=f"{key_prefix}_hsn",
    )

    st.markdown("**GST rates**")
    gst_rows = list(st.session_state[gst_key])
    gst_remove = None
    gst_active_pick = None
    for i, row in enumerate(gst_rows):
        with st.container(border=True):
            g_cols = st.columns([2, 2, 1, 1])
            row["gst_rate"] = g_cols[0].number_input(
                "GST rate (%)",
                min_value=0.0,
                max_value=100.0,
                value=float(row.get("gst_rate") or 0),
                key=f"{key_prefix}_gst_rate_{i}",
            )
            eff = g_cols[1].date_input(
                "Effective from",
                value=date.fromisoformat(str(row["effective_from"])[:10]),
                key=f"{key_prefix}_gst_eff_{i}",
            )
            row["effective_from"] = eff.isoformat()
            if g_cols[2].radio(
                "Active",
                ["Yes", "No"],
                index=0 if row.get("is_active") else 1,
                key=f"{key_prefix}_gst_active_{i}",
                horizontal=True,
            ) == "Yes":
                gst_active_pick = i
            if len(gst_rows) > 1 and g_cols[3].button("Remove", key=f"{key_prefix}_gst_rm_{i}"):
                gst_remove = i
        gst_rows[i] = row
    if gst_active_pick is not None:
        _set_active(gst_rows, gst_active_pick)
    if gst_remove is not None:
        gst_rows.pop(gst_remove)
        if not any(r.get("is_active") for r in gst_rows) and gst_rows:
            gst_rows[0]["is_active"] = True
        st.session_state[gst_key] = gst_rows
        st.rerun()
    if st.button("+ Add GST rate", key=f"{key_prefix}_gst_add"):
        for row in gst_rows:
            row["is_active"] = False
        gst_rows.append(_gst_row(is_active=True))
        st.session_state[gst_key] = gst_rows
        st.rerun()
    st.session_state[gst_key] = gst_rows

    st.markdown("**MRP**")
    mrp_rows = list(st.session_state[mrp_key])
    mrp_remove = None
    mrp_active_pick = None
    for i, row in enumerate(mrp_rows):
        with st.container(border=True):
            m_cols = st.columns([2, 2, 1, 1])
            row["mrp"] = m_cols[0].number_input(
                "MRP (₹)",
                min_value=0.0,
                value=float(row.get("mrp") or 0),
                key=f"{key_prefix}_mrp_val_{i}",
            )
            eff = m_cols[1].date_input(
                "Effective from",
                value=date.fromisoformat(str(row["effective_from"])[:10]),
                key=f"{key_prefix}_mrp_eff_{i}",
            )
            row["effective_from"] = eff.isoformat()
            if m_cols[2].radio(
                "Active",
                ["Yes", "No"],
                index=0 if row.get("is_active") else 1,
                key=f"{key_prefix}_mrp_active_{i}",
                horizontal=True,
            ) == "Yes":
                mrp_active_pick = i
            if len(mrp_rows) > 1 and m_cols[3].button("Remove", key=f"{key_prefix}_mrp_rm_{i}"):
                mrp_remove = i
        mrp_rows[i] = row
    if mrp_active_pick is not None:
        _set_active(mrp_rows, mrp_active_pick)
    if mrp_remove is not None:
        mrp_rows.pop(mrp_remove)
        if not any(r.get("is_active") for r in mrp_rows) and mrp_rows:
            mrp_rows[0]["is_active"] = True
        st.session_state[mrp_key] = mrp_rows
        st.rerun()
    if st.button("+ Add MRP", key=f"{key_prefix}_mrp_add"):
        for row in mrp_rows:
            row["is_active"] = False
        mrp_rows.append(_mrp_row(is_active=True))
        st.session_state[mrp_key] = mrp_rows
        st.rerun()
    st.session_state[mrp_key] = mrp_rows

    st.markdown("**Pricing**")
    selling_rate = st.number_input(
        "Selling rate (ex-GST) (₹)",
        min_value=0.0,
        value=float(existing.selling_rate) if existing else 0.0,
        key=f"{key_prefix}_sell",
    )

    opening_qty = 0.0
    if show_opening_qty:
        opening_qty = st.number_input(
            "Opening qty",
            min_value=0.0,
            value=0.0,
            key=f"{key_prefix}_opening",
        )

    is_active = True
    if show_active:
        is_active = st.checkbox(
            "Active",
            value=existing.is_active if existing else True,
            key=f"{key_prefix}_active",
        )

    if st.button(submit_label, type="primary", key=f"{key_prefix}_submit"):
        specifications = {
            row["name"].strip(): row["value"].strip()
            for row in st.session_state[spec_key]
            if row.get("name", "").strip() and row.get("value", "").strip()
        }
        return {
            "sku": sku.strip(),
            "name": name.strip(),
            "category_ids": category_ids,
            "unit_id": unit_id,
            "hsn_sac": hsn_sac.strip(),
            "gst_rates": _parse_rows_to_gst_slabs(st.session_state[gst_key]),
            "mrp_entries": _parse_rows_to_mrp_entries(st.session_state[mrp_key]),
            "selling_rate": float(selling_rate),
            "opening_qty": float(opening_qty),
            "is_active": is_active,
            "specifications": specifications,
            "custom_fields": custom_values,
        }
    return None


def clear_product_form_state(key_prefix: str) -> None:
    for key in list(st.session_state.keys()):
        if key.startswith(key_prefix):
            st.session_state.pop(key, None)
