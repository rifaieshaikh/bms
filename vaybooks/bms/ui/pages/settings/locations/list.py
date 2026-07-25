"""Settings -> Locations: warehouses and retail stores used across inventory."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.domain.shared.enums import LocationType
from vaybooks.bms.ui.components.common.list_view import render_list
from vaybooks.bms.ui.components.inventory.inventory_product_card import (
    inventory_location_card,
)
from vaybooks.bms.ui.dialog_utils import (
    clear_all_dialog_flags,
    make_dismiss_handler,
    register_armed_dialog,
)
from vaybooks.bms.ui.inventory_list_schemas import SETTINGS_LOCATIONS
from vaybooks.bms.ui.keyboard.dialog_actions import (
    consume_submit,
    open_dialog,
)
from vaybooks.bms.ui.keyboard.wired import mark_wired
from vaybooks.bms.ui.styles import render_card_grid

L_ADD = "settings_location_add_dialog"
L_EDIT = "settings_location_edit_dialog"
SUBMIT_ADD = "submit_settings_location_add"
SUBMIT_EDIT = "submit_settings_location_edit"

_LOCATION_TYPES = [t.value for t in LocationType]


def _open_add_location() -> None:
    clear_all_dialog_flags()
    open_dialog(L_ADD, submit_key=SUBMIT_ADD, clear_others=False)
    mark_wired("settings.locations.add", "list.primary", "dialog.save")


def _open_edit_location(location_id: str) -> None:
    clear_all_dialog_flags()
    open_dialog(L_EDIT, submit_key=SUBMIT_EDIT, value=location_id, clear_others=False)
    mark_wired("settings.locations.save", "dialog.save", "list.edit_nth.1")


@st.dialog("Add Location", width="medium", on_dismiss=make_dismiss_handler(L_ADD))
def _add_location_dialog(inventory):
    mark_wired("dialog.save", "settings.locations.add")
    code = st.text_input("Code", key=f"{L_ADD}_code")
    name = st.text_input("Name", key=f"{L_ADD}_name")
    location_type = st.selectbox("Type", _LOCATION_TYPES, key=f"{L_ADD}_type")
    address = st.text_area("Address", key=f"{L_ADD}_address")
    cols = st.columns(2)
    do_create = cols[0].button(
        "Create Location", type="primary", width="stretch"
    ) or consume_submit(SUBMIT_ADD)
    if cols[1].button("Cancel", width="stretch"):
        st.session_state.pop(L_ADD, None)
        st.rerun()
    if not do_create:
        return
    if not code.strip() or not name.strip():
        st.error("Code and name are required")
        return
    try:
        inventory.create_location(
            code, name, address, location_type=LocationType(location_type)
        )
        st.session_state.pop(L_ADD, None)
        st.success(f"Created {name}")
        st.rerun()
    except Exception as exc:
        st.error(str(exc))


@st.dialog("Edit Location", width="medium", on_dismiss=make_dismiss_handler(L_EDIT))
def _edit_location_dialog(inventory, location_id: str):
    mark_wired("dialog.save", "settings.locations.save")
    location = inventory.get_location(location_id)
    if not location:
        st.error("Location not found")
        return

    code = st.text_input(
        "Code", value=location.code, key=f"{L_EDIT}_code_{location_id}"
    )
    name = st.text_input(
        "Name", value=location.name, key=f"{L_EDIT}_name_{location_id}"
    )
    type_value = getattr(location.location_type, "value", location.location_type)
    type_index = (
        _LOCATION_TYPES.index(type_value) if type_value in _LOCATION_TYPES else 0
    )
    location_type = st.selectbox(
        "Type",
        _LOCATION_TYPES,
        index=type_index,
        key=f"{L_EDIT}_type_{location_id}",
    )
    address = st.text_area(
        "Address",
        value=location.address or "",
        key=f"{L_EDIT}_address_{location_id}",
    )
    is_active = st.checkbox(
        "Active", value=location.is_active, key=f"{L_EDIT}_active_{location_id}"
    )

    cols = st.columns(2)
    do_save = cols[0].button(
        "Save Changes", type="primary", width="stretch"
    ) or consume_submit(SUBMIT_EDIT)
    if cols[1].button("Delete", width="stretch"):
        try:
            inventory.delete_location(location_id)
            st.session_state.pop(L_EDIT, None)
            st.success("Location deleted")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
        return

    if do_save:
        try:
            inventory.update_location(
                location_id,
                code,
                name,
                address,
                is_active=is_active,
                location_type=LocationType(location_type),
            )
            st.session_state.pop(L_EDIT, None)
            st.success("Location updated")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def _load_locations(services, filters, sort):
    try:
        return services["inventory"].list_locations(active_only=False)
    except Exception:
        return []


def _render_cards(page_locations, services):
    def _render(location, _i):
        if inventory_location_card(location):
            _open_edit_location(location.id)
            st.rerun()

    render_card_grid(
        page_locations,
        _render,
        suffix="settings_locations",
        card_min_width=240,
    )


def render(services: dict):
    inventory = services["inventory"]
    mark_wired(
        "settings.locations.add",
        "list.filters.open",
        "list.sort.open",
        "list.primary",
    )
    bar = render_list(
        SETTINGS_LOCATIONS,
        services=services,
        load_fn=_load_locations,
        card_renderer=_render_cards,
        primary_label="Add Location",
        primary_key="settings_locations_add_btn",
        title="Locations",
        count_label="locations",
        empty_text="No locations yet.",
        page_key_nav="settings_locations_list",
    )
    if bar["primary_clicked"]:
        _open_add_location()
    if bar.get("edit_nth"):
        _open_edit_location(bar["edit_nth"])
        st.rerun()
    if st.session_state.get(L_ADD):
        from vaybooks.bms.ui.keyboard.context import get_submit_map

        get_submit_map().setdefault(L_ADD, SUBMIT_ADD)
        register_armed_dialog(L_ADD)
        _add_location_dialog(inventory)
    if st.session_state.get(L_EDIT):
        from vaybooks.bms.ui.keyboard.context import get_submit_map

        get_submit_map().setdefault(L_EDIT, SUBMIT_EDIT)
        register_armed_dialog(L_EDIT)
        _edit_location_dialog(inventory, st.session_state[L_EDIT])
