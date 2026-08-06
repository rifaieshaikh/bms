"""Create-only store sales invoice dialog (shared by Sales page)."""

from __future__ import annotations

from datetime import date

import streamlit as st

from vaybooks.bms.domain.sales.sales_line_resolver import business_is_registered
from vaybooks.bms.domain.shared.enums import PartyRegistrationType
from vaybooks.bms.ui.components.common.customer_identity_selector import (
    render_customer_identity_selector,
    resolve_customer_identity,
)
from vaybooks.bms.ui.components.sales.sales_invoice_form import (
    line_items_discount,
    line_items_gross,
)
from vaybooks.bms.ui.components.sales.sales_line_ui import (
    line_items_total,
    line_tax_profile,
    preview_sales_line_gst,
    sales_tax_column_labels,
    sales_tax_display_mode,
    tax_summary_from_previews,
)
from vaybooks.bms.ui.components.common.dialog_state import reset_dialog_state
from vaybooks.bms.ui.auth.session import require_specific_location
from vaybooks.bms.ui.components.sales.discount_controls import (
    eligible_invoice_discount_base,
    render_invoice_level_discount,
)
from vaybooks.bms.ui.components.sales.apply_discount_rules import (
    render_apply_discount_rules_button,
)
from vaybooks.bms.domain.sales.discount_entities import APPLY_SALES_INVOICE
from vaybooks.bms.ui.components.sales.invoice_number_field import (
    render_store_invoice_number_field,
)
from vaybooks.bms.ui.components.sales.sales_lines_entry_table import (
    entry_table_focus_chain,
    entry_table_focus_columns,
    entry_table_grid_roles,
    render_sales_lines_entry_table,
)
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler, register_armed_dialog
from vaybooks.bms.ui.keyboard.dialog_actions import consume_submit, open_dialog
from vaybooks.bms.ui.keyboard.focus.registry import get_strategy
from vaybooks.bms.ui.keyboard.wired import mark_wired

SALES_RECORD_DIALOG = "sales_record_dialog"
SALES_INVOICE_FOCUS_STRATEGY = "sales_invoice_dialog"
SALES_RECORD_PRESELECT = "sales_record_dialog_preselect_customer_id"
SALES_RECORD_SUBMIT_KEY = "sales_record_dialog_submit"
SALES_RECORD_FOCUS_KEY = f"{SALES_RECORD_DIALOG}_focus"


def _index_of(options: dict, target_id, default: int = 0) -> int:
    ids = list(options.values())
    return ids.index(target_id) if target_id in ids else default


def arm_sales_record_dialog(customer_id: str | None = None) -> None:
    reset_dialog_state(SALES_RECORD_DIALOG)
    open_dialog(
        SALES_RECORD_DIALOG,
        submit_key=SALES_RECORD_SUBMIT_KEY,
        value="new",
        clear_others=True,
    )
    st.session_state[SALES_RECORD_FOCUS_KEY] = f"{SALES_RECORD_DIALOG}_customer_name"
    if customer_id:
        st.session_state[SALES_RECORD_PRESELECT] = customer_id
    else:
        st.session_state.pop(SALES_RECORD_PRESELECT, None)
    mark_wired("dialog.save")


def _clear_dialog_session() -> None:
    for key in list(st.session_state.keys()):
        if key.startswith(SALES_RECORD_DIALOG):
            st.session_state.pop(key, None)
    st.session_state.pop(SALES_RECORD_DIALOG, None)
    st.session_state.pop(SALES_RECORD_PRESELECT, None)
    st.session_state.pop(SALES_RECORD_SUBMIT_KEY, None)


@st.dialog(
    "Record Sale",
    width="large",
    on_dismiss=make_dismiss_handler(SALES_RECORD_DIALOG),
)
def sales_record_dialog(services: dict) -> None:
    if st.session_state.get(SALES_RECORD_DIALOG) != "new":
        return

    register_armed_dialog(SALES_RECORD_DIALOG)
    mark_wired("dialog.save")

    accounting_service = services["accounting"]
    customer_service = services["customers"]
    inventory_service = services.get("inventory")
    business_service = services.get("business")
    sales_account = accounting_service.get_sales_account()
    store_accounts = accounting_service.get_store_accounts()
    discount_account = accounting_service.get_discount_account()

    business = business_service.get_profile() if business_service else None
    business_registered = business_is_registered(business)
    business_state = business.state_code if business else ""
    show_gst = business_registered

    if not sales_account:
        st.error('No "Sales" revenue account found.')
        if st.button("Close"):
            _clear_dialog_session()
            st.rerun()
        return
    if not store_accounts:
        st.error("Need at least one cash/bank store account.")
        if st.button("Close"):
            _clear_dialog_session()
            st.rerun()
        return

    customer_selection = render_customer_identity_selector(
        customer_service,
        key_prefix=SALES_RECORD_DIALOG,
        initial_customer=(
            customer_service.get_customer_detail(
                st.session_state.get(SALES_RECORD_PRESELECT)
            )
            if st.session_state.get(SALES_RECORD_PRESELECT)
            else None
        ),
        services=services,
    )
    matched_customer = customer_selection.customer
    customer_state = matched_customer.state_code if matched_customer else ""
    customer_registered = bool(
        matched_customer
        and (
            matched_customer.registration_type == PartyRegistrationType.REGISTERED
            or (matched_customer.gstin or "").strip()
        )
    )
    if not customer_registered and not customer_state:
        customer_state = business_state

    store_opts = {a.account_name: a.id for a in store_accounts}
    store_names = list(store_opts.keys())
    default_store = store_accounts[0].id

    inv_cols = st.columns(2)
    date_key = f"{SALES_RECORD_DIALOG}_date"
    preview_date = st.session_state.get(date_key) or date.today()
    with inv_cols[0]:
        store_number = render_store_invoice_number_field(
            services.get("sales"),
            key=f"{SALES_RECORD_DIALOG}_store_no",
            voucher_date=preview_date if isinstance(preview_date, date) else date.today(),
        )
    with inv_cols[1]:
        inv_date = st.date_input(
            "Date",
            value=date.today(),
            key=date_key,
        )
    products = inventory_service.list_products(active_only=True) if inventory_service else []
    if not products:
        st.error("Add inventory products first.")
        return

    editor_lines, gst_errors = render_sales_lines_entry_table(
        key_prefix=SALES_RECORD_DIALOG,
        products=products,
        initial_lines=None,
        customer_id=matched_customer.id if matched_customer else None,
        use_customer_pricing=True,
        show_discount=True,
        sales_service=services.get("sales"),
        inventory_service=inventory_service,
        business_registered=business_registered,
        business=business,
        business_state_code=business_state,
        customer_state_code=customer_state or "",
        qty_field="qty",
        focus_restore_key=SALES_RECORD_FOCUS_KEY,
    )

    if matched_customer:
        render_apply_discount_rules_button(
            key_prefix=SALES_RECORD_DIALOG,
            services=services,
            customer=matched_customer,
            apply_to=APPLY_SALES_INVOICE,
            on_date=inv_date,
            qty_field="qty",
        )

    line_items = [
        {
            "description": row.get("product_name") or "",
            "qty": float(row.get("qty") or 0),
            "rate": float(row.get("rate") or 0),
            "discount": float(row.get("discount") or 0),
            "discount_mode": row.get("discount_mode") or "flat",
            "discount_input": float(
                row.get("discount_input")
                if row.get("discount_input") is not None
                else row.get("discount")
                or 0
            ),
            "product_id": row.get("product_id"),
        }
        for row in editor_lines
    ]

    gst_previews: list[dict] = []
    for row in line_items:
        product = (
            inventory_service.get_product(row["product_id"])
            if inventory_service and row.get("product_id")
            else None
        )
        gst_previews.append(
            preview_sales_line_gst(
                float(row["qty"] or 0),
                float(row["rate"] or 0),
                float(row["discount"] or 0),
                line_tax_profile(product),
                business_registered=business_registered,
                business=business,
                business_state_code=business_state,
                customer_state_code=customer_state or "",
            )
        )

    gross = line_items_gross(line_items)
    line_discount_total = line_items_discount(line_items)
    taxable_sub = round(sum(p.get("taxable_amount", 0) for p in gst_previews), 2)
    tax_summary = tax_summary_from_previews(gst_previews) if gst_previews else {}
    grand_before_inv_disc = tax_summary.get(
        "grand_total", line_items_total(line_items, gst_previews)
    )

    inv_disc_key = f"{SALES_RECORD_DIALOG}_inv_disc"
    received_key = f"{SALES_RECORD_DIALOG}_received"
    store_key = f"{SALES_RECORD_DIALOG}_store"
    save_key = f"{SALES_RECORD_DIALOG}_save"
    cancel_key = f"{SALES_RECORD_DIALOG}_cancel"
    date_key = f"{SALES_RECORD_DIALOG}_date"
    customer_name_key = f"{SALES_RECORD_DIALOG}_customer_name"

    inv_disc_base = eligible_invoice_discount_base(line_items)
    invoice_discount = render_invoice_level_discount(
        key_prefix=inv_disc_key,
        base_amount=inv_disc_base,
    )
    total_discount = round(line_discount_total + invoice_discount, 2)

    if invoice_discount > 0 and show_gst and inv_disc_base > 0:
        # Approximate GST net: shrink eligible portion of taxable, keep line-discounted lines.
        factor = round((inv_disc_base - invoice_discount) / inv_disc_base, 6)
        eligible_taxable = round(
            sum(
                float(p.get("taxable_amount") or 0)
                for row, p in zip(line_items, gst_previews)
                if float(row.get("discount") or 0) <= 0.01
            ),
            2,
        ) if gst_previews and len(gst_previews) == len(line_items) else inv_disc_base
        other_taxable = round(max(taxable_sub - eligible_taxable, 0.0), 2)
        adjusted_eligible = round(eligible_taxable * factor, 2)
        adjusted_taxable = round(other_taxable + adjusted_eligible, 2)
        if tax_summary and taxable_sub > 0:
            tax_factor = round(adjusted_taxable / taxable_sub, 6) if taxable_sub else 1.0
            adjusted_tax = round(tax_summary.get("total_tax", 0) * tax_factor, 2)
            net_due = round(adjusted_taxable + adjusted_tax, 2)
        else:
            net_due = round(max(grand_before_inv_disc - invoice_discount, 0.0), 2)
    elif invoice_discount > 0:
        net_due = round(max(grand_before_inv_disc - invoice_discount, 0.0), 2)
    else:
        net_due = round(max(grand_before_inv_disc - invoice_discount, 0.0), 2)

    credit_available = 0.0
    advance_available = 0.0
    if matched_customer:
        cust_acct = accounting_service.get_customer_account(matched_customer.id)
        if cust_acct:
            credit_available = accounting_service.customer_credit_balance(cust_acct.id)
            advance_available = accounting_service.get_customer_unapplied_advance(
                cust_acct.id, general_only=True
            )

    credit_key = f"{SALES_RECORD_DIALOG}_credit_applied"
    default_credit = round(min(credit_available, net_due), 2) if credit_available > 0 else 0.0
    credit_applied = 0.0
    if credit_available > 0:
        credit_applied = st.number_input(
            "Apply customer credit",
            min_value=0.0,
            max_value=float(min(credit_available, net_due)) if net_due > 0 else 0.0,
            value=float(default_credit),
            key=credit_key,
            help=f"Available credit ₹{credit_available:,.2f}",
        )
        st.caption(
            f"Available credit: ₹{credit_available:,.2f} · "
            f"Collect cash for remainder after credit."
        )

    after_credit = round(max(net_due - float(credit_applied or 0), 0.0), 2)
    advance_key = f"{SALES_RECORD_DIALOG}_advance_applied"
    default_advance = (
        round(min(advance_available, after_credit), 2) if advance_available > 0 else 0.0
    )
    advance_applied = 0.0
    if advance_available > 0:
        advance_applied = st.number_input(
            "Apply customer advance",
            min_value=0.0,
            max_value=float(min(advance_available, after_credit))
            if after_credit > 0
            else 0.0,
            value=float(default_advance),
            key=advance_key,
            help=f"Available advance ₹{advance_available:,.2f} (general, not order-linked)",
        )
        st.caption(
            f"Available advance: ₹{advance_available:,.2f} · "
            f"Settles from Advance From Customers."
        )

    cash_due = round(
        max(net_due - float(credit_applied or 0) - float(advance_applied or 0), 0.0),
        2,
    )
    if received_key not in st.session_state:
        st.session_state[received_key] = float(cash_due)

    pay_cols = st.columns(2)
    with pay_cols[0]:
        received = st.number_input(
            "Amount received now",
            min_value=0.0,
            key=received_key,
            help="You can receive more than due; excess stays as customer credit.",
        )
    with pay_cols[1]:
        store_name = st.selectbox(
            "Cash / Bank account",
            store_names,
            index=_index_of(store_opts, default_store),
            key=store_key,
        )
    overpay = round(max(float(received or 0) - cash_due, 0.0), 2)
    balance = round(cash_due - float(received or 0), 2)
    if overpay > 0:
        st.caption(
            f"Overpay ₹{overpay:,.2f} will be kept as customer credit "
            f"(invoice settles ₹{cash_due:,.2f})."
        )
    elif balance > 0.01:
        st.caption(f"Balance due after this payment: ₹{balance:,.2f}")

    # --- Commission parties (agents + sales reps) ---
    from vaybooks.bms.ui.components.sales.commission_profile_editor import (
        render_commission_party_multiselect,
    )

    agent_service = services.get("commission_agents")
    worker_service = services.get("workers")
    agents = agent_service.list_all_agents() if agent_service else []
    sales_reps = (
        worker_service.list_commission_enabled_workers()
        if worker_service
        else []
    )
    commission_tags = render_commission_party_multiselect(
        f"{SALES_RECORD_DIALOG}_tags",
        agents=agents,
        sales_reps=sales_reps,
    )
    if commission_tags.get("commission_agent_ids") or commission_tags.get(
        "sales_rep_ids"
    ):
        preview_bits = []
        if commission_tags.get("commission_agent_ids"):
            preview_bits.append(
                f"{len(commission_tags['commission_agent_ids'])} agent(s)"
            )
        if commission_tags.get("sales_rep_ids"):
            preview_bits.append(
                f"{len(commission_tags['sales_rep_ids'])} sales rep(s)"
            )
        st.caption(
            "Commission rules will accrue for: " + ", ".join(preview_bits)
        )

    with st.container(border=True):
        st.markdown("**Summary**")
        if show_gst:
            tax_mode = sales_tax_display_mode(
                business_registered=True,
                business_state_code=business_state,
                customer_state_code=customer_state or "",
            )
            tax_labels = sales_tax_column_labels(tax_mode)
            m = st.columns(3 + len(tax_labels))
            m[0].metric("Subtotal (taxable)", f"₹{taxable_sub:,.0f}")
            key_by_label = {
                "CGST": "cgst",
                "SGST": "sgst",
                "UTGST": "utgst",
                "IGST": "igst",
            }
            for i, label in enumerate(tax_labels):
                m[1 + i].metric(
                    label, f"₹{tax_summary.get(key_by_label[label], 0):,.0f}"
                )
            m[-2].metric("Grand total", f"₹{grand_before_inv_disc:,.0f}")
            m[-1].metric("Net due", f"₹{net_due:,.0f}")
            if total_discount > 0:
                st.caption(f"Discount (line + invoice): ₹{total_discount:,.0f}")
        else:
            m = st.columns(4)
            m[0].metric("Subtotal", f"₹{gross:,.0f}")
            m[1].metric("Total discount", f"₹{total_discount:,.0f}")
            m[2].metric("Net due", f"₹{net_due:,.0f}")
            m[3].metric("Customer balance", f"₹{balance:,.0f}")

    if total_discount > 0 and not discount_account and not show_gst:
        st.warning('No "Discount Allowed" account found. Create one to post discounts.')

    st.caption(f"Revenue credited to: **{sales_account.account_name}**")

    cols = st.columns(2)
    do_save = cols[0].button(
        "Save", type="primary", width="stretch", key=save_key
    ) or consume_submit(SALES_RECORD_SUBMIT_KEY)
    if cols[1].button("Cancel", width="stretch", key=cancel_key):
        _clear_dialog_session()
        st.rerun()

    row_chain = entry_table_focus_chain(SALES_RECORD_DIALOG)
    row_columns = entry_table_focus_columns(SALES_RECORD_DIALOG)
    grid_roles = entry_table_grid_roles(SALES_RECORD_DIALOG)
    restore = st.session_state.pop(SALES_RECORD_FOCUS_KEY, None)
    inv_disc_mode = st.session_state.get(f"{inv_disc_key}_mode", "₹")
    inv_disc_focus = (
        f"{inv_disc_key}_pct" if inv_disc_mode == "%" else f"{inv_disc_key}_flat"
    )
    get_strategy(SALES_INVOICE_FOCUS_STRATEGY).inject(
        chain=[
            customer_name_key,
            date_key,
            *row_chain,
            f"{inv_disc_key}_mode",
            inv_disc_focus,
            received_key,
            store_key,
            save_key,
            cancel_key,
        ],
        restore_key=restore,
        columns=row_columns,
        above_first=date_key,
        below_last=save_key,
        grid_roles=grid_roles,
        component_key=f"sales_inv_entry_{len(row_chain)}",
    )

    if do_save:
        try:
            if gst_errors:
                raise ValueError(gst_errors[0])
            if not line_items:
                raise ValueError("Add at least one product line")
            location_id = require_specific_location(services)
            for item in line_items:
                item["location_id"] = location_id
            if net_due <= 0:
                raise ValueError("Invoice net amount must be positive")
            if received < 0:
                raise ValueError("Amount received cannot be negative")
            if total_discount > 0 and not show_gst and not discount_account:
                raise ValueError('A "Discount Allowed" account is required for discounts')
            customer = resolve_customer_identity(
                customer_service,
                customer_selection,
                location_ids=[location_id],
            )
            customer_account = accounting_service.get_customer_account(customer.id)
            if not customer_account:
                raise ValueError("No ledger account for this customer")
            sales_service = services.get("sales")
            if sales_service:
                sales_service.create_direct_sale(
                    customer_account.id,
                    store_opts[store_name],
                    gross,
                    total_discount,
                    received,
                    store_number,
                    line_items,
                    voucher_date=inv_date,
                    invoice_discount=invoice_discount,
                    credit_applied=float(credit_applied or 0),
                    advance_applied=float(advance_applied or 0),
                    commission_tags=commission_tags,
                )
            else:
                from vaybooks.bms.ui.components.sales.sales_invoice_form import serialize_line_items

                note = serialize_line_items(line_items, invoice_discount)
                from vaybooks.bms.ui.components.common.location_fields import (
                    require_location_name,
                )

                location_id, location_name = require_location_name(services)
                voucher = accounting_service.create_cash_sales_invoice(
                    customer_account.id,
                    store_opts[store_name],
                    gross,
                    total_discount,
                    received,
                    store_number,
                    line_items_note=note,
                    voucher_date=inv_date,
                    credit_applied=float(credit_applied or 0),
                    advance_applied=float(advance_applied or 0),
                    location_id=location_id,
                    location_name=location_name,
                )
                if inventory_service:
                    inventory_service.apply_sales_movements(voucher.id, line_items)
            _clear_dialog_session()
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def open_sales_record_dialog_if_armed(services: dict) -> None:
    if st.session_state.get(SALES_RECORD_DIALOG):
        sales_record_dialog(services)
