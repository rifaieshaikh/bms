"""Edit dialog for purchase bills (metadata + GST only; landed_cost_alloc pass-through)."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.domain.shared.enums import CatalogItemType
from vaybooks.bms.ui.components.purchases.purchase_line_ui import vendor_is_registered
from vaybooks.bms.ui.components.purchases.purchase_lines_entry_table import (
    entry_table_focus_chain,
    entry_table_focus_columns,
    render_purchase_lines_entry_table,
)
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler
from vaybooks.bms.ui.keyboard.focus.registry import get_strategy

PURCHASE_BILL_EDIT_DIALOG = "purchase_bill_edit_dialog"
BILL_EDIT_FOCUS_KEY = f"{PURCHASE_BILL_EDIT_DIALOG}_focus"


def arm_purchase_bill_edit_dialog(voucher_id: str) -> None:
    st.session_state[PURCHASE_BILL_EDIT_DIALOG] = voucher_id


def _clear() -> None:
    for key in list(st.session_state.keys()):
        if key == PURCHASE_BILL_EDIT_DIALOG or key.startswith(
            f"{PURCHASE_BILL_EDIT_DIALOG}_"
        ):
            st.session_state.pop(key, None)


@st.dialog(
    "Edit Purchase Bill",
    width="large",
    on_dismiss=make_dismiss_handler(PURCHASE_BILL_EDIT_DIALOG),
)
def _purchase_bill_edit_dialog(services: dict) -> None:
    voucher_id = st.session_state.get(PURCHASE_BILL_EDIT_DIALOG)
    if not voucher_id:
        return

    purchases = services["purchases"]
    accounting = services["accounting"]
    vendors = services["vendors"]
    inventory = services.get("inventory")
    business = services["business"].get_profile()

    row = purchases.get_purchase_bill(voucher_id)
    voucher = accounting.get_voucher(voucher_id)
    if not row or not voucher:
        st.error("Purchase bill not found")
        return

    vendor_account_id = row.get("vendor_account_id")
    vendor_account = (
        accounting.get_account(vendor_account_id) if vendor_account_id else None
    )
    vendor_id = getattr(vendor_account, "linked_vendor_id", None) if vendor_account else None
    vendor = vendors.get_vendor_detail(vendor_id) if vendor_id else None
    if not vendor_id or not vendor:
        st.error("Vendor not found for this bill")
        return

    products = inventory.list_products(active_only=True) if inventory else []
    registered = vendor_is_registered(vendor)

    st.caption(f"Vendor: {row.get('vendor_name') or vendor.vendor_name}")
    bill_no_key = f"{PURCHASE_BILL_EDIT_DIALOG}_bill_no"
    date_key = f"{PURCHASE_BILL_EDIT_DIALOG}_date"
    bill_number = st.text_input(
        "Vendor bill number",
        value=row.get("vendor_bill_number") or "",
        key=bill_no_key,
    )
    bill_date = st.date_input(
        "Date",
        value=row.get("bill_date"),
        key=date_key,
    )

    initial_lines = []
    skipped_services = 0
    for item in row.get("line_items") or []:
        item_type = str(item.get("item_type") or CatalogItemType.PRODUCT.value)
        if item_type != CatalogItemType.PRODUCT.value:
            skipped_services += 1
            continue
        item_id = str(item.get("item_id") or item.get("product_id") or "")
        initial_lines.append(
            {
                "item_type": CatalogItemType.PRODUCT.value,
                "item_id": item_id,
                "product_id": item.get("product_id") or item_id,
                "item_name": item.get("item_name") or item.get("product_name") or "",
                "qty": float(item.get("qty") or 0),
                "rate": float(item.get("rate") or 0),
                "landed_cost_alloc": float(item.get("landed_cost_alloc") or 0),
            }
        )

    st.markdown("**Line items**")
    st.caption("Editing updates bill lines and GST. Stock receive and landed cost are not re-applied.")
    if skipped_services:
        st.caption(
            f"{skipped_services} service line(s) from this bill are not editable here "
            "(product lines only)."
        )
    line_items, gst_errors = render_purchase_lines_entry_table(
        key_prefix=PURCHASE_BILL_EDIT_DIALOG,
        products=products,
        initial_lines=initial_lines,
        vendor_id=vendor_id,
        purchases_service=purchases,
        inventory_service=inventory,
        qty_field="qty",
        vendor_registered=registered,
        business=business,
        business_state_code=business.state_code if business else "",
        vendor_state_code=vendor.state_code if vendor else "",
        focus_restore_key=BILL_EDIT_FOCUS_KEY,
    )

    store_accounts = accounting.get_store_accounts()
    store_opts = {a.account_name: a.id for a in store_accounts}
    pay_total = round(
        sum(float(line.get("line_total") or 0) for line in line_items), 2
    )
    if pay_total <= 0:
        pay_total = float(row.get("total") or 0)

    paid_key = f"{PURCHASE_BILL_EDIT_DIALOG}_paid"
    pay_acct_key = f"{PURCHASE_BILL_EDIT_DIALOG}_pay_acct"
    save_key = f"{PURCHASE_BILL_EDIT_DIALOG}_save"

    amount_paid = st.number_input(
        "Amount paid",
        min_value=0.0,
        max_value=float(max(pay_total, 0)),
        value=float(row.get("paid") or 0),
        key=paid_key,
    )
    paying_id = None
    chain_tail: list[str] = [paid_key]
    if amount_paid > 0 and store_opts:
        paying_name = st.selectbox(
            "Paying account",
            list(store_opts.keys()),
            key=pay_acct_key,
        )
        paying_id = store_opts[paying_name]
        chain_tail.append(pay_acct_key)

    do_save = st.button("Update bill", type="primary", key=save_key)

    row_chain = entry_table_focus_chain(PURCHASE_BILL_EDIT_DIALOG)
    row_columns = entry_table_focus_columns(PURCHASE_BILL_EDIT_DIALOG)
    restore = st.session_state.pop(BILL_EDIT_FOCUS_KEY, None)
    get_strategy(PURCHASE_BILL_EDIT_DIALOG).inject(
        chain=[bill_no_key, date_key, *row_chain, *chain_tail, save_key],
        restore_key=restore,
        columns=row_columns,
        above_first=date_key,
        below_last=save_key,
        component_key=f"bill_edit_entry_{str(voucher_id)[:8]}_{len(row_chain)}",
    )

    if do_save:
        try:
            if gst_errors:
                raise ValueError(gst_errors[0])
            if not line_items:
                raise ValueError("Add at least one line with quantity, rate, and item")
            for line in line_items:
                line["item_type"] = CatalogItemType.PRODUCT.value
                if not line.get("product_id"):
                    line["product_id"] = line.get("item_id")
                for seeded in initial_lines:
                    if str(seeded.get("item_id") or "") == str(line.get("item_id") or ""):
                        line["landed_cost_alloc"] = seeded.get("landed_cost_alloc") or 0
                        break
            purchases.update_purchase_bill_from_lines(
                voucher_id=voucher_id,
                vendor_id=vendor_id,
                raw_lines=line_items,
                vendor_bill_number=bill_number,
                amount_paid=amount_paid,
                paying_account_id=paying_id,
                voucher_date=bill_date,
            )
            _clear()
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def open_purchase_bill_edit_dialog_if_armed(services: dict) -> None:
    if st.session_state.get(PURCHASE_BILL_EDIT_DIALOG):
        _purchase_bill_edit_dialog(services)
