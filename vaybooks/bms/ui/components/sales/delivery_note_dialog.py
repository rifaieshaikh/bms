"""Create Delivery Note — slim flow: source, qty grid, partner select, charge/paid."""

from __future__ import annotations

from datetime import date

import streamlit as st

from vaybooks.bms.domain.shared.enums import (
    DeliveryChargePaymentStatus,
    VoucherType,
)
from vaybooks.bms.ui.auth.session import require_specific_location
from vaybooks.bms.ui.components.common.dialog_state import (
    ensure_selectbox_option,
    reset_dialog_state,
)
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler, register_armed_dialog
from vaybooks.bms.ui.keyboard.dialog_actions import consume_submit, open_dialog
from vaybooks.bms.ui.keyboard.focus.registry import get_strategy
from vaybooks.bms.ui.keyboard.wired import mark_wired

DN_DIALOG = "delivery_note_dialog"
DN_SUBMIT_KEY = "delivery_note_dialog_submit"
DN_FOCUS_KEY = f"{DN_DIALOG}_focus"


def arm_dn_dialog(
    so_id: str | None = None,
    invoice_id: str | None = None,
) -> None:
    reset_dialog_state(DN_DIALOG)
    open_dialog(DN_DIALOG, submit_key=DN_SUBMIT_KEY, value="new", clear_others=True)
    st.session_state[DN_FOCUS_KEY] = f"{DN_DIALOG}_date"
    if so_id:
        st.session_state[f"{DN_DIALOG}_so_id"] = so_id
        st.session_state[f"{DN_DIALOG}_mode"] = "Sales Order"
    if invoice_id:
        st.session_state[f"{DN_DIALOG}_invoice_id"] = invoice_id
        st.session_state[f"{DN_DIALOG}_mode"] = "Delivery Against Invoice"
    mark_wired("dialog.save")


def _clear() -> None:
    for key in list(st.session_state.keys()):
        if key.startswith(DN_DIALOG):
            st.session_state.pop(key, None)
    st.session_state.pop(DN_SUBMIT_KEY, None)


def render_partner_charge_fields(
    services: dict,
    *,
    prefix: str,
) -> dict:
    """Shared partner select + delivery charge + paid controls.

    Returns dict suitable for create_delivery_note charges/partner kwargs.
    """
    partners_svc = services.get("delivery_partners")
    accounting = services.get("accounting")
    partner_id = ""
    partner_name = ""

    if partners_svc:
        partners = partners_svc.list_active_partners()
        opts = {"— Select partner —": ""}
        opts.update({f"{p.display_name} ({p.phone_number})": p.id for p in partners})
        pkey = f"{prefix}_partner"
        ensure_selectbox_option(pkey, list(opts.keys()))
        label = st.selectbox("Delivery partner", list(opts.keys()), key=pkey)
        partner_id = opts.get(label) or ""
        if partner_id:
            partner = partners_svc.get_partner(partner_id)
            if partner:
                partner_name = partner.display_name
                st.caption(partner.phone_number)

    charge_amt = st.number_input(
        "Delivery charge (₹)",
        min_value=0.0,
        value=0.0,
        key=f"{prefix}_charge",
    )
    paid_by_us = False
    paid_now = False
    paid_from = ""
    pay_mode = ""
    recoverable = False
    if charge_amt > 0:
        paid_by_us = st.checkbox(
            "Paid by business (payable to partner)",
            value=True,
            key=f"{prefix}_paid_us",
        )
        if paid_by_us:
            paid_now = st.checkbox("Already paid", key=f"{prefix}_paid_now")
            if paid_now and accounting:
                accounts = [
                    a
                    for a in accounting.list_accounts()
                    if a.is_active
                    and (
                        a.is_store_account
                        or "cash" in a.account_name.lower()
                        or "bank" in a.account_name.lower()
                        or "upi" in a.account_name.lower()
                    )
                ]
                if not accounts:
                    accounts = [a for a in accounting.list_accounts() if a.is_active]
                acct_opts = {a.account_name: a.id for a in accounts}
                if acct_opts:
                    paid_from = acct_opts[
                        st.selectbox(
                            "Paid from",
                            list(acct_opts.keys()),
                            key=f"{prefix}_paid_from",
                        )
                    ]
                pay_mode = st.selectbox(
                    "Payment mode",
                    ["Cash", "Bank", "UPI", "Other"],
                    key=f"{prefix}_pay_mode",
                )
        recoverable = st.checkbox(
            "Recover from customer",
            key=f"{prefix}_recoverable",
        )

    payment_status = DeliveryChargePaymentStatus.UNPAID.value
    if paid_by_us and paid_now:
        payment_status = DeliveryChargePaymentStatus.PAID.value

    return {
        "delivery_partner_id": partner_id,
        "delivery_partner_name": partner_name,
        "charges": {
            "paid_by_us": paid_by_us,
            "recoverable_from_customer": recoverable,
            "amount": charge_amt,
            "tax_amount": 0.0,
            "payment_status": payment_status,
            "payment_mode": pay_mode,
            "paid_from_account_id": paid_from,
            "partner_payable_amount": charge_amt if paid_by_us and not paid_now else 0.0,
            "customer_recoverable_amount": charge_amt if recoverable else 0.0,
            "payment_date": date.today() if paid_now else None,
        },
    }


def render_delivery_qty_grid(
    line_sources: list[dict],
    *,
    prefix: str,
) -> tuple[list[dict], list[str]]:
    """One row per item: name | ordered | prev | remaining | deliver qty."""
    st.markdown("**Items to deliver**")
    hdr = st.columns([3, 1, 1, 1, 1.2])
    hdr[0].caption("Item")
    hdr[1].caption("Ordered")
    hdr[2].caption("Delivered")
    hdr[3].caption("Remaining")
    hdr[4].caption("This delivery")

    lines: list[dict] = []
    qty_keys: list[str] = []
    for i, src in enumerate(line_sources):
        pending = src.get("pending")
        label = src["product_name"]
        cols = st.columns([3, 1, 1, 1, 1.2])
        cols[0].write(label)
        if pending is not None:
            cols[1].write(f"{src.get('qty_ordered', 0):g}")
            cols[2].write(f"{src.get('qty_previously_delivered', 0):g}")
            cols[3].write(f"{pending:g}")
            qkey = f"{prefix}_qty_{i}"
            qty_keys.append(qkey)
            qty = cols[4].number_input(
                "Qty",
                min_value=0.0,
                max_value=float(pending),
                value=float(pending),
                key=qkey,
                label_visibility="collapsed",
            )
        else:
            cols[1].write("—")
            cols[2].write("—")
            cols[3].write("—")
            qkey = f"{prefix}_qty_{i}"
            qty_keys.append(qkey)
            qty = cols[4].number_input(
                "Qty",
                min_value=0.0,
                value=1.0,
                key=qkey,
                label_visibility="collapsed",
            )
        if qty > 0:
            lines.append(
                {
                    "product_id": src["product_id"],
                    "product_name": src["product_name"],
                    "qty_delivered": qty,
                    "rate": src["rate"],
                    "qty_ordered": src.get("qty_ordered") or 0,
                    "qty_previously_delivered": src.get("qty_previously_delivered") or 0,
                    "sales_order_line_id": src.get("sales_order_line_id") or "",
                    "sales_invoice_line_id": src.get("sales_invoice_line_id") or "",
                }
            )
    return lines, qty_keys


def _line_sources_from_so(so) -> list[dict]:
    sources = []
    for sl in so.lines:
        if sl.qty_pending <= 0:
            continue
        sources.append(
            {
                "product_id": sl.product_id,
                "product_name": sl.product_name,
                "qty_ordered": sl.qty_ordered,
                "qty_previously_delivered": sl.qty_delivered,
                "pending": sl.qty_pending,
                "rate": sl.rate,
                "sales_order_line_id": sl.id,
            }
        )
    return sources


def _line_sources_from_invoice(sales, accounting, invoice_id: str) -> tuple[str, list[dict]]:
    voucher = accounting.get_voucher(invoice_id)
    if not voucher:
        return "", []
    from vaybooks.bms.domain.sales.line_items import parse_sales_line_items_note

    items, _, _ = parse_sales_line_items_note(voucher.description)
    pending_map = sales.invoice_pending_delivery_qty(invoice_id)
    delivered_map = sales.invoice_delivered_qty_by_product(invoice_id)
    customer_id = ""
    for line in voucher.lines:
        acct = accounting.get_account(line.account_id)
        if acct and acct.linked_customer_id:
            customer_id = acct.linked_customer_id
            break
    sources = []
    for item in items:
        product_id = str(item.get("product_id") or "")
        pending = pending_map.get(product_id, 0)
        if pending <= 0:
            continue
        sources.append(
            {
                "product_id": product_id,
                "product_name": item.get("item_name")
                or item.get("description")
                or product_id,
                "qty_ordered": float(item.get("qty") or 0),
                "qty_previously_delivered": delivered_map.get(product_id, 0),
                "pending": pending,
                "rate": float(item.get("rate") or 0),
                "sales_invoice_line_id": product_id,
            }
        )
    return customer_id, sources


@st.dialog(
    "Create Delivery Note",
    width="large",
    on_dismiss=make_dismiss_handler(DN_DIALOG),
)
def delivery_note_dialog(services: dict) -> None:
    if st.session_state.get(DN_DIALOG) != "new":
        return

    register_armed_dialog(DN_DIALOG)
    mark_wired("dialog.save")

    sales = services["sales"]
    accounting = services.get("accounting")

    mode_key = f"{DN_DIALOG}_mode"
    modes = ["Sales Order", "Delivery Against Invoice"]
    if st.session_state.get(mode_key) not in modes:
        st.session_state[mode_key] = "Sales Order"
    # Hide mode picker when already locked from SO/Invoice detail
    locked = bool(
        st.session_state.get(f"{DN_DIALOG}_so_id")
        or st.session_state.get(f"{DN_DIALOG}_invoice_id")
    )
    if locked:
        mode = st.session_state[mode_key]
        st.caption(mode)
    else:
        mode = st.radio(
            "Delivery against",
            modes,
            horizontal=True,
            key=mode_key,
        )

    so = None
    so_id = None
    invoice_id = None
    customer_id = None
    line_sources: list[dict] = []

    if mode == "Sales Order":
        open_orders = [
            so_
            for so_ in sales.list_sales_orders()
            if so_.status.value not in ("Cancelled", "Closed", "Delivered")
        ]
        so_opts = {"— Select sales order —": None}
        so_opts.update(
            {f"{so_.so_number} — {so_.customer_name}": so_.id for so_ in open_orders}
        )
        pre_so = st.session_state.get(f"{DN_DIALOG}_so_id")
        so_key = f"{DN_DIALOG}_so"
        if locked and pre_so:
            so_id = pre_so
            so = sales.get_sales_order(so_id)
        else:
            so_label = st.selectbox(
                "Sales order",
                list(so_opts.keys()),
                index=(
                    list(so_opts.values()).index(pre_so)
                    if pre_so in so_opts.values()
                    else 0
                ),
                key=so_key,
            )
            so_id = so_opts[so_label]
            so = sales.get_sales_order(so_id) if so_id else None
        if not so:
            st.info("Select a sales order with pending quantities.")
            return
        customer_id = so.customer_id
        st.caption(f"Customer: {so.customer_name}")
        line_sources = _line_sources_from_so(so)
    else:
        st.caption("Delivery Against Invoice — goods billed before dispatch.")
        if not accounting:
            st.error("Accounting service unavailable.")
            return
        invoices = accounting.list_vouchers_by_type(VoucherType.SALES_INVOICE)
        inv_opts = {"— Select invoice —": None}
        for inv in invoices:
            if sales.invoice_pending_delivery_qty(inv.id):
                inv_opts[f"{inv.voucher_number}"] = inv.id
        pre_inv = st.session_state.get(f"{DN_DIALOG}_invoice_id")
        if locked and pre_inv:
            invoice_id = pre_inv
        else:
            inv_label = st.selectbox(
                "Sales invoice",
                list(inv_opts.keys()),
                index=(
                    list(inv_opts.values()).index(pre_inv)
                    if pre_inv in inv_opts.values()
                    else 0
                ),
                key=f"{DN_DIALOG}_invoice",
            )
            invoice_id = inv_opts[inv_label]
        if not invoice_id:
            st.info("Select an invoice with pending delivery quantity.")
            return
        customer_id, line_sources = _line_sources_from_invoice(
            sales, accounting, invoice_id
        )
        if customer_id:
            cust = services["customers"].get_customer_detail(customer_id)
            if cust:
                st.caption(f"Customer: {cust.customer_name}")

    if not line_sources:
        st.warning("No pending items to deliver.")
        return
    if not customer_id:
        st.warning("Customer is required.")
        return

    date_key = f"{DN_DIALOG}_date"
    delivery_date = st.date_input(
        "Delivery date", value=date.today(), key=date_key
    )
    notes = st.text_input("Notes (optional)", key=f"{DN_DIALOG}_notes")

    lines, qty_keys = render_delivery_qty_grid(line_sources, prefix=DN_DIALOG)
    partner_fields = render_partner_charge_fields(services, prefix=DN_DIALOG)

    save_key = f"{DN_DIALOG}_save"
    do_save = st.button(
        "Create Delivery Note", type="primary", key=save_key
    ) or consume_submit(DN_SUBMIT_KEY)

    restore = st.session_state.pop(DN_FOCUS_KEY, None)
    get_strategy(DN_DIALOG).inject(
        chain=[date_key, *qty_keys, save_key],
        restore_key=restore,
        columns={"qty": qty_keys},
        above_first=date_key,
        below_last=save_key,
        component_key=f"dn_qty_{len(qty_keys)}",
    )

    if do_save:
        try:
            if not lines:
                raise ValueError("Enter at least one delivery quantity")
            if partner_fields["charges"]["amount"] > 0 and partner_fields[
                "charges"
            ]["paid_by_us"]:
                if not partner_fields["delivery_partner_id"]:
                    raise ValueError("Select a delivery partner for the charge")
            location_id = require_specific_location(services)
            dn = sales.create_delivery_note(
                customer_id=customer_id,
                delivery_date=delivery_date,
                lines=lines,
                sales_order_id=so_id,
                sales_invoice_id=invoice_id,
                notes=notes or "",
                confirm=False,
                location_id=location_id,
                delivery_partner_id=partner_fields["delivery_partner_id"],
                delivery_partner_name=partner_fields["delivery_partner_name"],
                charges=partner_fields["charges"],
            )
            # Confirm so SO/invoice qty and delivery-charge accounting post.
            sales.confirm_delivery_note(dn.id)
            _clear()
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def open_dn_dialog_if_armed(services: dict) -> None:
    if st.session_state.get(DN_DIALOG) == "new":
        delivery_note_dialog(services)
