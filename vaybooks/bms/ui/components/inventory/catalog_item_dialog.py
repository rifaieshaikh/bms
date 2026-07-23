"""Add/edit catalog product or service with tax fields and price history."""

from __future__ import annotations

import re

import streamlit as st

from vaybooks.bms.domain.shared.enums import CatalogItemType
from vaybooks.bms.domain.shared.india import MATERIAL_PURCHASE_EXPENSE_NAME
from vaybooks.bms.domain.shared.item_tax import ItemTaxProfile
from vaybooks.bms.ui.components.inventory.product_form import clear_product_form_state, render_product_form
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler

CATALOG_ITEM_DIALOG = "catalog_item_dialog"


def arm_catalog_item_dialog(mode: str = "product", **context) -> None:
    st.session_state[CATALOG_ITEM_DIALOG] = {"mode": mode, **context}


def _clear_catalog_form_state() -> None:
    for key in list(st.session_state):
        if key.startswith("cat_product_") or key.startswith("cat_svc_") or key in {
            "cat_hsn",
            "cat_gst",
            "cat_mrp",
        }:
            st.session_state.pop(key, None)


def _product_prefill(text: str) -> tuple[str, str]:
    value = (text or "").strip()
    if "—" in value:
        sku, name = value.split("—", 1)
        return sku.strip(), name.strip()
    sku = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").upper()
    return sku, value


def _apply_to_bill_line(ctx: dict, saved_item, mode: str) -> None:
    draft_product_key = ctx.get("draft_product_key")
    if draft_product_key:
        label = (
            f"{saved_item.sku} — {saved_item.name}"
            if mode == "product"
            else saved_item.service_name
        )
        st.session_state[draft_product_key] = label
        st.session_state.pop(f"{ctx['return_to']}_products_cache", None)
        return

    editor_df_key = ctx.get("editor_df_key")
    if editor_df_key and editor_df_key in st.session_state:
        idx = int(ctx["line_index"])
        rows = list(st.session_state[editor_df_key])
        if 0 <= idx < len(rows):
            label = (
                f"{saved_item.sku} — {saved_item.name}"
                if mode == "product"
                else saved_item.service_name
            )
            rows[idx]["Item"] = label
            rows[idx]["Name"] = (
                saved_item.name if mode == "product" else saved_item.service_name
            )
            if "Type" in rows[idx]:
                rows[idx]["Type"] = (
                    CatalogItemType.PRODUCT.value
                    if mode == "product"
                    else CatalogItemType.SERVICE.value
                )
            st.session_state[editor_df_key] = rows
            editor_key = ctx.get("editor_key")
            if editor_key:
                st.session_state.pop(editor_key, None)
            # Parent dialog may cache list_products for the open session.
            st.session_state.pop(f"{ctx['return_to']}_products_cache", None)
        return

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
    st.session_state.pop(f"{ctx['return_to']}_products_cache", None)


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
        form_prefix = f"cat_product_{item_id or 'new'}"
        st.caption(f"Expense account: **{MATERIAL_PURCHASE_EXPENSE_NAME}** (auto)")
        if not existing and ctx.get("prefill_text"):
            sku, name = _product_prefill(str(ctx["prefill_text"]))
            st.session_state.setdefault(f"{form_prefix}_sku", sku)
            st.session_state.setdefault(f"{form_prefix}_name", name)

        payload = render_product_form(
            inventory=inventory,
            key_prefix=form_prefix,
            existing=existing,
            business=services["business"].get_profile(),
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
                        is_active=existing.is_active,
                        hsn_sac=payload["hsn_sac"],
                        selling_rate=payload["selling_rate"],
                        mrp=payload["mrp"],
                        gst_rate=payload["gst_rate"],
                        gst_required=payload["gst_required"],
                        specifications=payload["specifications"],
                        custom_fields=payload["custom_fields"],
                        pending_category_name=payload.get("pending_category_name"),
                        pending_unit_code=payload.get("pending_unit_code"),
                    )
                else:
                    saved = inventory.create_product(
                        payload["sku"],
                        payload["name"],
                        payload["category_ids"],
                        selling_rate=payload["selling_rate"],
                        mrp=payload["mrp"],
                        gst_rate=payload["gst_rate"],
                        unit_id=payload["unit_id"],
                        hsn_sac=payload["hsn_sac"],
                        gst_required=payload["gst_required"],
                        specifications=payload["specifications"],
                        custom_fields=payload["custom_fields"],
                        pending_category_name=payload.get("pending_category_name"),
                        pending_unit_code=payload.get("pending_unit_code"),
                    )
                inventory.set_product_cost_fields(
                    saved.id,
                    last_purchase_rate=float(payload.get("purchase_rate") or 0),
                )
                saved = inventory.get_product(saved.id) or saved
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
        if not existing and ctx.get("prefill_text"):
            st.session_state.setdefault(
                "cat_svc_name", str(ctx["prefill_text"]).strip()
            )
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
                    _clear_catalog_form_state()
                    st.session_state.pop(CATALOG_ITEM_DIALOG, None)
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    if save_cols[1].button("Close", key="cat_close"):
        _clear_catalog_form_state()
        st.session_state.pop(CATALOG_ITEM_DIALOG, None)
        st.rerun()

    show_id = item_id or (existing.id if existing else None)
    if show_id:
        hist_type = CatalogItemType.PRODUCT if mode == "product" else CatalogItemType.SERVICE
        history = purchases.list_purchase_price_history(hist_type, show_id)
        st.markdown("**Purchase price history**")
        st.caption("Ex-GST rates. Newest per vendor is Active.")
        if not history:
            st.caption("No purchase history yet.")
        else:
            for idx, row in enumerate(history[:10]):
                is_active = not any(
                    h.vendor_id == row.vendor_id for h in history[:idx]
                )
                status = "Active" if is_active else "Previous"
                st.caption(
                    f"{status} · {row.purchase_date} · Qty {row.qty:g} @ ₹{row.rate:,.2f} "
                    f"(total ₹{row.line_total:,.2f}) · Bill {row.vendor_bill_number or '—'}"
                )


def open_catalog_item_dialog_if_armed(services: dict) -> None:
    if st.session_state.get(CATALOG_ITEM_DIALOG):
        catalog_item_dialog(services)
