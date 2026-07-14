"""Purchase bill detail with edit/delete."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.domain.shared.enums import VoucherType
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.purchase_return_dialog import arm_return_dialog, open_return_dialog_if_armed


def render(services: dict) -> None:
    from vaybooks.bms.ui.keyboard.actions import consume_action
    from vaybooks.bms.ui.keyboard.context import set_current_page
    from vaybooks.bms.ui.keyboard.wired import mark_wired

    set_current_page("purchase_detail")
    mark_wired("nav.back")
    bill_id = st.query_params.get("id")
    if not bill_id:
        st.warning("Purchase bill not specified")
        return

    purchases = services["purchases"]
    accounting = services["accounting"]
    row = purchases.get_purchase_bill(bill_id)
    voucher = accounting.get_voucher(bill_id)
    if not row or not voucher:
        st.warning("Purchase bill not found")
        return

    if st.button("← Back", key="purchase_detail_back") or consume_action("nav.back"):
        navigation.go_back_to_list("purchases_list", "purchases")
        return

    st.title(row.get("vendor_bill_number") or voucher.voucher_number)
    st.caption(f"Vendor: {row.get('vendor_name')}")
    st.caption(f"Type: {row.get('voucher_type')}")
    st.caption(f"Date: {row.get('bill_date')}")
    st.metric("Total", f"₹{float(row.get('total') or 0):,.0f}")
    st.metric("Paid", f"₹{float(row.get('paid') or 0):,.0f}")
    st.metric("Outstanding", f"₹{float(row.get('outstanding') or 0):,.0f}")

    for item in row.get("line_items") or []:
        with st.container(border=True):
            st.write(item.get("product_name") or item.get("product_id") or "Line")
            st.caption(
                f"Qty {item.get('qty')} @ ₹{float(item.get('rate') or 0):,.2f} · "
                f"Amount ₹{float(item.get('amount') or 0):,.0f}"
            )

    if voucher.voucher_type == VoucherType.PURCHASE_BILL:
        cols = st.columns(2)
        if cols[0].button("Record return", key="bill_return_btn"):
            arm_return_dialog(source_bill_id=bill_id)
            st.rerun()
        if cols[1].button("Delete bill", key="bill_delete_btn"):
            try:
                purchases.delete_purchase_bill(bill_id)
                navigation.go_back_to_list("purchases_list", "purchases")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    open_return_dialog_if_armed(services)
