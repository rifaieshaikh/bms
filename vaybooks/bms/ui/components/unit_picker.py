"""Unit picker and inline unit management for product forms."""

from __future__ import annotations

from typing import Optional

import streamlit as st


def render_unit_picker(
    inventory,
    *,
    key_prefix: str,
    selected_unit_id: str = "",
) -> str:
    units = inventory.list_units(active_only=False)
    active_units = [u for u in units if u.is_active] or units
    labels = [f"{u.code} — {u.label}" for u in active_units]
    id_by_label = {f"{u.code} — {u.label}": u.id for u in active_units}
    default_index = 0
    if selected_unit_id:
        for i, unit in enumerate(active_units):
            if unit.id == selected_unit_id:
                default_index = i
                break
    pick = st.selectbox(
        "Unit",
        labels or ["pcs — Pieces"],
        index=default_index if labels else 0,
        key=f"{key_prefix}_unit_pick",
    )
    unit_id = id_by_label.get(pick, "")

    with st.expander("Manage units", expanded=False):
        st.caption("Add a unit or edit labels. Duplicate codes reuse the existing unit.")
        add_cols = st.columns(2)
        new_code = add_cols[0].text_input("Code", key=f"{key_prefix}_unit_new_code")
        new_label = add_cols[1].text_input("Label", key=f"{key_prefix}_unit_new_label")
        if st.button("Add unit", key=f"{key_prefix}_unit_add"):
            try:
                before = inventory.list_units(active_only=False)
                before_codes = {u.code for u in before}
                saved = inventory.find_or_create_unit(new_code, new_label)
                if saved.code in before_codes:
                    st.info("Unit already exists — selected existing.")
                st.session_state[f"{key_prefix}_unit_pick"] = f"{saved.code} — {saved.label}"
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

        for unit in units:
            with st.container(border=True):
                e_cols = st.columns([2, 3, 1, 1])
                e_cols[0].markdown(f"**{unit.code}**")
                new_lbl = e_cols[1].text_input(
                    "Label",
                    value=unit.label,
                    key=f"{key_prefix}_unit_lbl_{unit.id}",
                    label_visibility="collapsed",
                )
                active = e_cols[2].checkbox(
                    "Active",
                    value=unit.is_active,
                    key=f"{key_prefix}_unit_act_{unit.id}",
                )
                if e_cols[3].button("Save", key=f"{key_prefix}_unit_save_{unit.id}"):
                    try:
                        inventory.update_unit(unit.id, new_lbl, active)
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
    return unit_id
