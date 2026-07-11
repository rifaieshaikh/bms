"""Create sales order dialog."""

from __future__ import annotations

from datetime import date

import streamlit as st

from vaybooks.bms.domain.shared.enums import SalesOrderStatus
from vaybooks.bms.ui.components.purchase_invoice_form import ensure_selectbox_option
from vaybooks.bms.ui.components.purchase_line_ui import default_purchase_line, item_option_map
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler

SO_DIALOG = "sales_order_dialog"
_LINES_KEY = f"{SO_DIALOG}_lines"


def arm_so_dialog() -> None:
    for key in list(st.session_state.keys()):
        if key.startswith(SO_DIALOG):
            st.session_state.pop(key, None)
    st.session_state[SO_DIALOG] = "new"
    st.session_state[_LINES_KEY] = [default_purchase_line()]


def _clear() -> None:
    for key in list(st.session_state.keys()):
        if key.startswith(SO_DIALOG):
            st.session_state.pop(key, None)


@st.dialog("Create Sales Order", width="large", on_dismiss=make_dismiss_handler(SO_DIALOG))
def sales_order_dialog(services: dict) -> None:
    if st.session_state.get(SO_DIALOG) != "new":
        return

    sales = services["sales"]
    customers = services["customers"]
    inventory = services.get("inventory")

    customer_list = customers.list_all_customers()
    if not customer_list:
        st.error("Add a customer first.")
        return
    cust_opts = {c.customer_name: c.id for c in customer_list}
    cust_names = list(cust_opts.keys())
    cust_key = f"{SO_DIALOG}_customer"
    ensure_selectbox_option(cust_key, cust_names)
    customer_name = st.selectbox("Customer", cust_names, key=cust_key)
    customer_id = cust_opts.get(customer_name)
    if not customer_id:
        st.warning("Select a customer.")
        return

    products = inventory.list_products(active_only=True) if inventory else []
    if not products:
        st.error("Add inventory products first.")
        return
    product_opts = item_option_map(products, lambda p: f"{p.sku} — {p.name}")

    if _LINES_KEY not in st.session_state:
        st.session_state[_LINES_KEY] = [default_purchase_line()]

    c1, c2 = st.columns(2)
    order_date = c1.date_input("Order date", value=date.today(), key=f"{SO_DIALOG}_date")
    expected_date = c2.date_input("Expected date", value=date.today(), key=f"{SO_DIALOG}_expected")
    notes = st.text_input("Notes", key=f"{SO_DIALOG}_notes")

    line_items = list(st.session_state[_LINES_KEY])
    for i, row in enumerate(line_items):
        with st.container(border=True):
            labels = ["—"] + list(product_opts.keys())
            current = "—"
            if row.get("product_id") in product_opts.values():
                current = next(k for k, v in product_opts.items() if v == row.get("product_id"))
            picked = st.selectbox(
                "Product", labels,
                index=labels.index(current) if current in labels else 0,
                key=f"{SO_DIALOG}_item_{i}",
            )
            if picked != "—":
                row["product_id"] = product_opts[picked]
                row["product_name"] = picked
            c2, c3 = st.columns(2)
            row["qty_ordered"] = c2.number_input(
                "Qty", min_value=0.0,
                value=float(row.get("qty") or row.get("qty_ordered") or 1),
                key=f"{SO_DIALOG}_qty_{i}",
            )
            row["rate"] = c3.number_input(
                "Rate", min_value=0.0, value=float(row.get("rate") or 0),
                key=f"{SO_DIALOG}_rate_{i}",
            )
        line_items[i] = row
    st.session_state[_LINES_KEY] = line_items

    if st.button("+ Add line", key=f"{SO_DIALOG}_add"):
        line_items.append(default_purchase_line())
        st.session_state[_LINES_KEY] = line_items
        st.rerun()

    if st.button("Save SO", type="primary"):
        try:
            so_lines = [
                {
                    "product_id": row.get("product_id") or "",
                    "product_name": row.get("product_name") or "",
                    "qty_ordered": float(row.get("qty_ordered") or 0),
                    "rate": float(row.get("rate") or 0),
                }
                for row in line_items
                if row.get("product_id") and float(row.get("qty_ordered") or 0) > 0
            ]
            if not so_lines:
                raise ValueError("Add at least one product line")
            sales.create_sales_order(
                customer_id=customer_id,
                order_date=order_date,
                expected_date=expected_date,
                lines=so_lines,
                notes=notes,
                status=SalesOrderStatus.CONFIRMED,
            )
            _clear()
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def open_so_dialog_if_armed(services: dict) -> None:
    if st.session_state.get(SO_DIALOG) == "new":
        sales_order_dialog(services)
