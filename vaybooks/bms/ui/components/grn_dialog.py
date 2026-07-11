"""Receive goods (GRN) dialog."""

from __future__ import annotations

from datetime import date

import streamlit as st

from vaybooks.bms.ui.components.purchase_invoice_form import (
    ensure_selectbox_option,
    reset_dialog_state,
    vendor_option_map,
    vendor_select_index,
)
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler

GRN_DIALOG = "grn_dialog"


def arm_grn_dialog(po_id: str | None = None) -> None:
    reset_dialog_state(GRN_DIALOG)
    st.session_state[GRN_DIALOG] = "new"
    if po_id:
        st.session_state[f"{GRN_DIALOG}_po_id"] = po_id


def _clear() -> None:
    for key in list(st.session_state.keys()):
        if key.startswith(GRN_DIALOG):
            st.session_state.pop(key, None)


@st.dialog("Receive Goods (GRN)", width="large", on_dismiss=make_dismiss_handler(GRN_DIALOG))
def grn_dialog(services: dict) -> None:
    if st.session_state.get(GRN_DIALOG) != "new":
        return

    purchases = services["purchases"]
    open_pos = [
        po
        for po in purchases.list_purchase_orders()
        if po.status.value not in ("Cancelled", "Closed", "Received")
    ]
    po_opts = {"— Direct (no PO) —": None}
    po_opts.update({f"{po.po_number} — {po.vendor_name}": po.id for po in open_pos})

    pre_po = st.session_state.get(f"{GRN_DIALOG}_po_id")
    po_label = st.selectbox(
        "Purchase order",
        list(po_opts.keys()),
        index=list(po_opts.values()).index(pre_po) if pre_po in po_opts.values() else 0,
        key=f"{GRN_DIALOG}_po",
    )
    po_id = po_opts[po_label]
    po = purchases.get_purchase_order(po_id) if po_id else None

    vendor_id = po.vendor_id if po else None
    if not po:
        vendors = services["vendors"]
        vendor_list = vendors.list_all_vendors()
        if not vendor_list:
            st.error("Add a vendor first, or select a purchase order.")
            if st.button("Close", key=f"{GRN_DIALOG}_close"):
                _clear()
                st.rerun()
            return
        vendor_opts = vendor_option_map(vendor_list)
        vendor_names = list(vendor_opts.keys())
        vendor_key = f"{GRN_DIALOG}_vendor"
        ensure_selectbox_option(vendor_key, vendor_names)
        vendor_name = st.selectbox(
            "Vendor",
            vendor_names,
            index=vendor_select_index(vendor_opts, vendor_id),
            key=vendor_key,
        )
        vendor_id = vendor_opts.get(vendor_name)
        if not vendor_id:
            st.warning("Select a vendor.")
            return

    receipt_date = st.date_input("Receipt date", value=date.today(), key=f"{GRN_DIALOG}_date")
    freight = st.number_input("Freight", min_value=0.0, value=0.0, key=f"{GRN_DIALOG}_freight")
    duty = st.number_input("Duty", min_value=0.0, value=0.0, key=f"{GRN_DIALOG}_duty")
    other = st.number_input("Other", min_value=0.0, value=0.0, key=f"{GRN_DIALOG}_other")

    lines = []
    if po:
        st.markdown("**Receive quantities**")
        for i, pl in enumerate(po.lines):
            pending = pl.qty_pending
            if pending <= 0:
                continue
            qty = st.number_input(
                f"{pl.product_name or pl.product_id} (pending {pending:g})",
                min_value=0.0,
                max_value=float(pending),
                value=float(pending),
                key=f"{GRN_DIALOG}_line_{i}",
            )
            if qty > 0:
                lines.append(
                    {
                        "product_id": pl.product_id,
                        "product_name": pl.product_name,
                        "qty_received": qty,
                        "rate": pl.rate,
                    }
                )
    else:
        st.info("Select a PO to receive against, or use direct bill for quick purchases.")

    if st.button("Confirm GRN", type="primary"):
        try:
            if not lines:
                raise ValueError("Enter at least one received quantity")
            purchases.create_goods_receipt(
                vendor_id=vendor_id,
                receipt_date=receipt_date,
                lines=lines,
                purchase_order_id=po_id,
                freight=freight,
                duty=duty,
                other=other,
                confirm=True,
            )
            _clear()
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def open_grn_dialog_if_armed(services: dict) -> None:
    if st.session_state.get(GRN_DIALOG) == "new":
        grn_dialog(services)
