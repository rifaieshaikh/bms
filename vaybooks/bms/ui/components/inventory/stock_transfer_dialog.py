"""Dialog to create a new stock transfer between locations."""

from __future__ import annotations

from datetime import date

import streamlit as st

from vaybooks.bms.domain.identity.location_access import accessible_locations
from vaybooks.bms.ui.auth.session import get_current_user
from vaybooks.bms.ui.components.common.location_picker import render_location_selectbox
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler, register_armed_dialog
from vaybooks.bms.ui.keyboard.dialog_actions import consume_submit, open_dialog
from vaybooks.bms.ui.keyboard.wired import mark_wired

TRANSFER_DIALOG = "stock_transfer_dialog"
SUBMIT_TRANSFER = "submit_stock_transfer"
_LINES_KEY = f"{TRANSFER_DIALOG}_lines"


def arm_transfer_dialog() -> None:
    open_dialog(TRANSFER_DIALOG, submit_key=SUBMIT_TRANSFER, value="new")
    st.session_state[_LINES_KEY] = [{"product_id": "", "qty": 1.0}]
    mark_wired("inventory.transfers.add", "list.primary", "dialog.save")


def _clear() -> None:
    for key in list(st.session_state.keys()):
        if key.startswith(TRANSFER_DIALOG):
            st.session_state.pop(key, None)
    st.session_state.pop(SUBMIT_TRANSFER, None)


def _next_transfer_number(inventory) -> str:
    existing = inventory.list_stock_transfers()
    return f"ST-{len(existing) + 1:04d}"


@st.dialog(
    "New Stock Transfer", width="large", on_dismiss=make_dismiss_handler(TRANSFER_DIALOG)
)
def stock_transfer_dialog(services: dict) -> None:
    if st.session_state.get(TRANSFER_DIALOG) != "new":
        return

    mark_wired("dialog.save", "inventory.transfers.add")
    inventory = services["inventory"]
    user = get_current_user(services)
    locations = accessible_locations(user, inventory)
    if len(locations) < 2:
        st.warning("Add at least two active locations (Settings → Locations) before creating a transfer.")
        if st.button("Close", key=f"{TRANSFER_DIALOG}_close_locations"):
            _clear()
            st.rerun()
        return

    products = inventory.list_products(active_only=True)
    if not products:
        st.warning("Add at least one active product before creating a transfer.")
        if st.button("Close", key=f"{TRANSFER_DIALOG}_close_products"):
            _clear()
            st.rerun()
        return

    prod_opts = {f"{p.sku} — {p.name}": p.id for p in products}
    prod_names = list(prod_opts.keys())
    prod_name_by_id = {p.id: f"{p.sku} — {p.name}" for p in products}

    cols = st.columns(2)
    with cols[0]:
        from_location_id = render_location_selectbox(
            inventory,
            f"{TRANSFER_DIALOG}_from",
            label="From location",
            required=True,
            user=user,
        )
    with cols[1]:
        to_location_id = render_location_selectbox(
            inventory,
            f"{TRANSFER_DIALOG}_to",
            label="To location",
            required=True,
            user=user,
        )

    date_cols = st.columns(2)
    transfer_date = date_cols[0].date_input(
        "Transfer date", value=date.today(), key=f"{TRANSFER_DIALOG}_date"
    )
    notes = st.text_area("Notes", key=f"{TRANSFER_DIALOG}_notes")

    st.markdown("**Lines**")
    lines = st.session_state.setdefault(_LINES_KEY, [{"product_id": "", "qty": 1.0}])
    for idx, line in enumerate(lines):
        line_cols = st.columns([3, 1])
        current_name = prod_name_by_id.get(line.get("product_id"), "")
        default_index = (
            prod_names.index(current_name) if current_name in prod_names else None
        )
        label_visibility = "visible" if idx == 0 else "collapsed"
        selected = line_cols[0].selectbox(
            "Product",
            prod_names,
            index=default_index,
            key=f"{TRANSFER_DIALOG}_line_{idx}_product",
            label_visibility=label_visibility,
            placeholder="Select product…",
        )
        line["product_id"] = prod_opts.get(selected, "")
        line["qty"] = line_cols[1].number_input(
            "Qty",
            min_value=0.0,
            value=float(line.get("qty") or 1.0),
            key=f"{TRANSFER_DIALOG}_line_{idx}_qty",
            label_visibility=label_visibility,
        )

    add_col, remove_col = st.columns(2)
    if add_col.button("+ Add line", key=f"{TRANSFER_DIALOG}_add_line", width="stretch"):
        lines.append({"product_id": "", "qty": 1.0})
        st.rerun()
    if remove_col.button(
        "Remove last line",
        key=f"{TRANSFER_DIALOG}_remove_line",
        width="stretch",
        disabled=len(lines) <= 1,
    ):
        lines.pop()
        st.rerun()

    action_cols = st.columns(2)
    do_save = action_cols[0].button(
        "Create Transfer", type="primary", width="stretch"
    ) or consume_submit(SUBMIT_TRANSFER)
    if action_cols[1].button("Cancel", width="stretch"):
        _clear()
        st.rerun()

    if not do_save:
        return
    try:
        if not from_location_id or not to_location_id:
            raise ValueError("Select both source and destination locations")
        if from_location_id == to_location_id:
            raise ValueError("Source and destination must differ")
        valid_lines = [
            {"product_id": ln["product_id"], "qty": float(ln.get("qty") or 0)}
            for ln in lines
            if ln.get("product_id") and float(ln.get("qty") or 0) > 0
        ]
        if not valid_lines:
            raise ValueError("Add at least one line with product and quantity")
        transfer_number = _next_transfer_number(inventory)
        inventory.create_stock_transfer(
            transfer_number,
            from_location_id,
            to_location_id,
            transfer_date,
            valid_lines,
            notes.strip(),
        )
        _clear()
        st.success(f"Transfer {transfer_number} created")
        st.rerun()
    except Exception as exc:
        st.error(str(exc))


def open_transfer_dialog_if_armed(services: dict) -> None:
    if st.session_state.get(TRANSFER_DIALOG):
        from vaybooks.bms.ui.keyboard.context import get_submit_map

        get_submit_map().setdefault(TRANSFER_DIALOG, SUBMIT_TRANSFER)
        register_armed_dialog(TRANSFER_DIALOG)
        stock_transfer_dialog(services)
