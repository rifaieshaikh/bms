"""Record purchase bill dialog."""

from __future__ import annotations

from datetime import date

import streamlit as st

from vaybooks.bms.domain.shared.enums import CatalogItemType
from vaybooks.bms.ui.components.inventory.catalog_item_dialog import CATALOG_ITEM_DIALOG
from vaybooks.bms.ui.components.common.dialog_state import (
    ensure_selectbox_option,
    reset_dialog_state,
)
from vaybooks.bms.ui.components.purchases.purchase_invoice_form import (
    vendor_option_map,
    vendor_select_index,
)
from vaybooks.bms.ui.components.purchases.purchase_line_ui import vendor_is_registered
from vaybooks.bms.ui.components.purchases.purchase_lines_editor import render_purchase_lines_editor
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler

PURCHASE_BILL_DIALOG = "purchase_bill_dialog"


def arm_purchase_bill_dialog(**prefill) -> None:
    reset_dialog_state(PURCHASE_BILL_DIALOG)
    st.session_state[PURCHASE_BILL_DIALOG] = "new"
    for key, value in prefill.items():
        st.session_state[f"{PURCHASE_BILL_DIALOG}_{key}"] = value


def _clear_dialog() -> None:
    for key in list(st.session_state.keys()):
        if key.startswith(PURCHASE_BILL_DIALOG):
            st.session_state.pop(key, None)


@st.dialog("Record Purchase Bill", width="large", on_dismiss=make_dismiss_handler(PURCHASE_BILL_DIALOG))
def purchase_bill_dialog(services: dict) -> None:
    if st.session_state.get(PURCHASE_BILL_DIALOG) != "new":
        return

    purchases = services["purchases"]
    accounting = services["accounting"]
    vendors = services["vendors"]
    inventory = services.get("inventory")
    vendor_services = services["vendor_services"]
    business = services["business"].get_profile()

    vendor_list = vendors.list_all_vendors()
    if not vendor_list:
        st.error("Add a vendor first.")
        if st.button("Close"):
            _clear_dialog()
            st.rerun()
        return

    vendor_opts = vendor_option_map(vendor_list)
    pre_vendor = st.session_state.get(f"{PURCHASE_BILL_DIALOG}_vendor_id")
    vendor_names = list(vendor_opts.keys())
    vendor_key = f"{PURCHASE_BILL_DIALOG}_vendor"
    ensure_selectbox_option(vendor_key, vendor_names)
    vendor_name = st.selectbox(
        "Vendor",
        vendor_names,
        index=vendor_select_index(vendor_opts, pre_vendor),
        key=vendor_key,
    )
    vendor_id = vendor_opts.get(vendor_name)
    if not vendor_id:
        st.warning("Select a vendor.")
        return
    vendor = vendors.get_vendor_detail(vendor_id)
    vendor_account = accounting.get_vendor_account(vendor_id)
    if not vendor_account:
        st.error("Vendor account not found.")
        return

    store_accounts = accounting.get_store_accounts()
    store_opts = {a.account_name: a.id for a in store_accounts}
    products = inventory.list_products(active_only=True) if inventory else []
    services_list = vendor_services.list_services(active_only=True)

    cols = st.columns(2)
    bill_number = cols[0].text_input(
        "Vendor bill number",
        value=st.session_state.get(f"{PURCHASE_BILL_DIALOG}_bill_number", ""),
        key=f"{PURCHASE_BILL_DIALOG}_bill_no",
    )
    bill_date = cols[1].date_input("Date", value=date.today(), key=f"{PURCHASE_BILL_DIALOG}_date")

    registered = vendor_is_registered(vendor)
    if registered:
        st.caption("Registered vendor — GST will be calculated from item HSN/SAC and rates (ex-GST).")
    else:
        st.caption("Unregistered/composition vendor — lines recorded without GST.")

    initial_lines = st.session_state.get(f"{PURCHASE_BILL_DIALOG}_lines")
    st.markdown("**Line items**")
    line_items, gst_errors = render_purchase_lines_editor(
        key_prefix=PURCHASE_BILL_DIALOG,
        products=products,
        services=services_list,
        initial_lines=initial_lines,
        vendor_id=vendor_id,
        purchases_service=purchases,
        inventory_service=inventory,
        allow_services=True,
        qty_field="qty",
        vendor_registered=registered,
        business=business,
        business_state_code=business.state_code if business else "",
        vendor_state_code=vendor.state_code if vendor else "",
        catalog_return_to=PURCHASE_BILL_DIALOG,
    )

    pay_total = round(
        sum(float(row.get("line_total") or 0) for row in line_items), 2
    )

    pay_cols = st.columns(2)
    amount_paid = pay_cols[0].number_input(
        "Amount paid",
        min_value=0.0,
        max_value=float(max(pay_total, 0)),
        value=float(st.session_state.get(f"{PURCHASE_BILL_DIALOG}_amount_paid", pay_total)),
        key=f"{PURCHASE_BILL_DIALOG}_paid",
    )
    paying_id = None
    if amount_paid > 0 and store_opts:
        paying_name = pay_cols[1].selectbox(
            "Paying account",
            list(store_opts.keys()),
            key=f"{PURCHASE_BILL_DIALOG}_pay_acct",
        )
        paying_id = store_opts[paying_name]

    has_product_lines = any(
        row.get("item_type") == CatalogItemType.PRODUCT.value and row.get("item_id")
        for row in line_items
    )
    apply_stock = False
    if has_product_lines:
        apply_stock = st.checkbox(
            "Receive stock (direct purchase, no GRN)",
            value=bool(st.session_state.get(f"{PURCHASE_BILL_DIALOG}_apply_stock", True)),
            key=f"{PURCHASE_BILL_DIALOG}_stock",
        )

    ref_order = st.session_state.get(f"{PURCHASE_BILL_DIALOG}_reference_order_id")
    ref_service = st.session_state.get(f"{PURCHASE_BILL_DIALOG}_reference_service_id")

    save_cols = st.columns(2)
    if save_cols[0].button("Save", type="primary", use_container_width=True):
        try:
            if gst_errors:
                raise ValueError(gst_errors[0])
            if not line_items:
                raise ValueError("Add at least one line with quantity, rate, and item")
            purchases.create_purchase_bill_from_lines(
                vendor_id=vendor_id,
                raw_lines=line_items,
                vendor_bill_number=bill_number,
                amount_paid=amount_paid,
                paying_account_id=paying_id,
                voucher_date=bill_date,
                reference_order_id=ref_order,
                reference_service_id=ref_service,
                apply_stock=apply_stock,
            )
            _clear_dialog()
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if save_cols[1].button("Cancel", use_container_width=True):
        _clear_dialog()
        st.rerun()


def open_purchase_bill_dialog_if_armed(services: dict) -> None:
    """Open catalog or purchase bill dialog — only one per run (no nesting)."""
    from vaybooks.bms.ui.components.inventory.catalog_item_dialog import (
        CATALOG_ITEM_DIALOG,
        catalog_item_dialog,
    )

    if st.session_state.get(CATALOG_ITEM_DIALOG):
        catalog_item_dialog(services)
    elif st.session_state.get(PURCHASE_BILL_DIALOG) == "new":
        purchase_bill_dialog(services)
