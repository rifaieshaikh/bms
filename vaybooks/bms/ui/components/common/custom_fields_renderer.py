"""Render admin-defined custom fields on product forms."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

import streamlit as st

from vaybooks.bms.domain.inventory.field_definitions import ProductFieldDefinition, ProductFieldType


def _applicable_definitions(
    definitions: List[ProductFieldDefinition],
    category_ids: List[str],
) -> List[ProductFieldDefinition]:
    return sorted(
        [d for d in definitions if d.applies_to_product(category_ids)],
        key=lambda d: d.sort_order,
    )


def render_custom_fields(
    definitions: List[ProductFieldDefinition],
    *,
    category_ids: List[str],
    values: Optional[Dict[str, Any]] = None,
    key_prefix: str,
) -> Dict[str, Any]:
    values = dict(values or {})
    result: Dict[str, Any] = {}
    applicable = _applicable_definitions(definitions, category_ids)
    if not applicable:
        return result

    st.markdown("**Custom fields**")
    for definition in applicable:
        current = values.get(definition.key)
        label = definition.label + (" *" if definition.required else "")
        if definition.field_type == ProductFieldType.BOOLEAN:
            result[definition.key] = st.checkbox(
                label,
                value=bool(current),
                key=f"{key_prefix}_cf_{definition.key}",
            )
        elif definition.field_type == ProductFieldType.NUMBER:
            result[definition.key] = st.number_input(
                label,
                value=float(current or 0),
                key=f"{key_prefix}_cf_{definition.key}",
            )
        elif definition.field_type == ProductFieldType.DATE:
            default = date.today()
            if current:
                try:
                    default = date.fromisoformat(str(current)[:10])
                except ValueError:
                    pass
            picked = st.date_input(label, value=default, key=f"{key_prefix}_cf_{definition.key}")
            result[definition.key] = picked.isoformat()
        elif definition.field_type == ProductFieldType.SELECT:
            options = definition.options or [""]
            index = 0
            if current in options:
                index = options.index(current)
            result[definition.key] = st.selectbox(
                label,
                options,
                index=index,
                key=f"{key_prefix}_cf_{definition.key}",
            )
        else:
            result[definition.key] = st.text_input(
                label,
                value=str(current or ""),
                key=f"{key_prefix}_cf_{definition.key}",
            )
    return result
