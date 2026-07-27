"""Shared discount controls for sales invoice / sales order dialogs."""

from __future__ import annotations

from typing import Literal

import streamlit as st

DiscountMode = Literal["flat", "percent"]

_DISC_TYPE_FLAT = "₹"
_DISC_TYPE_PCT = "%"
_DISC_TYPE_OPTIONS = [_DISC_TYPE_FLAT, _DISC_TYPE_PCT]


def resolve_line_discount(
    *,
    qty: float,
    rate: float,
    value: float,
    mode: DiscountMode | str = "flat",
) -> float:
    """Convert line discount flat ₹ or % into a rupee amount capped at line gross."""
    gross = round(max(float(qty or 0), 0.0) * max(float(rate or 0), 0.0), 2)
    raw = max(float(value or 0), 0.0)
    if str(mode).strip().lower() in {"percent", "%", "pct"}:
        amount = round(gross * min(raw, 100.0) / 100.0, 2)
    else:
        amount = round(raw, 2)
    return round(min(amount, gross), 2)


def resolve_invoice_level_discount(
    *,
    base_amount: float,
    value: float,
    mode: DiscountMode,
) -> float:
    """Convert flat ₹ or % input into a rupee discount capped at ``base_amount``."""
    base = max(float(base_amount or 0), 0.0)
    raw = max(float(value or 0), 0.0)
    if mode == "percent":
        amount = round(base * min(raw, 100.0) / 100.0, 2)
    else:
        amount = round(raw, 2)
    return round(min(amount, base), 2)


def line_has_discount(line: dict | object, *, tolerance: float = 0.01) -> bool:
    """True when the line already carries a line-level discount."""
    if isinstance(line, dict):
        return float(line.get("discount") or 0) > tolerance
    return float(getattr(line, "discount", 0) or 0) > tolerance


def eligible_invoice_discount_base(lines: list[dict]) -> float:
    """Sum of qty×rate for lines that have no line-level discount."""
    total = 0.0
    for line in lines or []:
        if line_has_discount(line):
            continue
        qty = float(line.get("qty") or 0)
        rate = float(line.get("rate") or 0)
        total += round(max(qty, 0.0) * max(rate, 0.0), 2)
    return round(total, 2)


def render_invoice_level_discount(
    *,
    key_prefix: str,
    base_amount: float,
    label: str = "Invoice-level discount",
) -> float:
    """Dropdown ₹/% plus amount; returns discount in rupees against ``base_amount``."""
    mode_key = f"{key_prefix}_mode"
    st.caption(label)
    cols = st.columns([1.0, 1.8])
    mode_label = cols[0].selectbox(
        "Discount type",
        options=_DISC_TYPE_OPTIONS,
        key=mode_key,
        label_visibility="collapsed",
        help="Flat rupees or percent of eligible line subtotal (lines without item discount)",
    )
    mode: DiscountMode = "percent" if mode_label == _DISC_TYPE_PCT else "flat"
    if mode == "percent":
        value = cols[1].number_input(
            "Percent",
            min_value=0.0,
            max_value=100.0,
            value=0.0,
            key=f"{key_prefix}_pct",
            label_visibility="collapsed",
            help="Percent of eligible lines (no item discount), weighted by qty × rate",
        )
    else:
        value = cols[1].number_input(
            "Amount (₹)",
            min_value=0.0,
            value=0.0,
            key=f"{key_prefix}_flat",
            label_visibility="collapsed",
            help="Flat invoice discount applied only to lines without item discount",
        )
    amount = resolve_invoice_level_discount(
        base_amount=base_amount, value=value, mode=mode
    )
    if base_amount <= 0 and (value or 0) > 0:
        st.caption("No eligible lines (all lines already have an item discount).")
    elif mode == "percent" and value > 0:
        st.caption(f"= ₹{amount:,.2f} on eligible subtotal ₹{base_amount:,.2f}")
    elif mode == "flat" and amount > 0:
        st.caption(f"On eligible subtotal ₹{base_amount:,.2f}")
    return amount
