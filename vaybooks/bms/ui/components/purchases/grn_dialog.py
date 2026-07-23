"""Receive goods (GRN) dialog."""

from __future__ import annotations

from datetime import date

import streamlit as st

from vaybooks.bms.ui.components.common.dialog_state import (
    ensure_selectbox_option,
    reset_dialog_state,
)
from vaybooks.bms.ui.components.purchases.grn_receive_table import (
    grn_table_focus_chain,
    grn_table_focus_columns,
    render_grn_receive_table,
)
from vaybooks.bms.ui.components.purchases.purchase_invoice_form import (
    vendor_option_map,
    vendor_select_index,
)
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler
from vaybooks.bms.ui.keyboard.focus.registry import get_strategy

GRN_DIALOG = "grn_dialog"
GRN_FOCUS_KEY = f"{GRN_DIALOG}_focus"
GRN_OVER_CONFIRM_KEY = f"{GRN_DIALOG}_over_confirm"


def arm_grn_dialog(po_id: str | None = None) -> None:
    reset_dialog_state(GRN_DIALOG)
    st.session_state[GRN_DIALOG] = "new"
    st.session_state[GRN_FOCUS_KEY] = f"{GRN_DIALOG}_date"
    if po_id:
        st.session_state[f"{GRN_DIALOG}_po_id"] = po_id


def _clear() -> None:
    for key in list(st.session_state.keys()):
        if key.startswith(GRN_DIALOG):
            st.session_state.pop(key, None)


def _submit_grn(
    *,
    purchases,
    vendor_id: str,
    receipt_date,
    lines: list[dict],
    po_id: str | None,
    freight: float,
    duty: float,
    other: float,
    allow_over_receive: bool,
) -> None:
    purchases.create_goods_receipt(
        vendor_id=vendor_id,
        receipt_date=receipt_date,
        lines=lines,
        purchase_order_id=po_id,
        freight=freight,
        duty=duty,
        other=other,
        confirm=True,
        allow_over_receive=allow_over_receive,
    )
    _clear()
    st.rerun()


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
    po_key = f"{GRN_DIALOG}_po"
    po_label = st.selectbox(
        "Purchase order",
        list(po_opts.keys()),
        index=list(po_opts.values()).index(pre_po) if pre_po in po_opts.values() else 0,
        key=po_key,
    )
    po_id = po_opts[po_label]
    po = purchases.get_purchase_order(po_id) if po_id else None

    vendor_id = po.vendor_id if po else None
    vendor_key = f"{GRN_DIALOG}_vendor"
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
            get_strategy(GRN_DIALOG).inject(
                chain=[po_key, vendor_key],
                restore_key=st.session_state.pop(GRN_FOCUS_KEY, None),
                component_key="grn_direct_vendor",
            )
            return
        st.info("Select a PO to receive against, or use direct bill for quick purchases.")
        get_strategy(GRN_DIALOG).inject(
            chain=[po_key, vendor_key],
            restore_key=st.session_state.pop(GRN_FOCUS_KEY, None),
            component_key="grn_direct_no_grid",
        )
        return

    date_key = f"{GRN_DIALOG}_date"
    freight_key = f"{GRN_DIALOG}_freight"
    duty_key = f"{GRN_DIALOG}_duty"
    other_key = f"{GRN_DIALOG}_other"
    confirm_key = f"{GRN_DIALOG}_confirm"

    receipt_date = st.date_input("Receipt date", value=date.today(), key=date_key)
    freight = st.number_input("Freight", min_value=0.0, value=0.0, key=freight_key)
    duty = st.number_input("Duty", min_value=0.0, value=0.0, key=duty_key)
    other = st.number_input("Other", min_value=0.0, value=0.0, key=other_key)

    st.markdown("**Receive quantities**")
    lines, overages = render_grn_receive_table(
        key_prefix=GRN_DIALOG, po_lines=list(po.lines or [])
    )

    awaiting_over_confirm = bool(st.session_state.get(GRN_OVER_CONFIRM_KEY))

    if awaiting_over_confirm and overages:
        st.warning(
            "One or more lines receive more than pending "
            "(Qty ordered − Previously received)."
        )
        for row in overages:
            st.caption(
                f"• {row['product_name']}: Received {row['qty_received']:g} "
                f"(pending {row['pending']:g}, excess {row['excess']:g})"
            )
        proceed_key = f"{GRN_DIALOG}_over_proceed"
        back_key = f"{GRN_DIALOG}_over_back"
        btn_cols = st.columns(2)
        if btn_cols[0].button(
            "Proceed anyway", type="primary", use_container_width=True, key=proceed_key
        ):
            try:
                st.session_state.pop(GRN_OVER_CONFIRM_KEY, None)
                _submit_grn(
                    purchases=purchases,
                    vendor_id=vendor_id,
                    receipt_date=receipt_date,
                    lines=lines,
                    po_id=po_id,
                    freight=freight,
                    duty=duty,
                    other=other,
                    allow_over_receive=True,
                )
            except Exception as exc:
                st.error(str(exc))
        if btn_cols[1].button("Back", use_container_width=True, key=back_key):
            st.session_state.pop(GRN_OVER_CONFIRM_KEY, None)
            st.rerun()

        get_strategy(GRN_DIALOG).inject(
            chain=[proceed_key, back_key],
            restore_key=proceed_key,
            component_key="grn_over_confirm",
        )
        return

    if awaiting_over_confirm and not overages:
        st.session_state.pop(GRN_OVER_CONFIRM_KEY, None)

    do_confirm = st.button("Confirm GRN", type="primary", key=confirm_key)

    qty_chain = grn_table_focus_chain(GRN_DIALOG)
    qty_columns = grn_table_focus_columns(GRN_DIALOG)
    restore = st.session_state.pop(GRN_FOCUS_KEY, None)
    get_strategy(GRN_DIALOG).inject(
        chain=[date_key, freight_key, duty_key, other_key, *qty_chain, confirm_key],
        restore_key=restore,
        columns=qty_columns,
        above_first=other_key,
        below_last=confirm_key,
        component_key=f"grn_recv_{po.id[:8]}_{len(qty_chain)}",
    )

    if do_confirm:
        try:
            if not lines:
                raise ValueError("Enter at least one received quantity")
            if overages:
                st.session_state[GRN_OVER_CONFIRM_KEY] = True
                st.rerun()
            _submit_grn(
                purchases=purchases,
                vendor_id=vendor_id,
                receipt_date=receipt_date,
                lines=lines,
                po_id=po_id,
                freight=freight,
                duty=duty,
                other=other,
                allow_over_receive=False,
            )
        except Exception as exc:
            st.error(str(exc))


def open_grn_dialog_if_armed(services: dict) -> None:
    if st.session_state.get(GRN_DIALOG) == "new":
        grn_dialog(services)
