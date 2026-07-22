"""Create purchase order dialog (product-only lines via data_editor table)."""

from __future__ import annotations

import logging
import time
from datetime import date

import streamlit as st

from vaybooks.bms.domain.shared.enums import CatalogItemType, PurchaseOrderStatus
from vaybooks.bms.ui.components.common.dialog_state import (
    ensure_selectbox_option,
    reset_dialog_state,
)
from vaybooks.bms.ui.components.purchases.purchase_invoice_form import (
    vendor_option_map,
    vendor_select_index,
)
from vaybooks.bms.ui.components.purchases.purchase_line_ui import vendor_is_registered
from vaybooks.bms.ui.components.purchases.purchase_lines_editor import (
    render_purchase_lines_editor,
)
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler, register_armed_dialog
from vaybooks.bms.ui.keyboard.dialog_actions import consume_submit, open_dialog
from vaybooks.bms.ui.keyboard.focus_manager import inject_focus_manager
from vaybooks.bms.ui.keyboard.wired import mark_wired

logger = logging.getLogger(__name__)

PO_DIALOG = "purchase_order_dialog"
PO_CREATE_SUCCESS_KEY = "po_create_success"
PO_SUBMIT_KEY = "po_dialog_submit"
PO_FOCUS_KEY = f"{PO_DIALOG}_focus"
PO_PRODUCTS_CACHE_KEY = f"{PO_DIALOG}_products_cache"


def _cached_products(inventory) -> list:
    """Load active products once per dialog open (invalidate on catalog return)."""
    cached = st.session_state.get(PO_PRODUCTS_CACHE_KEY)
    if cached is not None:
        logger.debug("po_dialog.list_products cache_hit count=%s", len(cached))
        return cached
    if not inventory:
        return []
    started = time.perf_counter()
    products = inventory.list_products(active_only=True)
    st.session_state[PO_PRODUCTS_CACHE_KEY] = products
    logger.debug(
        "po_dialog.list_products cache_miss count=%s duration_ms=%.1f",
        len(products),
        (time.perf_counter() - started) * 1000,
    )
    return products


def arm_po_dialog() -> None:
    reset_dialog_state(PO_DIALOG)
    open_dialog(PO_DIALOG, submit_key=PO_SUBMIT_KEY, value="new", clear_others=True)
    st.session_state[PO_FOCUS_KEY] = f"{PO_DIALOG}_vendor"
    mark_wired("dialog.save")


def _clear() -> None:
    for key in list(st.session_state.keys()):
        if key.startswith(PO_DIALOG):
            st.session_state.pop(key, None)
    st.session_state.pop(PO_SUBMIT_KEY, None)


def consume_po_create_success() -> None:
    """Show a toast when a PO was just created (call from the list page)."""
    po_number = st.session_state.pop(PO_CREATE_SUCCESS_KEY, None)
    if po_number:
        st.toast(
            f"Purchase order {po_number} created",
            icon=":material/check_circle:",
        )


@st.dialog("Create Purchase Order", width="large", on_dismiss=make_dismiss_handler(PO_DIALOG))
def purchase_order_dialog(services: dict) -> None:
    if st.session_state.get(PO_DIALOG) != "new":
        return

    register_armed_dialog(PO_DIALOG)
    mark_wired("dialog.save")

    purchases = services["purchases"]
    vendors = services["vendors"]
    inventory = services.get("inventory")
    business = services["business"].get_profile()

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
    vendor = vendors.get_vendor_detail(vendor_id)

    products = _cached_products(inventory)

    c1, c2 = st.columns(2)
    order_date = c1.date_input("Order date", value=date.today(), key=f"{PO_DIALOG}_date")
    expected_date = c2.date_input(
        "Expected date", value=date.today(), key=f"{PO_DIALOG}_expected"
    )
    notes = st.text_input("Notes", key=f"{PO_DIALOG}_notes")

    st.markdown("**Line items**")
    st.caption(
        "Purchase orders are product-only. Pick a product — HSN, rate, and totals fill from the catalog. "
        "Keyboard: Vendor → Expected → Item table (Enter / Tab). **Ctrl+S** saves."
    )
    vendor_registered = vendor_is_registered(vendor)
    line_items, gst_errors = render_purchase_lines_editor(
        key_prefix=PO_DIALOG,
        products=products,
        services=[],
        vendor_id=vendor_id,
        purchases_service=purchases,
        inventory_service=inventory,
        allow_services=False,
        qty_field="qty_ordered",
        vendor_registered=vendor_registered,
        business=business,
        business_state_code=business.state_code if business else "",
        vendor_state_code=vendor.state_code if vendor else "",
        catalog_return_to=PO_DIALOG,
    )

    # After the table exists: Enter on Expected focuses Item cell; in-grid Enter→Tab
    editor_key = f"{PO_DIALOG}_lines_editor"
    restore = st.session_state.pop(PO_FOCUS_KEY, None)
    inject_focus_manager(
        [vendor_key, f"{PO_DIALOG}_expected"],
        initial_key=vendor_key,
        restore_key=restore,
        data_editor_key=editor_key,
        component_key=f"po_editor_bridge_{vendor_id[:8]}",
    )

    save_cols = st.columns(2)
    do_save = save_cols[0].button(
        "Save PO", type="primary", use_container_width=True
    ) or consume_submit(PO_SUBMIT_KEY)
    if do_save:
        try:
            if gst_errors:
                raise ValueError(gst_errors[0])
            if not line_items:
                raise ValueError("Add at least one product line")
            for row in line_items:
                row["item_type"] = CatalogItemType.PRODUCT.value
                if not row.get("product_id"):
                    row["product_id"] = row.get("item_id")
            resolved = purchases.resolve_purchase_lines(line_items, vendor_id)
            po_lines = []
            for line in resolved:
                if line.item_type != CatalogItemType.PRODUCT:
                    continue
                po_lines.append(
                    {
                        "product_id": line.product_id or line.item_id,
                        "product_name": line.item_name,
                        "qty_ordered": line.qty,
                        "rate": line.rate,
                        "expense_account_id": line.expense_account_id,
                    }
                )
            if not po_lines:
                raise ValueError("Add at least one product line")
            created = purchases.create_purchase_order(
                vendor_id=vendor_id,
                order_date=order_date,
                expected_date=expected_date,
                lines=po_lines,
                notes=notes,
                status=PurchaseOrderStatus.SENT,
            )
            st.session_state[PO_CREATE_SUCCESS_KEY] = created.po_number
            _clear()
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if save_cols[1].button("Cancel", use_container_width=True):
        _clear()
        st.rerun()


def open_po_dialog_if_armed(services: dict) -> None:
    from vaybooks.bms.ui.components.inventory.catalog_item_dialog import (
        CATALOG_ITEM_DIALOG,
        catalog_item_dialog,
    )

    if st.session_state.get(CATALOG_ITEM_DIALOG):
        catalog_item_dialog(services)
    elif st.session_state.get(PO_DIALOG) == "new":
        purchase_order_dialog(services)
