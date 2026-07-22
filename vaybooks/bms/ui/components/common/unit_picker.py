"""Chip-style searchable unit picker for product forms."""

from __future__ import annotations

from typing import Optional, TypedDict

import streamlit as st


class UnitPickerResult(TypedDict):
    unit_id: str
    pending_unit_code: Optional[str]


def _unit_label(unit) -> str:
    label = (unit.label or "").strip()
    if label and label.lower() != unit.code.lower():
        return f"{unit.code} — {label}"
    return unit.code


def render_unit_picker(
    inventory,
    *,
    key_prefix: str,
    selected_unit_id: str = "",
    limit: int = 10,
) -> UnitPickerResult:
    """Single-select chip: filter existing units or type a new code.

    ``limit`` is kept for API compatibility; native multiselect filters the
    full active unit list client-side (one chip + accept_new_options).
    """
    _ = limit
    units = inventory.list_units(active_only=True)
    label_to_id = {_unit_label(u): u.id for u in units}
    code_to_id = {u.code.strip().lower(): u.id for u in units if u.code}
    options = sorted(label_to_id.keys(), key=lambda s: s.lower())

    widget_key = f"{key_prefix}_unit_ms"
    if widget_key not in st.session_state:
        initial: list[str] = []
        if selected_unit_id:
            unit = inventory.get_unit(selected_unit_id)
            if unit:
                initial = [_unit_label(unit)]
        st.session_state[widget_key] = initial

    current = list(st.session_state.get(widget_key) or [])
    for label in current:
        if label and label not in options:
            options = list(options) + [label]

    selected_labels = st.multiselect(
        "Unit",
        options=options,
        key=widget_key,
        max_selections=1,
        accept_new_options=True,
        placeholder="Type to search or add a unit…",
        help="Select a unit or type a new code. New units are created when you save the product.",
        label_visibility="collapsed",
    )

    if not selected_labels:
        return {"unit_id": "", "pending_unit_code": None}

    text = (selected_labels[0] or "").strip()
    unit_id = label_to_id.get(text) or code_to_id.get(text.lower())
    if unit_id:
        return {"unit_id": unit_id, "pending_unit_code": None}

    # Free-typed value: use the part before " — " as code if pasted as label form
    pending = text.split(" — ", 1)[0].strip() or text
    return {"unit_id": "", "pending_unit_code": pending}
