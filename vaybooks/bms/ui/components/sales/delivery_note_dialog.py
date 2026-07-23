"""Delivery note dialog (qty-against-SO, GRN-style focus)."""

from __future__ import annotations

from datetime import date

import streamlit as st

from vaybooks.bms.ui.components.common.dialog_state import (
    ensure_selectbox_option,
    reset_dialog_state,
)
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler, register_armed_dialog
from vaybooks.bms.ui.keyboard.dialog_actions import consume_submit, open_dialog
from vaybooks.bms.ui.keyboard.focus.registry import get_strategy
from vaybooks.bms.ui.keyboard.wired import mark_wired

DN_DIALOG = "delivery_note_dialog"
DN_SUBMIT_KEY = "delivery_note_dialog_submit"
DN_FOCUS_KEY = f"{DN_DIALOG}_focus"


def arm_dn_dialog(so_id: str | None = None) -> None:
    reset_dialog_state(DN_DIALOG)
    open_dialog(DN_DIALOG, submit_key=DN_SUBMIT_KEY, value="new", clear_others=True)
    st.session_state[DN_FOCUS_KEY] = f"{DN_DIALOG}_date"
    if so_id:
        st.session_state[f"{DN_DIALOG}_so_id"] = so_id
    mark_wired("dialog.save")


def _clear() -> None:
    for key in list(st.session_state.keys()):
        if key.startswith(DN_DIALOG):
            st.session_state.pop(key, None)
    st.session_state.pop(DN_SUBMIT_KEY, None)


@st.dialog("Create Delivery Note", width="large", on_dismiss=make_dismiss_handler(DN_DIALOG))
def delivery_note_dialog(services: dict) -> None:
    if st.session_state.get(DN_DIALOG) != "new":
        return

    register_armed_dialog(DN_DIALOG)
    mark_wired("dialog.save")

    sales = services["sales"]
    customers = services["customers"]
    open_orders = [
        so
        for so in sales.list_sales_orders()
        if so.status.value not in ("Cancelled", "Closed", "Delivered")
    ]
    so_opts = {"— Direct (no SO) —": None}
    so_opts.update({f"{so.so_number} — {so.customer_name}": so.id for so in open_orders})

    pre_so = st.session_state.get(f"{DN_DIALOG}_so_id")
    so_key = f"{DN_DIALOG}_so"
    so_label = st.selectbox(
        "Sales order",
        list(so_opts.keys()),
        index=list(so_opts.values()).index(pre_so) if pre_so in so_opts.values() else 0,
        key=so_key,
    )
    so_id = so_opts[so_label]
    so = sales.get_sales_order(so_id) if so_id else None

    customer_id = so.customer_id if so else None
    cust_key = f"{DN_DIALOG}_customer"
    if not so:
        customer_list = customers.list_all_customers()
        if not customer_list:
            st.error("Add a customer first, or select a sales order.")
            if st.button("Close", key=f"{DN_DIALOG}_close"):
                _clear()
                st.rerun()
            return
        cust_opts = {c.customer_name: c.id for c in customer_list}
        cust_names = list(cust_opts.keys())
        ensure_selectbox_option(cust_key, cust_names)
        customer_name = st.selectbox("Customer", cust_names, key=cust_key)
        customer_id = cust_opts.get(customer_name)
        if not customer_id:
            st.warning("Select a customer.")
            get_strategy(DN_DIALOG).inject(
                chain=[so_key, cust_key],
                restore_key=st.session_state.pop(DN_FOCUS_KEY, None),
                component_key="dn_direct_customer",
            )
            return
        st.info("Select a sales order to deliver against, or create a sales order first.")
        get_strategy(DN_DIALOG).inject(
            chain=[so_key, cust_key],
            restore_key=st.session_state.pop(DN_FOCUS_KEY, None),
            component_key="dn_direct_no_grid",
        )
        return

    date_key = f"{DN_DIALOG}_date"
    save_key = f"{DN_DIALOG}_save"
    delivery_date = st.date_input("Delivery date", value=date.today(), key=date_key)

    lines = []
    qty_keys: list[str] = []
    st.markdown("**Deliver quantities**")
    for i, sl in enumerate(so.lines):
        pending = sl.qty_pending
        if pending <= 0:
            continue
        uid = sl.product_id or str(i)
        qkey = f"{DN_DIALOG}_r{uid}_qty_recv"
        qty_keys.append(qkey)
        qty = st.number_input(
            f"{sl.product_name or sl.product_id} (pending {pending:g})",
            min_value=0.0,
            max_value=float(pending),
            value=float(pending),
            key=qkey,
        )
        if qty > 0:
            lines.append(
                {
                    "product_id": sl.product_id,
                    "product_name": sl.product_name,
                    "qty_delivered": qty,
                    "rate": sl.rate,
                }
            )

    st.session_state[f"{DN_DIALOG}_kb_chain"] = qty_keys
    do_save = st.button(
        "Confirm delivery", type="primary", key=save_key
    ) or consume_submit(DN_SUBMIT_KEY)

    restore = st.session_state.pop(DN_FOCUS_KEY, None)
    get_strategy(DN_DIALOG).inject(
        chain=[date_key, *qty_keys, save_key],
        restore_key=restore,
        columns={"qty": qty_keys},
        above_first=date_key,
        below_last=save_key,
        component_key=f"dn_recv_{so.id[:8]}_{len(qty_keys)}",
    )

    if do_save:
        try:
            if not so_id:
                raise ValueError("Select a sales order")
            if not lines:
                raise ValueError("Enter at least one delivered quantity")
            sales.create_delivery_note(
                customer_id=customer_id,
                delivery_date=delivery_date,
                lines=lines,
                sales_order_id=so_id,
                confirm=True,
            )
            _clear()
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def open_dn_dialog_if_armed(services: dict) -> None:
    if st.session_state.get(DN_DIALOG) == "new":
        delivery_note_dialog(services)
