"""Record purchase bill dialog."""

from __future__ import annotations

from datetime import date

import streamlit as st

from vaybooks.bms.domain.shared.enums import CatalogItemType, VendorRegistrationType
from vaybooks.bms.ui.components.catalog_item_dialog import CATALOG_ITEM_DIALOG
from vaybooks.bms.ui.components.purchase_invoice_form import (
    ensure_selectbox_option,
    reset_dialog_state,
    vendor_option_map,
    vendor_select_index,
)
from vaybooks.bms.ui.components.purchase_line_ui import (
    default_purchase_line,
    item_option_map,
    line_items_total,
    line_tax_profile,
    preview_line_gst,
    vendor_is_registered,
)
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler

PURCHASE_BILL_DIALOG = "purchase_bill_dialog"
_LINES_KEY = f"{PURCHASE_BILL_DIALOG}_lines"


def arm_purchase_bill_dialog(**prefill) -> None:
    reset_dialog_state(PURCHASE_BILL_DIALOG)
    st.session_state[PURCHASE_BILL_DIALOG] = "new"
    for key, value in prefill.items():
        st.session_state[f"{PURCHASE_BILL_DIALOG}_{key}"] = value


def _clear_dialog() -> None:
    for key in list(st.session_state.keys()):
        if key.startswith(PURCHASE_BILL_DIALOG):
            st.session_state.pop(key, None)


def _item_lookup(services, item_type: str, item_id: str):
    if item_type == CatalogItemType.SERVICE.value:
        return services["vendor_services"].get_service(item_id)
    return services["inventory"].get_product(item_id)


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

    if _LINES_KEY not in st.session_state:
        pre_lines = st.session_state.get(f"{PURCHASE_BILL_DIALOG}_lines")
        st.session_state[_LINES_KEY] = pre_lines or [default_purchase_line()]

    cols = st.columns(2)
    bill_number = cols[0].text_input(
        "Vendor bill number",
        value=st.session_state.get(f"{PURCHASE_BILL_DIALOG}_bill_number", ""),
        key=f"{PURCHASE_BILL_DIALOG}_bill_no",
    )
    bill_date = cols[1].date_input("Date", value=date.today(), key=f"{PURCHASE_BILL_DIALOG}_date")

    show_gst = vendor_is_registered(vendor)
    if show_gst:
        st.caption("Registered vendor — GST will be calculated from item HSN/SAC and rates (ex-GST).")
    else:
        st.caption("Unregistered/composition vendor — lines recorded without GST.")

    st.markdown("**Line items**")
    line_items = list(st.session_state[_LINES_KEY])
    gst_previews = []
    remove_idx = None
    registered = vendor.registration_type == VendorRegistrationType.REGISTERED

    for i, row in enumerate(line_items):
        with st.container(border=True):
            type_col, item_col, add_col = st.columns([1, 3, 1])
            item_type = type_col.selectbox(
                "Type",
                [CatalogItemType.PRODUCT.value, CatalogItemType.SERVICE.value],
                index=0 if row.get("item_type") != CatalogItemType.SERVICE.value else 1,
                key=f"{PURCHASE_BILL_DIALOG}_type_{i}",
            )
            row["item_type"] = item_type

            if item_type == CatalogItemType.SERVICE.value:
                opts = item_option_map(services_list, lambda s: s.service_name)
            else:
                opts = item_option_map(products, lambda p: f"{p.sku} — {p.name}")

            item_labels = ["—"] + list(opts.keys())
            current_label = "—"
            if row.get("item_id") in opts.values():
                current_label = next(k for k, v in opts.items() if v == row.get("item_id"))
            picked = item_col.selectbox(
                "Item",
                item_labels,
                index=item_labels.index(current_label) if current_label in item_labels else 0,
                key=f"{PURCHASE_BILL_DIALOG}_item_{i}",
            )
            if add_col.button("+ Add", key=f"{PURCHASE_BILL_DIALOG}_add_item_{i}"):
                st.session_state[CATALOG_ITEM_DIALOG] = {
                    "mode": "product" if item_type == CatalogItemType.PRODUCT.value else "service",
                    "return_to": PURCHASE_BILL_DIALOG,
                    "line_index": i,
                }
                st.rerun()

            if picked != "—":
                row["item_id"] = opts[picked]
                item = _item_lookup(services, item_type, row["item_id"])
                row["item_name"] = (
                    item.name if item_type == CatalogItemType.PRODUCT.value else item.service_name
                )
                if item_type == CatalogItemType.PRODUCT.value:
                    row["product_id"] = row["item_id"]
                else:
                    row["product_id"] = None
                if not row.get("rate"):
                    latest = purchases.get_latest_purchase_rate(
                        CatalogItemType(item_type), row["item_id"], vendor_id
                    )
                    if latest:
                        row["rate"] = latest
            else:
                row["item_id"] = None
                row["item_name"] = ""
                row["product_id"] = None

            c_qty, c_rate = st.columns(2)
            row["qty"] = c_qty.number_input(
                "Qty", min_value=0.0, value=float(row.get("qty") or 1),
                key=f"{PURCHASE_BILL_DIALOG}_qty_{i}",
            )
            row["rate"] = c_rate.number_input(
                "Rate (ex-GST)", min_value=0.0, value=float(row.get("rate") or 0),
                key=f"{PURCHASE_BILL_DIALOG}_rate_{i}",
            )

            item = _item_lookup(services, item_type, row.get("item_id") or "")
            tax_profile = line_tax_profile(item)

            preview = preview_line_gst(
                row["qty"],
                row["rate"],
                tax_profile,
                vendor_registered=registered,
                business_state_code=business.state_code,
                vendor_state_code=vendor.state_code if vendor else "",
            )
            gst_previews.append(preview)
            if show_gst and preview["line_total"] > 0:
                gst_bits = []
                if preview["cgst_amount"]:
                    gst_bits.append(f"CGST ₹{preview['cgst_amount']:,.2f}")
                if preview["sgst_amount"]:
                    gst_bits.append(f"SGST ₹{preview['sgst_amount']:,.2f}")
                if preview["utgst_amount"]:
                    gst_bits.append(f"UTGST ₹{preview['utgst_amount']:,.2f}")
                if preview["igst_amount"]:
                    gst_bits.append(f"IGST ₹{preview['igst_amount']:,.2f}")
                st.caption(
                    f"Taxable ₹{preview['taxable_amount']:,.2f}"
                    + (f" · {' · '.join(gst_bits)}" if gst_bits else "")
                    + f" · Line total ₹{preview['line_total']:,.2f}"
                )
            elif preview["line_total"] > 0:
                st.caption(f"Line total ₹{preview['line_total']:,.2f}")

            if st.button("Remove line", key=f"{PURCHASE_BILL_DIALOG}_rm_{i}"):
                remove_idx = i
        line_items[i] = row

    if remove_idx is not None:
        line_items.pop(remove_idx)
        st.session_state[_LINES_KEY] = line_items or [default_purchase_line()]
        st.rerun()

    if st.button("+ Add line", key=f"{PURCHASE_BILL_DIALOG}_add"):
        line_items.append(default_purchase_line())
        st.session_state[_LINES_KEY] = line_items
        st.rerun()

    total = line_items_total(line_items, gst_previews)
    taxable_sub = round(sum(p.get("taxable_amount", 0) for p in gst_previews), 2)
    gst_sub = round(total - taxable_sub, 2) if show_gst else 0.0
    st.caption(
        f"Subtotal (taxable): ₹{taxable_sub:,.2f}"
        + (f" · GST: ₹{gst_sub:,.2f}" if show_gst else "")
        + f" · Bill total: ₹{total:,.2f}"
    )

    pay_cols = st.columns(2)
    amount_paid = pay_cols[0].number_input(
        "Amount paid",
        min_value=0.0,
        max_value=float(total),
        value=float(st.session_state.get(f"{PURCHASE_BILL_DIALOG}_amount_paid", total)),
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
    from vaybooks.bms.ui.components.catalog_item_dialog import (
        CATALOG_ITEM_DIALOG,
        catalog_item_dialog,
    )

    if st.session_state.get(CATALOG_ITEM_DIALOG):
        catalog_item_dialog(services)
    elif st.session_state.get(PURCHASE_BILL_DIALOG) == "new":
        purchase_bill_dialog(services)
