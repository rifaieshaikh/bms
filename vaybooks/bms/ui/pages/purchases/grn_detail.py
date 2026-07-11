"""GRN detail."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.ui import navigation


def render(services: dict) -> None:
    grn_id = st.query_params.get("id")
    if not grn_id:
        st.warning("GRN not specified")
        return

    grn = services["purchases"].get_goods_receipt(grn_id)
    if not grn:
        st.warning("Goods receipt not found")
        return

    if st.button("← Back", key="grn_detail_back"):
        navigation.go_back_to_list("goods_receipt_list", "goods-receipt")
        return

    st.title(grn.grn_number)
    st.caption(f"Vendor: {grn.vendor_name}")
    if grn.po_number:
        st.caption(f"PO: {grn.po_number}")
    st.caption(f"Status: {grn.status.value}")
    st.caption(f"Receipt date: {grn.receipt_date}")
    st.caption(
        f"Landed extras — Freight ₹{grn.freight:,.0f}, Duty ₹{grn.duty:,.0f}, Other ₹{grn.other:,.0f}"
    )

    for line in grn.lines:
        with st.container(border=True):
            st.write(line.product_name or line.product_id)
            st.caption(
                f"Qty {line.qty_received:g} @ ₹{line.rate:,.2f} · "
                f"Unit cost ₹{line.unit_cost:,.2f}"
            )
