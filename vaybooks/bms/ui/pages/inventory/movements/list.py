import streamlit as st

from vaybooks.bms.ui.components.record_movement_dialog import (
    arm_record_movement_dialog,
    open_record_movement_dialog_if_armed,
)
from vaybooks.bms.ui.keyboard.actions import consume_action
from vaybooks.bms.ui.keyboard.context import set_current_page
from vaybooks.bms.ui.keyboard.wired import mark_wired


def render(services: dict):
    set_current_page("inventory_movements_list")
    mark_wired("list.primary", "inventory.movement.add")
    st.caption(
        "Record manual stock movements here. View full history on **Stock Ledger** "
        "or open a product for its running balance."
    )
    if st.button("Record Movement", type="primary", key="inv_movements_record_btn") or consume_action(
        "list.primary"
    ):
        arm_record_movement_dialog()
        st.rerun()

    open_record_movement_dialog_if_armed(services)
