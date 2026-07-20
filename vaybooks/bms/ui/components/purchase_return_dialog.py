"""Purchase return dialog with optional source-bill prefill."""

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
from vaybooks.bms.ui.components.purchase_lines_editor import render_purchase_lines_editor
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler
from vaybooks.bms.ui.purchase_display import product_lines_from_bill_row

RETURN_DIALOG = "purchase_return_dialog"


def arm_return_dialog(source_bill_id: str | None = None) -> None:
    reset_dialog_state(RETURN_DIALOG)
    st.session_state[RETURN_DIALOG] = "new"
    if source_bill_id:
        st.session_state[f"{RETURN_DIALOG}_bill_id"] = source_bill_id


def _clear() -> None:
    for key in list(st.session_state.keys()):
        if key.startswith(RETURN_DIALOG):
            st.session_state.pop(key, None)


def _prefill_from_source_bill(services: dict, source_bill_id: str) -> tuple[str | None, list[dict], int]:
    """Return (vendor_id, product lines, skipped_service_count)."""
    purchases = services["purchases"]
    accounting = services["accounting"]
    row = purchases.get_purchase_bill(source_bill_id)
    voucher = accounting.get_voucher(source_bill_id)
    if not row or not voucher:
        return None, [], 0

    vendor_account_id = row.get("vendor_account_id")
    vendor_id = None
    if vendor_account_id:
        account = accounting.get_account(vendor_account_id)
        if account and getattr(account, "linked_vendor_id", None):
            vendor_id = account.linked_vendor_id

    product_lines, skipped = product_lines_from_bill_row(
        row, voucher.description or ""
    )
    return vendor_id, product_lines, skipped


@st.dialog("Record Purchase Return", width="large", on_dismiss=make_dismiss_handler(RETURN_DIALOG))
def purchase_return_dialog(services: dict) -> None:
    if st.session_state.get(RETURN_DIALOG) != "new":
        return

    purchases = services["purchases"]
    accounting = services["accounting"]
    vendors = services["vendors"]
    inventory = services.get("inventory")
    business = services["business"].get_profile()

    source_bill_id = st.session_state.get(f"{RETURN_DIALOG}_bill_id")
    prefill_vendor_id = None
    initial_lines = None
    skipped_services = 0
    if source_bill_id and f"{RETURN_DIALOG}_prefilled" not in st.session_state:
        prefill_vendor_id, initial_lines, skipped_services = _prefill_from_source_bill(
            services, source_bill_id
        )
        st.session_state[f"{RETURN_DIALOG}_prefilled"] = True
        st.session_state[f"{RETURN_DIALOG}_skipped_services"] = skipped_services
        if prefill_vendor_id:
            st.session_state[f"{RETURN_DIALOG}_pre_vendor_id"] = prefill_vendor_id
        if initial_lines:
            st.session_state[f"{RETURN_DIALOG}_seed_lines"] = initial_lines

    skipped_services = int(st.session_state.get(f"{RETURN_DIALOG}_skipped_services") or 0)
    pre_vendor = st.session_state.get(f"{RETURN_DIALOG}_pre_vendor_id")
    seed_lines = st.session_state.get(f"{RETURN_DIALOG}_seed_lines")

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
        index=vendor_select_index(vendor_opts, pre_vendor),
        key=vendor_key,
    )
    vendor_id = vendor_opts.get(vendor_name)
    if not vendor_id:
        st.warning("Select a vendor.")
        return
    vendor = vendors.get_vendor_detail(vendor_id)

    products = inventory.list_products(active_only=True) if inventory else []

    return_date = st.date_input("Return date", value=date.today(), key=f"{RETURN_DIALOG}_date")
    if source_bill_id:
        st.caption(f"Linked to purchase bill `{source_bill_id[:8]}…`")
    if skipped_services:
        st.caption(
            f"{skipped_services} service line(s) from the bill are not returnable here."
        )

    st.markdown("**Line items**")
    line_items, gst_errors = render_purchase_lines_editor(
        key_prefix=RETURN_DIALOG,
        products=products,
        services=[],
        initial_lines=seed_lines,
        vendor_id=vendor_id,
        purchases_service=purchases,
        inventory_service=inventory,
        allow_services=False,
        qty_field="qty",
        vendor_registered=False,
        business=business,
        business_state_code=business.state_code if business else "",
        vendor_state_code=vendor.state_code if vendor else "",
    )

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
            if gst_errors:
                raise ValueError(gst_errors[0])
            if not line_items:
                raise ValueError("Add at least one product line")
            for row in line_items:
                row["item_type"] = CatalogItemType.PRODUCT.value
                if not row.get("product_id"):
                    row["product_id"] = row.get("item_id")
            resolved = purchases.resolve_purchase_lines(line_items, vendor_id)
            lines = [
                {
                    "product_id": row.product_id or row.item_id,
                    "product_name": row.item_name,
                    "qty": row.qty,
                    "rate": row.rate,
                    "expense_account_id": row.expense_account_id,
                }
                for row in resolved
                if row.qty > 0 and row.item_type == CatalogItemType.PRODUCT
            ]
            if not lines:
                raise ValueError("Add at least one product line")
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
