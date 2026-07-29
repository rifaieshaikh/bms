"""Shared UI to pay unpaid delivery-partner charges."""

from __future__ import annotations

from datetime import date

import streamlit as st


def render_pay_delivery_charges(
    services: dict,
    *,
    partner_id: str | None = None,
    key_prefix: str = "pay_dc",
) -> None:
    """List unpaid DN charges and post payment for a selected note."""
    sales = services.get("sales")
    accounting = services.get("accounting")
    if not sales or not accounting:
        st.warning("Sales/accounting services unavailable.")
        return

    unpaid = sales.list_unpaid_delivery_charges(partner_id)
    if not unpaid:
        st.info("No unpaid delivery charges.")
        return

    opts = {
        f"{dn.dn_number} — {dn.customer_name} — ₹{dn.charges.amount:,.2f}"
        + (f" ({dn.delivery_partner_name})" if not partner_id else "")
        : dn.id
        for dn in unpaid
    }
    label = st.selectbox(
        "Delivery note",
        list(opts.keys()),
        key=f"{key_prefix}_dn",
    )
    dn_id = opts[label]
    dn = sales.get_delivery_note(dn_id)
    if not dn:
        return

    amount = float(dn.charges.partner_payable_amount or dn.charges.amount)
    st.caption(f"Payable ₹{amount:,.2f} to {dn.delivery_partner_name or 'partner'}")

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
    if not acct_opts:
        st.error("No payment accounts found.")
        return
    paid_from = acct_opts[
        st.selectbox("Paid from", list(acct_opts.keys()), key=f"{key_prefix}_acct")
    ]
    mode = st.selectbox(
        "Mode",
        ["Cash", "Bank", "UPI", "Other"],
        key=f"{key_prefix}_mode",
    )
    ref = st.text_input("Reference", key=f"{key_prefix}_ref")
    pay_date = st.date_input("Payment date", value=date.today(), key=f"{key_prefix}_date")

    if st.button("Post payment", type="primary", key=f"{key_prefix}_go"):
        try:
            sales.record_delivery_partner_payment(
                dn_id,
                paid_from_account_id=paid_from,
                payment_mode=mode,
                payment_reference=ref,
                payment_date=pay_date,
                amount=amount,
            )
            st.success(f"Payment recorded for {dn.dn_number}")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
