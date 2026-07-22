"""Chip-style searchable category multi-picker for product forms."""

from __future__ import annotations

from typing import List, Optional, TypedDict

import streamlit as st


class CategoryPickerResult(TypedDict):
    category_ids: List[str]
    pending_category_name: Optional[str]
    pending_category_names: List[str]


def render_category_picker(
    inventory,
    *,
    key_prefix: str,
    selected_ids: Optional[List[str]] = None,
    active_only: bool = True,
    limit: int = 10,
) -> CategoryPickerResult:
    """Multi-select chips: filter existing categories or type a new root name.

    ``limit`` is kept for API compatibility; native multiselect filters the
    full active catalog client-side (chips + accept_new_options).
    """
    _ = limit
    categories = inventory.list_categories(active_only=active_only)
    paths = inventory.category_paths_for([c.id for c in categories])
    label_to_id = {
        paths[c.id]: c.id for c in categories if c.id in paths and paths[c.id]
    }
    # Fallback for categories without a resolved path
    for c in categories:
        if c.id not in {v for v in label_to_id.values()}:
            label_to_id[c.name] = c.id

    options = sorted(label_to_id.keys(), key=lambda s: s.lower())

    widget_key = f"{key_prefix}_category_ms"
    if widget_key not in st.session_state:
        init_ids = [cid for cid in (selected_ids or []) if cid]
        init_paths = inventory.category_paths_for(init_ids)
        st.session_state[widget_key] = [
            init_paths[cid] for cid in init_ids if cid in init_paths and init_paths[cid]
        ]

    # Keep any currently selected labels that are not in options (new chips)
    current = list(st.session_state.get(widget_key) or [])
    for label in current:
        if label and label not in options:
            options = list(options) + [label]

    selected_labels = st.multiselect(
        "Categories",
        options=options,
        key=widget_key,
        accept_new_options=True,
        placeholder="Type to search or add a category…",
        help="Select from suggestions or type a new name. New root categories are created when you save the product.",
        label_visibility="collapsed",
    )

    category_ids: List[str] = []
    pending_names: List[str] = []
    seen_ids: set[str] = set()
    for label in selected_labels:
        text = (label or "").strip()
        if not text:
            continue
        cid = label_to_id.get(text)
        if cid and cid not in seen_ids:
            category_ids.append(cid)
            seen_ids.add(cid)
        elif not cid:
            pending_names.append(text)

    return {
        "category_ids": category_ids,
        "pending_category_name": pending_names[0] if pending_names else None,
        "pending_category_names": pending_names,
    }
