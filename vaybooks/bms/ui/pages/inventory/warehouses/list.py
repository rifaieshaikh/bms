import streamlit as st

from vaybooks.bms.ui.components.common.list_view import render_list
from vaybooks.bms.ui.components.inventory.inventory_product_card import (
    inventory_warehouse_card,
)
from vaybooks.bms.ui.dialog_utils import (
    clear_all_dialog_flags,
    make_dismiss_handler,
    register_armed_dialog,
)
from vaybooks.bms.ui.inventory_list_schemas import INVENTORY_WAREHOUSES
from vaybooks.bms.ui.keyboard.dialog_actions import (
    consume_submit,
    open_dialog,
)
from vaybooks.bms.ui.keyboard.wired import mark_wired
from vaybooks.bms.ui.styles import render_card_grid

W_ADD = "inv_warehouse_add_dialog"
W_EDIT = "inv_warehouse_edit_dialog"
SUBMIT_ADD = "submit_inv_warehouse_add"
SUBMIT_EDIT = "submit_inv_warehouse_edit"


def _open_add_warehouse() -> None:
    clear_all_dialog_flags()
    open_dialog(W_ADD, submit_key=SUBMIT_ADD, clear_others=False)
    mark_wired("inventory.warehouse.add", "list.primary", "dialog.save")


def _open_edit_warehouse(warehouse_id: str) -> None:
    clear_all_dialog_flags()
    open_dialog(W_EDIT, submit_key=SUBMIT_EDIT, value=warehouse_id, clear_others=False)
    mark_wired("inventory.warehouse.save", "dialog.save", "list.edit_nth.1")


@st.dialog("Add Warehouse", width="medium", on_dismiss=make_dismiss_handler(W_ADD))
def _add_warehouse_dialog(inventory):
    mark_wired("dialog.save", "inventory.warehouse.add")
    code = st.text_input("Code", key=f"{W_ADD}_code")
    name = st.text_input("Name", key=f"{W_ADD}_name")
    address = st.text_area("Address", key=f"{W_ADD}_address")
    cols = st.columns(2)
    do_create = cols[0].button(
        "Create Warehouse", type="primary", width="stretch"
    ) or consume_submit(SUBMIT_ADD)
    if cols[1].button("Cancel", width="stretch"):
        st.session_state.pop(W_ADD, None)
        st.rerun()
    if not do_create:
        return
    if not code.strip() or not name.strip():
        st.error("Code and name are required")
        return
    try:
        inventory.create_warehouse(code, name, address)
        st.session_state.pop(W_ADD, None)
        st.success(f"Created {name}")
        st.rerun()
    except Exception as exc:
        st.error(str(exc))


@st.dialog("Edit Warehouse", width="medium", on_dismiss=make_dismiss_handler(W_EDIT))
def _edit_warehouse_dialog(inventory, warehouse_id: str):
    mark_wired("dialog.save", "inventory.warehouse.save")
    warehouse = inventory.get_warehouse(warehouse_id)
    if not warehouse:
        st.error("Warehouse not found")
        return

    code = st.text_input(
        "Code", value=warehouse.code, key=f"{W_EDIT}_code_{warehouse_id}"
    )
    name = st.text_input(
        "Name", value=warehouse.name, key=f"{W_EDIT}_name_{warehouse_id}"
    )
    address = st.text_area(
        "Address",
        value=warehouse.address or "",
        key=f"{W_EDIT}_address_{warehouse_id}",
    )
    is_active = st.checkbox(
        "Active", value=warehouse.is_active, key=f"{W_EDIT}_active_{warehouse_id}"
    )

    cols = st.columns(2)
    do_save = cols[0].button(
        "Save Changes", type="primary", width="stretch"
    ) or consume_submit(SUBMIT_EDIT)
    if cols[1].button("Delete", width="stretch"):
        try:
            inventory.delete_warehouse(warehouse_id)
            st.session_state.pop(W_EDIT, None)
            st.success("Warehouse deleted")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
        return

    if do_save:
        try:
            inventory.update_warehouse(
                warehouse_id, code, name, address, is_active=is_active
            )
            st.session_state.pop(W_EDIT, None)
            st.success("Warehouse updated")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def _load_warehouses(services, filters, sort):
    try:
        return services["inventory"].list_warehouses(active_only=False)
    except Exception:
        return []


def _render_cards(page_warehouses, services):
    def _render(warehouse, _i):
        if inventory_warehouse_card(warehouse):
            _open_edit_warehouse(warehouse.id)
            st.rerun()

    render_card_grid(
        page_warehouses,
        _render,
        suffix="inv_warehouses",
        card_min_width=240,
    )


def render(services: dict):
    inventory = services["inventory"]
    mark_wired(
        "inventory.warehouse.add",
        "list.filters.open",
        "list.sort.open",
        "list.primary",
    )
    bar = render_list(
        INVENTORY_WAREHOUSES,
        services=services,
        load_fn=_load_warehouses,
        card_renderer=_render_cards,
        primary_label="Add Warehouse",
        primary_key="inv_warehouses_add_btn",
        count_label="warehouses",
        empty_text="No warehouses yet.",
        page_key_nav="inventory_warehouses_list",
    )
    if bar["primary_clicked"]:
        _open_add_warehouse()
    if bar.get("edit_nth"):
        _open_edit_warehouse(bar["edit_nth"])
        st.rerun()
    if st.session_state.get(W_ADD):
        from vaybooks.bms.ui.keyboard.context import get_submit_map

        get_submit_map().setdefault(W_ADD, SUBMIT_ADD)
        register_armed_dialog(W_ADD)
        _add_warehouse_dialog(inventory)
    if st.session_state.get(W_EDIT):
        from vaybooks.bms.ui.keyboard.context import get_submit_map

        get_submit_map().setdefault(W_EDIT, SUBMIT_EDIT)
        register_armed_dialog(W_EDIT)
        _edit_warehouse_dialog(inventory, st.session_state[W_EDIT])
