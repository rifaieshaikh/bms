"""Delivery note dialog."""

from __future__ import annotations

from datetime import date

import streamlit as st

from vaybooks.bms.ui.components.purchase_invoice_form import ensure_selectbox_option
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler

DN_DIALOG = "delivery_note_dialog"


def arm_dn_dialog(so_id: str | None = None) -> None:
    for key in list(st.session_state.keys()):
        if key.startswith(DN_DIALOG):
            st.session_state.pop(key, None)
    st.session_state[DN_DIALOG] = "new"
    if so_id:
        st.session_state[f"{DN_DIALOG}_so_id"] = so_id


def _clear() -> None:
    for key in list(st.session_state.keys()):
        if key.startswith(DN_DIALOG):
            st.session_state.pop(key, None)


@st.dialog("Create Delivery Note", width="large", on_dismiss=make_dismiss_handler(DN_DIALOG))
def delivery_note_dialog(services: dict) -> None:
    if st.session_state.get(DN_DIALOG) != "new":
        return

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
    so_label = st.selectbox(
        "Sales order",
        list(so_opts.keys()),
        index=list(so_opts.values()).index(pre_so) if pre_so in so_opts.values() else 0,
        key=f"{DN_DIALOG}_so",
    )
    so_id = so_opts[so_label]
    so = sales.get_sales_order(so_id) if so_id else None

    customer_id = so.customer_id if so else None
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
        cust_key = f"{DN_DIALOG}_customer"
        ensure_selectbox_option(cust_key, cust_names)
        customer_name = st.selectbox("Customer", cust_names, key=cust_key)
        customer_id = cust_opts.get(customer_name)
        if not customer_id:
            st.warning("Select a customer.")
            return
        st.info("Select a sales order to deliver against, or create a sales order first.")

    delivery_date = st.date_input("Delivery date", value=date.today(), key=f"{DN_DIALOG}_date")

    lines = []
    if so:
        st.markdown("**Deliver quantities**")
        for i, sl in enumerate(so.lines):
            pending = sl.qty_pending
            if pending <= 0:
                continue
            qty = st.number_input(
                f"{sl.product_name or sl.product_id} (pending {pending:g})",
                min_value=0.0,
                max_value=float(pending),
                value=float(pending),
                key=f"{DN_DIALOG}_line_{i}",
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
    else:
        st.info("Delivery without a sales order is not supported. Select an open SO.")

    if st.button("Confirm delivery", type="primary"):
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
