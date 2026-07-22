"""Edit dialog for purchase orders (product-only)."""

from __future__ import annotations

import logging
import time

import streamlit as st

from vaybooks.bms.domain.shared.enums import CatalogItemType, PurchaseOrderStatus
from vaybooks.bms.ui.components.purchases.purchase_line_ui import vendor_is_registered
from vaybooks.bms.ui.components.purchases.purchase_lines_editor import render_purchase_lines_editor
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler

logger = logging.getLogger(__name__)

PO_EDIT_DIALOG = "purchase_order_edit_dialog"
PO_EDIT_PRODUCTS_CACHE_KEY = f"{PO_EDIT_DIALOG}_products_cache"


def arm_po_edit_dialog(order_id: str) -> None:
    st.session_state[PO_EDIT_DIALOG] = order_id


def _clear() -> None:
    for key in list(st.session_state.keys()):
        if key == PO_EDIT_DIALOG or key.startswith(f"{PO_EDIT_DIALOG}_"):
            st.session_state.pop(key, None)


def _cached_products(inventory) -> list:
    cached = st.session_state.get(PO_EDIT_PRODUCTS_CACHE_KEY)
    if cached is not None:
        logger.debug("po_edit.list_products cache_hit count=%s", len(cached))
        return cached
    if not inventory:
        return []
    started = time.perf_counter()
    products = inventory.list_products(active_only=True)
    st.session_state[PO_EDIT_PRODUCTS_CACHE_KEY] = products
    logger.debug(
        "po_edit.list_products cache_miss count=%s duration_ms=%.1f",
        len(products),
        (time.perf_counter() - started) * 1000,
    )
    return products


@st.dialog(
    "Edit Purchase Order",
    width="large",
    on_dismiss=make_dismiss_handler(PO_EDIT_DIALOG),
)
def _po_edit_dialog(services: dict) -> None:
    order_id = st.session_state.get(PO_EDIT_DIALOG)
    if not order_id:
        return

    purchases = services["purchases"]
    inventory = services.get("inventory")
    business = services["business"].get_profile()
    vendors = services["vendors"]

    order = purchases.get_purchase_order(order_id)
    if not order:
        st.error("Purchase order not found")
        return
    if order.status in (PurchaseOrderStatus.CANCELLED, PurchaseOrderStatus.CLOSED):
        st.error("Cannot edit a closed or cancelled purchase order")
        return

    vendor = vendors.get_vendor_detail(order.vendor_id)
    products = _cached_products(inventory)

    st.caption(f"PO {order.po_number} · Vendor: {order.vendor_name}")
    order_date = st.date_input(
        "Order date", value=order.order_date, key=f"{PO_EDIT_DIALOG}_date"
    )
    expected_date = st.date_input(
        "Expected date",
        value=order.expected_date or order.order_date,
        key=f"{PO_EDIT_DIALOG}_expected",
    )
    notes = st.text_area("Notes", value=order.notes, key=f"{PO_EDIT_DIALOG}_notes")

    initial_lines = [
        {
            "item_type": CatalogItemType.PRODUCT.value,
            "item_id": line.product_id,
            "product_id": line.product_id,
            "item_name": line.product_name,
            "qty_ordered": line.qty_ordered,
            "qty": line.qty_ordered,
            "rate": line.rate,
        }
        for line in order.lines
    ]
    st.markdown("**Line items**")
    st.caption("Ordered qty cannot fall below already received for each product.")
    vendor_registered = vendor_is_registered(vendor)
    line_items, gst_errors = render_purchase_lines_editor(
        key_prefix=PO_EDIT_DIALOG,
        products=products,
        services=[],
        initial_lines=initial_lines,
        vendor_id=order.vendor_id,
        purchases_service=purchases,
        inventory_service=inventory,
        allow_services=False,
        qty_field="qty_ordered",
        vendor_registered=vendor_registered,
        business=business,
        business_state_code=business.state_code if business else "",
        vendor_state_code=vendor.state_code if vendor else "",
    )

    if st.button("Update Purchase Order", type="primary", key=f"{PO_EDIT_DIALOG}_save"):
        try:
            if gst_errors:
                raise ValueError(gst_errors[0])
            if not line_items:
                raise ValueError("Add at least one product line")
            po_lines = []
            for row in line_items:
                product_id = str(row.get("product_id") or row.get("item_id") or "")
                if not product_id:
                    continue
                po_lines.append(
                    {
                        "product_id": product_id,
                        "product_name": row.get("item_name") or "",
                        "qty_ordered": float(row.get("qty_ordered") or row.get("qty") or 0),
                        "rate": float(row.get("rate") or 0),
                        "expense_account_id": row.get("expense_account_id") or "",
                    }
                )
            # Fill expense accounts via resolve when missing
            resolve_raw = [
                {
                    "item_type": CatalogItemType.PRODUCT.value,
                    "item_id": line["product_id"],
                    "product_id": line["product_id"],
                    "qty": line["qty_ordered"],
                    "rate": line["rate"],
                }
                for line in po_lines
            ]
            resolved = purchases.resolve_purchase_lines(resolve_raw, order.vendor_id)
            for po_line, resolved_line in zip(po_lines, resolved):
                po_line["expense_account_id"] = resolved_line.expense_account_id
                po_line["product_name"] = resolved_line.item_name
            purchases.update_purchase_order(
                order.id,
                vendor_id=order.vendor_id,
                order_date=order_date,
                expected_date=expected_date,
                lines=po_lines,
                notes=notes,
            )
            _clear()
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def open_po_edit_dialog_if_armed(services: dict) -> None:
    if st.session_state.get(PO_EDIT_DIALOG):
        _po_edit_dialog(services)
