import streamlit as st

from vaybooks.bms.ui.components.record_movement_dialog import (
    arm_record_movement_dialog,
    open_record_movement_dialog_if_armed,
)


def render(services: dict):
    st.caption(
        "Record manual stock movements here. View full history on **Stock Ledger** "
        "or open a product for its running balance."
    )
    if st.button("Record Movement", type="primary", key="inv_movements_record_btn"):
        arm_record_movement_dialog()
        st.rerun()

    open_record_movement_dialog_if_armed(services)
