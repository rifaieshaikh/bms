"""Suggest/fill configured discount rules into sales line entry tables."""

from __future__ import annotations

from datetime import date
from typing import Optional

import streamlit as st

from vaybooks.bms.domain.sales.discount_entities import (
    APPLY_SALES_INVOICE,
    APPLY_SALES_ORDER,
)
from vaybooks.bms.ui.components.sales.sales_lines_entry_table import _sku_label


def _discount_key(key_prefix: str, uid: str) -> str:
    return f"{key_prefix}_r{uid}_discount"


def _discount_mode_key(key_prefix: str, uid: str) -> str:
    return f"{key_prefix}_r{uid}_disc_mode"


def apply_rules_to_entry_rows(
    *,
    key_prefix: str,
    discounts_svc,
    inventory_svc,
    customer,
    apply_to: str,
    on_date: Optional[date] = None,
    qty_field: str = "qty",
) -> int:
    """Fill line discounts from rules into session rows + widget keys.

    Returns the number of lines that received a discount.
    """
    if not discounts_svc:
        return 0
    rows_key = f"{key_prefix}_rows"
    rows = list(st.session_state.get(rows_key) or [])
    if not rows:
        return 0

    products = inventory_svc.list_products(active_only=True) if inventory_svc else []
    label_lookup = {_sku_label(p).casefold(): p for p in products}

    customer_id = getattr(customer, "id", "") or ""
    segment_ids = list(getattr(customer, "segment_ids", None) or [])
    line_payloads: list[dict] = []
    row_indexes: list[int] = []

    for index, row in enumerate(rows):
        label = row.get("item_label")
        if not label:
            continue
        product = label_lookup.get(str(label).casefold())
        product_id = str(
            (product.id if product else None) or row.get("product_id") or ""
        ).strip()
        uid = str(row.get("uid") or "")
        qty = float(row.get("qty") or row.get(qty_field) or 0)
        rate = float(row.get("rate") or 0)
        if uid:
            qty_key = f"{key_prefix}_r{uid}_qty"
            rate_key = f"{key_prefix}_r{uid}_rate"
            if qty_key in st.session_state:
                qty = float(st.session_state.get(qty_key) or 0)
            if rate_key in st.session_state:
                rate = float(st.session_state.get(rate_key) or 0)
        if qty <= 0 or rate < 0:
            continue
        category_ids: list[str] = []
        if product:
            category_ids = list(getattr(product, "category_ids", None) or [])
            if not category_ids and getattr(product, "category_id", ""):
                category_ids = [product.category_id]
            row["product_id"] = product.id
        line_payloads.append(
            {
                "product_id": product_id,
                "category_ids": category_ids,
                "qty": qty,
                qty_field: qty,
                "rate": rate,
            }
        )
        row_indexes.append(index)

    results = discounts_svc.suggest_line_discounts(
        line_payloads,
        customer_id=customer_id,
        customer_segment_ids=segment_ids,
        apply_to=apply_to,
        on_date=on_date or date.today(),
        boutique=False,
        qty_field=qty_field,
    )

    applied = 0
    for row_index, result in zip(row_indexes, results):
        row = rows[row_index]
        uid = str(row.get("uid") or "")
        amount = float(result.amount) if result else 0.0
        row["discount"] = amount
        row["discount_mode"] = "flat"
        row["discount_input"] = amount
        if result:
            row["discount_rule_id"] = result.rule_id
            row["discount_rule_name"] = result.rule_name
            applied += 1
        else:
            row.pop("discount_rule_id", None)
            row.pop("discount_rule_name", None)
        if uid:
            st.session_state[_discount_mode_key(key_prefix, uid)] = "₹"
            st.session_state[_discount_key(key_prefix, uid)] = amount
        rows[row_index] = row

    st.session_state[rows_key] = rows
    return applied


def render_apply_discount_rules_button(
    *,
    key_prefix: str,
    services: dict,
    customer,
    apply_to: str,
    on_date: Optional[date] = None,
    qty_field: str = "qty",
    button_key: Optional[str] = None,
) -> None:
    """Render Re-apply discounts control for SO / invoice dialogs."""
    discounts_svc = services.get("discounts")
    if not discounts_svc or not customer:
        return
    help_text = (
        "Fill line discounts from configured rules (overwrites current line discounts)."
    )
    if apply_to not in {APPLY_SALES_ORDER, APPLY_SALES_INVOICE}:
        help_text = "Fill line discounts from configured rules."

    if st.button(
        "Re-apply discounts",
        key=button_key or f"{key_prefix}_apply_discount_rules",
        help=help_text,
        width="stretch",
    ):
        count = apply_rules_to_entry_rows(
            key_prefix=key_prefix,
            discounts_svc=discounts_svc,
            inventory_svc=services.get("inventory"),
            customer=customer,
            apply_to=apply_to,
            on_date=on_date,
            qty_field=qty_field,
        )
        if count:
            st.success(f"Applied discounts to {count} line(s).")
        else:
            st.info("No matching discount rules for these lines.")
        st.rerun()
