"""Sales return dialog."""

from __future__ import annotations

from datetime import date

import streamlit as st

from vaybooks.bms.ui.components.purchase_invoice_form import ensure_selectbox_option
from vaybooks.bms.ui.components.purchase_line_ui import default_purchase_line, item_option_map
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler

SALES_RETURN_DIALOG = "sales_return_dialog"
_LINES_KEY = f"{SALES_RETURN_DIALOG}_lines"


def arm_sales_return_dialog(source_invoice_id: str | None = None) -> None:
    for key in list(st.session_state.keys()):
        if key.startswith(SALES_RETURN_DIALOG):
            st.session_state.pop(key, None)
    st.session_state[SALES_RETURN_DIALOG] = "new"
    st.session_state[_LINES_KEY] = [default_purchase_line()]
    if source_invoice_id:
        st.session_state[f"{SALES_RETURN_DIALOG}_invoice_id"] = source_invoice_id


def _clear() -> None:
    for key in list(st.session_state.keys()):
        if key.startswith(SALES_RETURN_DIALOG):
            st.session_state.pop(key, None)


@st.dialog("Record Sales Return", width="large", on_dismiss=make_dismiss_handler(SALES_RETURN_DIALOG))
def sales_return_dialog(services: dict) -> None:
    if st.session_state.get(SALES_RETURN_DIALOG) != "new":
        return

    sales = services["sales"]
    accounting = services["accounting"]
    customers = services["customers"]
    inventory = services.get("inventory")

    customer_list = customers.list_all_customers()
    if not customer_list:
        st.error("Add a customer first.")
        return
    cust_opts = {c.customer_name: c.id for c in customer_list}
    cust_names = list(cust_opts.keys())
    cust_key = f"{SALES_RETURN_DIALOG}_customer"
    ensure_selectbox_option(cust_key, cust_names)
    customer_name = st.selectbox("Customer", cust_names, key=cust_key)
    customer_id = cust_opts.get(customer_name)
    if not customer_id:
        st.warning("Select a customer.")
        return

    products = inventory.list_products(active_only=True) if inventory else []
    product_opts = item_option_map(products, lambda p: f"{p.sku} — {p.name}")
    product_names = ["—"] + list(product_opts.keys())

    return_date = st.date_input("Return date", value=date.today(), key=f"{SALES_RETURN_DIALOG}_date")
    source_invoice_id = st.session_state.get(f"{SALES_RETURN_DIALOG}_invoice_id")

    line_items = list(st.session_state.get(_LINES_KEY, [default_purchase_line()]))
    for i, row in enumerate(line_items):
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 1, 1])
            prod_key = f"{SALES_RETURN_DIALOG}_prod_{i}"
            ensure_selectbox_option(prod_key, product_names)
            picked = c1.selectbox("Product", product_names, key=prod_key)
            if picked != "—":
                row["product_id"] = product_opts[picked]
                row["product_name"] = picked
            row["qty"] = c2.number_input(
                "Qty", min_value=0.0, value=float(row.get("qty") or 1),
                key=f"{SALES_RETURN_DIALOG}_qty_{i}",
            )
            row["rate"] = c3.number_input(
                "Rate", min_value=0.0, value=float(row.get("rate") or 0),
                key=f"{SALES_RETURN_DIALOG}_rate_{i}",
            )
        line_items[i] = row
    st.session_state[_LINES_KEY] = line_items

    refund = st.number_input("Cash refund", min_value=0.0, value=0.0, key=f"{SALES_RETURN_DIALOG}_refund")
    refund_acct = None
    if refund > 0:
        store_accounts = accounting.get_store_accounts()
        if not store_accounts:
            st.error("No cash/bank account found for refund.")
            return
        store_opts = {a.account_name: a.id for a in store_accounts}
        store_names = list(store_opts.keys())
        refund_key = f"{SALES_RETURN_DIALOG}_refund_acct"
        ensure_selectbox_option(refund_key, store_names)
        refund_picked = st.selectbox("Refund account", store_names, key=refund_key)
        refund_acct = store_opts.get(refund_picked)

    if st.button("Save return", type="primary"):
        try:
            lines = [
                {
                    "product_id": row.get("product_id") or "",
                    "product_name": row.get("product_name") or "",
                    "qty": float(row.get("qty") or 0),
                    "rate": float(row.get("rate") or 0),
                }
                for row in line_items
                if row.get("product_id") and float(row.get("qty") or 0) > 0
            ]
            if not lines:
                raise ValueError("Add at least one return line")
            sales.create_sales_return(
                customer_id=customer_id,
                return_date=return_date,
                lines=lines,
                source_invoice_id=source_invoice_id,
                amount_refunded=refund,
                refund_account_id=refund_acct,
            )
            _clear()
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def open_sales_return_dialog_if_armed(services: dict) -> None:
    if st.session_state.get(SALES_RETURN_DIALOG) == "new":
        sales_return_dialog(services)
