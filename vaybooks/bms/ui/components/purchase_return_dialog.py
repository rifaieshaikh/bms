"""Purchase return dialog."""

from __future__ import annotations

from datetime import date

import streamlit as st

from vaybooks.bms.domain.shared.enums import CatalogItemType
from vaybooks.bms.ui.components.purchase_invoice_form import (
    ensure_selectbox_option,
    reset_dialog_state,
    vendor_option_map,
    vendor_select_index,
)
from vaybooks.bms.ui.components.purchase_line_ui import default_purchase_line, item_option_map
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler

RETURN_DIALOG = "purchase_return_dialog"
_LINES_KEY = f"{RETURN_DIALOG}_lines"


def arm_return_dialog(source_bill_id: str | None = None) -> None:
    reset_dialog_state(RETURN_DIALOG)
    st.session_state[RETURN_DIALOG] = "new"
    if source_bill_id:
        st.session_state[f"{RETURN_DIALOG}_bill_id"] = source_bill_id


def _clear() -> None:
    for key in list(st.session_state.keys()):
        if key.startswith(RETURN_DIALOG):
            st.session_state.pop(key, None)


@st.dialog("Record Purchase Return", width="large", on_dismiss=make_dismiss_handler(RETURN_DIALOG))
def purchase_return_dialog(services: dict) -> None:
    if st.session_state.get(RETURN_DIALOG) != "new":
        return

    purchases = services["purchases"]
    accounting = services["accounting"]
    vendors = services["vendors"]
    inventory = services.get("inventory")

    vendor_list = vendors.list_all_vendors()
    if not vendor_list:
        st.error("Add a vendor first.")
        return
    vendor_opts = vendor_option_map(vendor_list)
    vendor_names = list(vendor_opts.keys())
    vendor_key = f"{RETURN_DIALOG}_vendor"
    ensure_selectbox_option(vendor_key, vendor_names)
    vendor_name = st.selectbox(
        "Vendor",
        vendor_names,
        index=vendor_select_index(vendor_opts, None),
        key=vendor_key,
    )
    vendor_id = vendor_opts.get(vendor_name)
    if not vendor_id:
        st.warning("Select a vendor.")
        return

    products = inventory.list_products(active_only=True) if inventory else []
    product_opts = item_option_map(products, lambda p: f"{p.sku} — {p.name}")
    product_names = ["—"] + list(product_opts.keys())

    if _LINES_KEY not in st.session_state:
        st.session_state[_LINES_KEY] = [default_purchase_line()]

    return_date = st.date_input("Return date", value=date.today(), key=f"{RETURN_DIALOG}_date")
    source_bill_id = st.session_state.get(f"{RETURN_DIALOG}_bill_id")

    line_items = list(st.session_state[_LINES_KEY])
    for i, row in enumerate(line_items):
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 1, 1])
            prod_key = f"{RETURN_DIALOG}_prod_{i}"
            ensure_selectbox_option(prod_key, product_names)
            picked = c1.selectbox("Product", product_names, key=prod_key)
            if picked != "—":
                row["product_id"] = product_opts[picked]
                row["item_id"] = row["product_id"]
                row["item_type"] = CatalogItemType.PRODUCT.value
                row["product_name"] = picked
            row["qty"] = c2.number_input(
                "Qty", min_value=0.0, value=float(row.get("qty") or 1),
                key=f"{RETURN_DIALOG}_qty_{i}",
            )
            row["rate"] = c3.number_input(
                "Rate (ex-GST)", min_value=0.0, value=float(row.get("rate") or 0),
                key=f"{RETURN_DIALOG}_rate_{i}",
            )
        line_items[i] = row
    st.session_state[_LINES_KEY] = line_items

    refund = st.number_input("Cash refund", min_value=0.0, value=0.0, key=f"{RETURN_DIALOG}_refund")
    refund_acct = None
    if refund > 0:
        store_accounts = accounting.get_store_accounts()
        if not store_accounts:
            st.error("No cash/bank account found for refund.")
            return
        store_opts = {a.account_name: a.id for a in store_accounts}
        store_names = list(store_opts.keys())
        refund_key = f"{RETURN_DIALOG}_refund_acct"
        ensure_selectbox_option(refund_key, store_names)
        refund_picked = st.selectbox("Refund account", store_names, key=refund_key)
        refund_acct = store_opts.get(refund_picked)

    if st.button("Save return", type="primary"):
        try:
            resolved = purchases.resolve_purchase_lines(line_items, vendor_id)
            lines = [
                {
                    "product_id": row.product_id or "",
                    "product_name": row.item_name,
                    "qty": row.qty,
                    "rate": row.rate,
                    "expense_account_id": row.expense_account_id,
                }
                for row in resolved
                if row.qty > 0
            ]
            purchases.create_purchase_return(
                vendor_id=vendor_id,
                return_date=return_date,
                lines=lines,
                source_bill_id=source_bill_id,
                amount_refunded=refund,
                refund_account_id=refund_acct,
            )
            _clear()
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def open_return_dialog_if_armed(services: dict) -> None:
    if st.session_state.get(RETURN_DIALOG) == "new":
        purchase_return_dialog(services)
