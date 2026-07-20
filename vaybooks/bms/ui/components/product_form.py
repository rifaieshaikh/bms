"""Shared product create/edit form."""

from __future__ import annotations

from typing import Any, Optional
from uuid import uuid4

import streamlit as st

from vaybooks.bms.domain.business.entities import BusinessProfile
from vaybooks.bms.domain.inventory.entities import InventoryProduct
from vaybooks.bms.domain.shared.enums import PartyRegistrationType
from vaybooks.bms.ui.components.category_picker import render_category_picker
from vaybooks.bms.ui.components.custom_fields_renderer import render_custom_fields
from vaybooks.bms.ui.components.unit_picker import render_unit_picker


def _spec_row(name: str = "", value: str = "") -> dict:
    return {"name": name, "value": value}


def _init_spec_rows(key: str, existing: dict[str, str]) -> None:
    if key in st.session_state:
        return
    if existing:
        st.session_state[key] = [{"name": k, "value": v} for k, v in existing.items()]
    else:
        st.session_state[key] = [_spec_row()]


def render_product_form(
    *,
    inventory,
    key_prefix: str,
    existing: Optional[InventoryProduct] = None,
    categories: list | None = None,
    business: Optional[BusinessProfile] = None,
    show_opening_qty: bool = False,
    show_active: bool = False,
    submit_label: str = "Save Product",
) -> Optional[dict[str, Any]]:
    """Render product fields. Returns form payload when submit is clicked."""
    _ = categories
    spec_key = f"{key_prefix}_spec_rows"
    _init_spec_rows(spec_key, dict(existing.specifications) if existing else {})

    registered = bool(
        business
        and business.registration_type == PartyRegistrationType.REGISTERED
    )

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

    st.markdown("**Categories**")
    category_pick = render_category_picker(
        inventory,
        key_prefix=key_prefix,
        selected_ids=list(existing.category_ids) if existing else [],
        active_only=True,
    )

    st.markdown("**Unit**")
    unit_pick = render_unit_picker(
        inventory,
        key_prefix=key_prefix,
        selected_unit_id=existing.unit_id if existing else "",
    )

    st.markdown("**Pricing**")
    sell_default = float(existing.active_selling_rate if existing else 0.0)
    mrp_default = float(existing.active_mrp if existing else 0.0)
    gst_default = float(existing.active_gst_rate if existing else 0.0)
    purchase_default = float(existing.last_purchase_rate if existing else 0.0)

    price_cols = st.columns(2)
    selling_rate = price_cols[0].number_input(
        "Selling price (ex-GST) (₹)",
        min_value=0.0,
        value=sell_default,
        key=f"{key_prefix}_sell",
    )
    purchase_rate = price_cols[1].number_input(
        "Purchase price (ex-GST) (₹)",
        min_value=0.0,
        value=purchase_default,
        key=f"{key_prefix}_purchase",
        help="Active purchase price. Vendor-specific latest rates from bills override this when loading lines.",
    )
    price_cols2 = st.columns(2)
    mrp = price_cols2[0].number_input(
        "MRP (₹)",
        min_value=0.0,
        value=mrp_default,
        key=f"{key_prefix}_mrp",
    )
    gst_rate = price_cols2[1].number_input(
        "GST rate (%)",
        min_value=0.0,
        max_value=100.0,
        value=gst_default,
        key=f"{key_prefix}_gst",
    )

    hsn_sac = st.text_input(
        "HSN",
        value=existing.hsn_sac if existing else "",
        key=f"{key_prefix}_hsn",
    )
    if registered:
        st.caption("HSN and GST rate are required for registered businesses.")

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

    show_specs = st.checkbox(
        "Edit specifications & custom fields",
        key=f"{key_prefix}_show_specs",
        value=False,
    )
    if show_specs:
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
            if len(spec_rows) > 1 and s_cols[2].button(
                "Remove", key=f"{key_prefix}_spec_rm_{i}"
            ):
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
            category_ids=category_pick["category_ids"],
            values=existing.custom_fields if existing else {},
            key_prefix=key_prefix,
        )
    else:
        custom_values = dict(existing.custom_fields) if existing else {}

    if st.button(submit_label, type="primary", key=f"{key_prefix}_submit"):
        specifications = {
            row["name"].strip(): row["value"].strip()
            for row in st.session_state[spec_key]
            if row.get("name", "").strip() and row.get("value", "").strip()
        }
        return {
            "sku": sku.strip(),
            "name": name.strip(),
            "category_ids": category_pick["category_ids"],
            "pending_category_name": (
                category_pick.get("pending_category_names")
                or category_pick.get("pending_category_name")
            ),
            "unit_id": unit_pick["unit_id"],
            "pending_unit_code": unit_pick.get("pending_unit_code"),
            "hsn_sac": (hsn_sac or "").strip(),
            "selling_rate": float(selling_rate),
            "purchase_rate": float(purchase_rate),
            "mrp": float(mrp),
            "gst_rate": float(gst_rate),
            "gst_required": registered,
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
