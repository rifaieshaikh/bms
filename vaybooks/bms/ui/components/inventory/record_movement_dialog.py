"""Dialog to record manual stock movements."""

from __future__ import annotations

from datetime import date

import streamlit as st

from vaybooks.bms.domain.shared.enums import StockMovementType
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler

MOVEMENT_DIALOG = "inventory_movement_dialog"

MANUAL_TYPES = [
    StockMovementType.RECEIVE,
    StockMovementType.ISSUE,
    StockMovementType.ADJUST_IN,
    StockMovementType.ADJUST_OUT,
]


def arm_record_movement_dialog() -> None:
    st.session_state[MOVEMENT_DIALOG] = "new"


@st.dialog(
    "Record Stock Movement",
    width="medium",
    on_dismiss=make_dismiss_handler(MOVEMENT_DIALOG),
)
def record_movement_dialog(services: dict) -> None:
    if st.session_state.get(MOVEMENT_DIALOG) != "new":
        return

    inventory = services["inventory"]
    products = inventory.list_products(active_only=True)
    if not products:
        st.warning("Add at least one active product before recording movements.")
        if st.button("Close"):
            st.session_state.pop(MOVEMENT_DIALOG, None)
            st.rerun()
        return

    prod_opts = {f"{p.sku} — {p.name}": p.id for p in products}
    prod_names = list(prod_opts.keys())
    type_opts = {t.value: t for t in MANUAL_TYPES}
    type_labels = list(type_opts.keys())

    product_name = st.selectbox("Product", prod_names, key=f"{MOVEMENT_DIALOG}_product")
    movement_label = st.selectbox(
        "Movement type",
        type_labels,
        key=f"{MOVEMENT_DIALOG}_type",
    )
    qty = st.number_input(
        "Quantity",
        min_value=0.0,
        value=1.0,
        key=f"{MOVEMENT_DIALOG}_qty",
    )
    movement_date = st.date_input(
        "Date",
        value=date.today(),
        key=f"{MOVEMENT_DIALOG}_date",
    )
    notes = st.text_area("Notes", key=f"{MOVEMENT_DIALOG}_notes")

    cols = st.columns(2)
    if cols[0].button("Save", type="primary", use_container_width=True):
        try:
            if qty <= 0:
                raise ValueError("Quantity must be positive")
            inventory.record_manual_movement(
                prod_opts[product_name],
                type_opts[movement_label],
                qty,
                movement_date,
                notes.strip(),
            )
            st.session_state.pop(MOVEMENT_DIALOG, None)
            st.success("Movement recorded")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if cols[1].button("Cancel", use_container_width=True):
        st.session_state.pop(MOVEMENT_DIALOG, None)
        st.rerun()


def open_record_movement_dialog_if_armed(services: dict) -> None:
    if st.session_state.get(MOVEMENT_DIALOG):
        record_movement_dialog(services)
