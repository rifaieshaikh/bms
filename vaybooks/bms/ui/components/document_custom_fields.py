from __future__ import annotations

from datetime import date

import streamlit as st


def render_document_custom_fields(
    definitions,
    *,
    key_prefix: str,
    initial_values: dict | None = None,
) -> dict:
    initial_values = initial_values or {}
    values = {}
    for definition in sorted(definitions, key=lambda item: item.display_order):
        key = f"{key_prefix}_{definition.key}"
        initial = initial_values.get(definition.key, definition.default_value)
        label = definition.label + (" *" if definition.required else "")
        if definition.field_type == "multiline":
            values[definition.key] = st.text_area(label, value=str(initial or ""), key=key)
        elif definition.field_type == "number":
            values[definition.key] = st.number_input(
                label, value=float(initial or 0), key=key
            )
        elif definition.field_type == "date":
            value = initial if isinstance(initial, date) else date.today()
            values[definition.key] = st.date_input(label, value=value, key=key)
        elif definition.field_type == "checkbox":
            values[definition.key] = st.checkbox(label, value=bool(initial), key=key)
        else:
            values[definition.key] = st.text_input(
                label, value=str(initial or ""), key=key
            )
    return values
