"""Create purchase order dialog."""

from __future__ import annotations

from datetime import date

import streamlit as st

from vaybooks.bms.domain.shared.enums import CatalogItemType, PurchaseOrderStatus
from vaybooks.bms.ui.components.purchase_invoice_form import (
    ensure_selectbox_option,
    reset_dialog_state,
    vendor_option_map,
    vendor_select_index,
)
from vaybooks.bms.ui.components.purchase_line_ui import (
    default_purchase_line,
    item_option_map,
)
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler

PO_DIALOG = "purchase_order_dialog"
_LINES_KEY = f"{PO_DIALOG}_lines"


def arm_po_dialog() -> None:
    reset_dialog_state(PO_DIALOG)
    st.session_state[PO_DIALOG] = "new"


def _clear() -> None:
    for key in list(st.session_state.keys()):
        if key.startswith(PO_DIALOG):
            st.session_state.pop(key, None)


@st.dialog("Create Purchase Order", width="large", on_dismiss=make_dismiss_handler(PO_DIALOG))
def purchase_order_dialog(services: dict) -> None:
    if st.session_state.get(PO_DIALOG) != "new":
        return

    purchases = services["purchases"]
    vendors = services["vendors"]
    inventory = services.get("inventory")
    vendor_services = services["vendor_services"]

    vendor_list = vendors.list_all_vendors()
    if not vendor_list:
        st.error("Add a vendor first.")
        return
    vendor_opts = vendor_option_map(vendor_list)
    vendor_names = list(vendor_opts.keys())
    vendor_key = f"{PO_DIALOG}_vendor"
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
    services_list = vendor_services.list_services(active_only=True)

    if _LINES_KEY not in st.session_state:
        st.session_state[_LINES_KEY] = [default_purchase_line()]

    c1, c2 = st.columns(2)
    order_date = c1.date_input("Order date", value=date.today(), key=f"{PO_DIALOG}_date")
    expected_date = c2.date_input("Expected date", value=date.today(), key=f"{PO_DIALOG}_expected")
    notes = st.text_input("Notes", key=f"{PO_DIALOG}_notes")

    line_items = list(st.session_state[_LINES_KEY])
    for i, row in enumerate(line_items):
        with st.container(border=True):
            type_col, item_col = st.columns([1, 3])
            item_type = type_col.selectbox(
                "Type",
                [CatalogItemType.PRODUCT.value, CatalogItemType.SERVICE.value],
                index=0 if row.get("item_type") != CatalogItemType.SERVICE.value else 1,
                key=f"{PO_DIALOG}_type_{i}",
            )
            row["item_type"] = item_type
            if item_type == CatalogItemType.SERVICE.value:
                opts = item_option_map(services_list, lambda s: s.service_name)
            else:
                opts = item_option_map(products, lambda p: f"{p.sku} — {p.name}")
            labels = ["—"] + list(opts.keys())
            current = "—"
            if row.get("item_id") in opts.values():
                current = next(k for k, v in opts.items() if v == row.get("item_id"))
            picked = item_col.selectbox(
                "Item", labels,
                index=labels.index(current) if current in labels else 0,
                key=f"{PO_DIALOG}_item_{i}",
            )
            if picked != "—":
                row["item_id"] = opts[picked]
                row["product_id"] = row["item_id"] if item_type == CatalogItemType.PRODUCT.value else None
                row["product_name"] = picked
            c2, c3 = st.columns(2)
            row["qty_ordered"] = c2.number_input(
                "Qty", min_value=0.0, value=float(row.get("qty") or row.get("qty_ordered") or 1),
                key=f"{PO_DIALOG}_qty_{i}",
            )
            row["qty"] = row["qty_ordered"]
            row["rate"] = c3.number_input(
                "Rate (ex-GST)", min_value=0.0, value=float(row.get("rate") or 0),
                key=f"{PO_DIALOG}_rate_{i}",
            )
        line_items[i] = row
    st.session_state[_LINES_KEY] = line_items

    if st.button("+ Add line", key=f"{PO_DIALOG}_add"):
        line_items.append(default_purchase_line())
        st.session_state[_LINES_KEY] = line_items
        st.rerun()

    if st.button("Save PO", type="primary"):
        try:
            resolved = purchases.resolve_purchase_lines(line_items, vendor_id)
            po_lines = []
            for raw, line in zip(line_items, resolved):
                po_lines.append(
                    {
                        "product_id": raw.get("product_id") or "",
                        "product_name": line.item_name,
                        "qty_ordered": line.qty,
                        "rate": line.rate,
                        "expense_account_id": line.expense_account_id,
                    }
                )
            purchases.create_purchase_order(
                vendor_id=vendor_id,
                order_date=order_date,
                expected_date=expected_date,
                lines=po_lines,
                notes=notes,
                status=PurchaseOrderStatus.SENT,
            )
            _clear()
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def open_po_dialog_if_armed(services: dict) -> None:
    if st.session_state.get(PO_DIALOG) == "new":
        purchase_order_dialog(services)
