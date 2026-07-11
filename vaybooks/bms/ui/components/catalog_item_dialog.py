"""Add/edit catalog product or service with tax fields and price history."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.domain.shared.enums import CatalogItemType
from vaybooks.bms.domain.shared.india import MATERIAL_PURCHASE_EXPENSE_NAME
from vaybooks.bms.domain.shared.item_tax import ItemTaxProfile
from vaybooks.bms.ui.components.product_form import clear_product_form_state, render_product_form
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler

CATALOG_ITEM_DIALOG = "catalog_item_dialog"


def arm_catalog_item_dialog(mode: str = "product", **context) -> None:
    st.session_state[CATALOG_ITEM_DIALOG] = {"mode": mode, **context}


def _apply_to_bill_line(ctx: dict, saved_item, mode: str) -> None:
    lines_key = f"{ctx['return_to']}_lines"
    if lines_key not in st.session_state:
        return
    idx = int(ctx["line_index"])
    lines = list(st.session_state[lines_key])
    if 0 <= idx < len(lines):
        lines[idx]["item_id"] = saved_item.id
        lines[idx]["item_type"] = (
            CatalogItemType.PRODUCT.value
            if mode == "product"
            else CatalogItemType.SERVICE.value
        )
        lines[idx]["item_name"] = (
            saved_item.name if mode == "product" else saved_item.service_name
        )
        if mode == "product":
            lines[idx]["product_id"] = saved_item.id
        st.session_state[lines_key] = lines


@st.dialog("Catalog Item", width="large", on_dismiss=make_dismiss_handler(CATALOG_ITEM_DIALOG))
def catalog_item_dialog(services: dict) -> None:
    ctx = st.session_state.get(CATALOG_ITEM_DIALOG)
    if not ctx:
        return

    mode = ctx.get("mode", "product")
    purchases = services["purchases"]
    inventory = services["inventory"]
    vendor_services = services["vendor_services"]
    accounting = services["accounting"]

    st.subheader("Product" if mode == "product" else "Service")

    item_id = ctx.get("item_id")
    existing = None
    if mode == "product" and item_id:
        existing = inventory.get_product(item_id)
    elif mode == "service" and item_id:
        existing = vendor_services.get_service(item_id)

    save_cols = st.columns(2)

    if mode == "product":
        categories = inventory.list_categories(active_only=True)
        if not categories:
            st.error("Create a category first.")
            return

        form_prefix = f"cat_product_{item_id or 'new'}"
        st.caption(f"Expense account: **{MATERIAL_PURCHASE_EXPENSE_NAME}** (auto)")

        payload = render_product_form(
            inventory=inventory,
            key_prefix=form_prefix,
            categories=categories,
            existing=existing,
            submit_label="Save Product",
        )
        if payload:
            try:
                if existing:
                    saved = inventory.update_product(
                        existing.id,
                        payload["sku"],
                        payload["name"],
                        payload["category_ids"],
                        payload["unit_id"],
                        payload["selling_rate"],
                        is_active=existing.is_active,
                        hsn_sac=payload["hsn_sac"],
                        gst_rates=payload["gst_rates"],
                        mrp_entries=payload["mrp_entries"],
                        specifications=payload["specifications"],
                        custom_fields=payload["custom_fields"],
                    )
                else:
                    saved = inventory.create_product(
                        payload["sku"],
                        payload["name"],
                        payload["category_ids"],
                        selling_rate=payload["selling_rate"],
                        unit_id=payload["unit_id"],
                        hsn_sac=payload["hsn_sac"],
                        gst_rates=payload["gst_rates"],
                        mrp_entries=payload["mrp_entries"],
                        specifications=payload["specifications"],
                        custom_fields=payload["custom_fields"],
                    )
                st.success(f"Saved {saved.name}")
                clear_product_form_state(form_prefix)
                if ctx.get("return_to") and ctx.get("line_index") is not None:
                    _apply_to_bill_line(ctx, saved, mode)
                    st.session_state.pop(CATALOG_ITEM_DIALOG, None)
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    else:
        tax = existing.tax_profile if existing else ItemTaxProfile()
        hsn_sac = st.text_input("SAC", value=tax.hsn_sac, key="cat_hsn")
        gst_rate = st.number_input(
            "GST rate (%)", min_value=0.0, max_value=100.0, value=float(tax.gst_rate),
            key="cat_gst",
        )
        mrp = st.number_input(
            "MRP (₹)", min_value=0.0, value=float(tax.mrp), key="cat_mrp"
        )
        profile = ItemTaxProfile(hsn_sac=hsn_sac.strip(), gst_rate=gst_rate, mrp=mrp)
        profile.sync_rates_from_gst()

        expense_accounts = accounting.get_expense_accounts()
        exp_opts = {a.account_name: a.id for a in expense_accounts}
        svc_name = st.text_input(
            "Service name",
            value=existing.service_name if existing else "",
            key="cat_svc_name",
        )
        exp_names = list(exp_opts.keys())
        exp_default = 0
        if existing:
            for i, aid in enumerate(exp_opts.values()):
                if aid == existing.expense_account_id:
                    exp_default = i
                    break
        expense_pick = st.selectbox(
            "Expense account", exp_names, index=exp_default, key="cat_svc_exp"
        )

        if save_cols[0].button("Save Service", type="primary", key="cat_save_service"):
            try:
                if existing:
                    saved = vendor_services.update_service(
                        existing.id, svc_name, exp_opts[expense_pick],
                        is_active=existing.is_active,
                    )
                    saved = vendor_services.set_service_tax_profile(saved.id, profile)
                else:
                    saved = vendor_services.create_service(
                        svc_name, exp_opts[expense_pick], tax_profile=profile,
                    )
                st.success(f"Saved {saved.service_name}")
                if ctx.get("return_to") and ctx.get("line_index") is not None:
                    _apply_to_bill_line(ctx, saved, mode)
                    st.session_state.pop(CATALOG_ITEM_DIALOG, None)
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    if save_cols[1].button("Close", key="cat_close"):
        st.session_state.pop(CATALOG_ITEM_DIALOG, None)
        st.rerun()

    show_id = item_id or (existing.id if existing else None)
    if show_id:
        hist_type = CatalogItemType.PRODUCT if mode == "product" else CatalogItemType.SERVICE
        history = purchases.list_purchase_price_history(hist_type, show_id)
        st.markdown("**Purchase price history**")
        if not history:
            st.caption("No purchase history yet.")
        else:
            for row in history[:10]:
                st.caption(
                    f"{row.purchase_date} · Qty {row.qty:g} @ ₹{row.rate:,.2f} "
                    f"(total ₹{row.line_total:,.2f}) · Bill {row.vendor_bill_number or '—'}"
                )


def open_catalog_item_dialog_if_armed(services: dict) -> None:
    if st.session_state.get(CATALOG_ITEM_DIALOG):
        catalog_item_dialog(services)
