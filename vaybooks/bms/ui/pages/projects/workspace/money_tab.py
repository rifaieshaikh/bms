"""Money tab — receipts, advances, vendor payments, retention."""

from __future__ import annotations

import json
import re

import pandas as pd
import streamlit as st

from vaybooks.bms.domain.shared.enums import AccountType, VoucherType
from vaybooks.bms.ui.pages.projects.workspace import helpers as H
from vaybooks.bms.ui.styles import metric_grid


def _store_account_options(services: dict) -> dict[str, str]:
    try:
        accounts = services["accounting"].get_store_accounts()
    except Exception:
        return {}
    return {a.account_name: a.id for a in accounts}


def _account_options(services: dict, account_type=None) -> dict[str, str]:
    try:
        accounts = services["accounting"].list_accounts(active_only=False)
    except Exception:
        return {}
    if account_type is not None:
        accounts = [a for a in accounts if a.account_type == account_type]
    return {a.account_name: a.id for a in accounts}


def _customer_account_options(services: dict) -> dict[str, str]:
    try:
        accounts = services["accounting"].list_accounts(active_only=False)
    except Exception:
        return {}
    return {a.account_name: a.id for a in accounts if a.linked_customer_id}


def _vendor_account_options(services: dict) -> dict[str, str]:
    try:
        accounts = services["accounting"].list_accounts(active_only=False)
    except Exception:
        return {}
    return {a.account_name: a.id for a in accounts if a.linked_vendor_id}


def _default_customer_account_id(services: dict, project) -> str | None:
    accounting = services.get("accounting")
    if accounting is None:
        return None
    try:
        account = accounting.get_customer_account(project.customer_id)
        return account.id if account else None
    except Exception:
        return None


def _account_label(options: dict[str, str], account_id: str | None) -> str | None:
    if not account_id:
        return None
    for label, aid in options.items():
        if aid == account_id:
            return label
    return None


def _customer_tds_total(services: dict, project_id: str, billing_svc) -> float:
    """Sum customer TDS from receipt voucher metadata when present."""
    total = 0.0
    pattern = re.compile(r"\n<!--TDS:(\{.*?\})-->", re.DOTALL)
    try:
        if billing_svc is not None and hasattr(billing_svc, "_list_project_vouchers"):
            vouchers = billing_svc._list_project_vouchers(project_id)
        else:
            return 0.0
        for voucher in vouchers:
            if voucher.voucher_type != VoucherType.RECEIPT:
                continue
            match = pattern.search(voucher.description or "")
            if not match:
                continue
            try:
                payload = json.loads(match.group(1))
                total += float(payload.get("amount") or 0)
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
    except Exception:
        pass
    return round(total, 2)


def _advances_liability(report_svc, project_id: str) -> float:
    if report_svc is None:
        return 0.0
    try:
        register = report_svc.billing_register(project_id)
        total = 0.0
        for row in register.get("rows") or []:
            if row.get("voucher_type") == VoucherType.ADVANCE.value:
                total += float(row.get("net") or row.get("gross") or 0)
        return round(total, 2)
    except Exception:
        return 0.0


def _collected_total(report_svc, project_id: str) -> float:
    if report_svc is None:
        return 0.0
    try:
        register = report_svc.billing_register(project_id)
        total = 0.0
        for row in register.get("rows") or []:
            if row.get("voucher_type") == VoucherType.RECEIPT.value:
                total += float(row.get("net") or row.get("collected") or row.get("gross") or 0)
        return round(total, 2)
    except Exception:
        return 0.0



def _receipt_allocation_totals(billing_svc, project_id: str) -> tuple[float, float]:
    """Sum short_payment / unallocated from receipt ALLOC_INVOICE metadata."""
    short_total = 0.0
    unalloc_total = 0.0
    if billing_svc is None or not hasattr(billing_svc, "_list_project_vouchers"):
        return 0.0, 0.0
    try:
        vouchers = billing_svc._list_project_vouchers(project_id)
    except Exception:
        return 0.0, 0.0
    for voucher in vouchers:
        if voucher.voucher_type != VoucherType.RECEIPT:
            continue
        meta = {}
        if hasattr(billing_svc, "_parse_meta"):
            meta = billing_svc._parse_meta(voucher.description or "", "ALLOC_INVOICE") or {}
        short_total += float(meta.get("short_payment") or 0)
        unalloc_total += float(meta.get("unallocated") or 0)
    return round(short_total, 2), round(unalloc_total, 2)


def render_money(services: dict, project) -> None:
    billing_svc = services.get("project_billing")
    report_svc = services.get("reports_projects")
    if billing_svc is None:
        st.warning("Billing service is not configured.")
        return

    try:
        party = billing_svc.get_party_balances(project.id)
        wip = billing_svc.get_wip_balances(project.id)
    except Exception as exc:
        st.error(str(exc))
        return

    retention_outstanding = 0.0
    if report_svc is not None:
        try:
            for row in report_svc.retention_register(project.id):
                retention_outstanding += float(row.get("outstanding_retention") or 0)
        except Exception:
            pass

    advances = _advances_liability(report_svc, project.id)
    customer_tds = _customer_tds_total(services, project.id, billing_svc)
    collected = _collected_total(report_svc, project.id)
    invoice_outstanding = float(party.get("customer_outstanding") or 0)
    short_pay, unallocated = _receipt_allocation_totals(billing_svc, project.id)

    st.markdown("**Customer collections**")
    metric_grid(
        [
            ("Advances (liability)", H.fmt_money(advances)),
            ("Invoice outstanding", H.fmt_money(invoice_outstanding)),
            ("Retention held", H.fmt_money(retention_outstanding)),
            ("Customer TDS", H.fmt_money(customer_tds)),
            ("Collected", H.fmt_money(collected)),
            ("Short payment", H.fmt_money(short_pay)),
            ("Unallocated", H.fmt_money(unallocated)),
        ],
        suffix="prj_money_top",
    )
    st.caption(
        "Advances are customer prepayments (liability). Customer TDS is deducted at source on receipts when recorded."
    )

    st.markdown("**Project balances**")
    metric_grid(
        [
            ("Vendor payable", H.fmt_money(party.get("vendor_payable"))),
            ("Unbilled cost", H.fmt_money(wip.get("unbilled_cost"))),
            ("Billed revenue", H.fmt_money(wip.get("billed_revenue"))),
        ],
        suffix="prj_money_bal",
    )

    tabs = st.tabs(
        [
            "Invoices & Receipts",
            "Advances & Credits",
            "Vendor Payments",
            "Retention",
            "Other",
        ]
    )

    store_opts = _store_account_options(services)
    customer_opts = _customer_account_options(services)
    vendor_opts = _vendor_account_options(services)
    expense_opts = _account_options(services, AccountType.EXPENSE)
    default_customer_id = _default_customer_account_id(services, project)
    default_customer_label = _account_label(customer_opts, default_customer_id)

    with tabs[0]:
        _render_invoices_receipts(services, project, billing_svc, report_svc, store_opts, customer_opts, default_customer_label)

    with tabs[1]:
        _render_advances_credits(services, project, billing_svc, report_svc, store_opts)

    with tabs[2]:
        _render_vendor_payments(project, billing_svc, store_opts, vendor_opts, expense_opts)

    with tabs[3]:
        _render_retention(billing_svc, report_svc, project.id)

    with tabs[4]:
        _render_other(services, project, billing_svc, report_svc)


def _render_invoices_receipts(services, project, billing_svc, report_svc, store_opts, customer_opts, default_customer_label):
    if report_svc is not None:
        try:
            register = report_svc.billing_register(project.id)
            inv_rows = [
                r
                for r in register.get("rows") or []
                if r.get("voucher_type") == VoucherType.SALES_INVOICE.value
                and float(r.get("outstanding") or 0) > 0
            ]
            if inv_rows:
                st.subheader("Outstanding invoices")
                st.dataframe(
                    pd.DataFrame(inv_rows),
                    use_container_width=True,
                    hide_index=True,
                )
        except Exception as exc:
            st.caption(str(exc))

    st.subheader("Record receipt")
    recv_label = st.selectbox(
        "Receiving account",
        options=list(store_opts.keys()) if store_opts else [""],
        key="prj_rcpt_recv",
    )
    cust_labels = list(customer_opts.keys())
    cust_index = (
        cust_labels.index(default_customer_label)
        if default_customer_label in cust_labels
        else 0
    ) if cust_labels else 0
    cust_label = st.selectbox(
        "Customer account",
        options=cust_labels or [""],
        index=cust_index,
        key="prj_rcpt_cust",
    )
    amount = st.number_input("Amount", min_value=0.01, value=100.0, key="prj_rcpt_amt")
    description = st.text_input("Description (optional)", key="prj_rcpt_desc")
    alloc_invoice_id = st.text_input(
        "Allocate to invoice id (optional)",
        key="prj_rcpt_alloc_inv",
        help="Leave blank for unallocated receipt, or enter invoice voucher id.",
    ).strip()
    alloc_amount = st.number_input(
        "Allocation amount",
        min_value=0.0,
        value=0.0,
        key="prj_rcpt_alloc_amt",
        help="Amount applied to the invoice; remainder is unallocated.",
    )
    if st.button("Record receipt", type="primary", key="prj_rcpt_save"):
        if not store_opts or not customer_opts:
            st.error("Receiving and customer accounts are required")
        else:
            allocations = None
            if alloc_invoice_id and alloc_amount > 0:
                allocations = [{"invoice_id": alloc_invoice_id, "amount": float(alloc_amount)}]

            def _do_receipt():
                result = billing_svc.create_receipt(
                    project.id,
                    receiving_account_id=store_opts[recv_label],
                    customer_account_id=customer_opts[cust_label],
                    amount=amount,
                    description=description,
                    allocations=allocations,
                )
                if isinstance(result, dict):
                    st.session_state["prj_rcpt_last_alloc"] = {
                        "short_payment": result.get("short_payment", 0),
                        "unallocated": result.get("unallocated", 0),
                    }
                return result

            H.run_action(_do_receipt, "Receipt recorded")
    last = st.session_state.get("prj_rcpt_last_alloc")
    if last:
        st.caption(
            f"Last receipt — short payment: {H.fmt_money(last.get('short_payment'))}, "
            f"unallocated: {H.fmt_money(last.get('unallocated'))}"
        )


def _render_advances_credits(services, project, billing_svc, report_svc, store_opts):
    st.subheader("Customer advance")
    adv_recv = st.selectbox(
        "Receiving account",
        options=list(store_opts.keys()) if store_opts else [""],
        key="prj_adv_recv",
    )
    adv_amount = st.number_input("Amount", min_value=0.01, value=100.0, key="prj_adv_amt")
    adv_desc = st.text_input("Description (optional)", key="prj_adv_desc")
    if st.button("Record advance", type="primary", key="prj_adv_save"):
        if not store_opts:
            st.error("Receiving account is required")
        else:
            H.run_action(
                lambda: billing_svc.create_customer_advance(
                    project.id,
                    receiving_account_id=store_opts[adv_recv],
                    amount=adv_amount,
                    description=adv_desc,
                ),
                "Advance recorded",
            )

    st.subheader("Refund")
    refund_store = st.selectbox(
        "Store account",
        options=list(store_opts.keys()) if store_opts else [""],
        key="prj_ref_store",
    )
    refund_amount = st.number_input("Amount", min_value=0.01, value=100.0, key="prj_ref_amt")
    refund_desc = st.text_input("Description (optional)", key="prj_ref_desc")
    if st.button("Record refund", type="primary", key="prj_ref_save"):
        if not store_opts:
            st.error("Store account is required")
        else:
            H.run_action(
                lambda: billing_svc.create_refund(
                    project.id,
                    store_account_id=store_opts[refund_store],
                    amount=refund_amount,
                    description=refund_desc,
                ),
                "Refund recorded",
            )

    st.subheader("Credit note")
    cn_amount = st.number_input("Amount", min_value=0.01, value=100.0, key="prj_cn_amt")
    cn_desc = st.text_input("Description (optional)", key="prj_cn_desc")
    if st.button("Create credit note", type="primary", key="prj_cn_save"):
        H.run_action(
            lambda: billing_svc.create_credit_note(
                project.id,
                amount=cn_amount,
                description=cn_desc,
            ),
            "Credit note created",
        )

    if report_svc is not None:
        try:
            register = report_svc.billing_register(project.id)
            related = [
                r
                for r in register.get("rows") or []
                if r.get("voucher_type")
                in (
                    VoucherType.ADVANCE.value,
                    VoucherType.REFUND.value,
                    VoucherType.SALES_RETURN.value,
                )
            ]
            if related:
                st.subheader("Related vouchers")
                st.dataframe(pd.DataFrame(related), use_container_width=True, hide_index=True)
        except Exception as exc:
            st.caption(str(exc))


def _render_vendor_payments(project, billing_svc, store_opts, vendor_opts, expense_opts):
    st.subheader("Vendor payment")
    vendor_label = st.selectbox(
        "Vendor account",
        options=list(vendor_opts.keys()) if vendor_opts else [""],
        key="prj_vp_vendor",
    )
    expense_label = st.selectbox(
        "Expense account",
        options=list(expense_opts.keys()) if expense_opts else [""],
        key="prj_vp_expense",
    )
    paying_label = st.selectbox(
        "Paying account",
        options=list(store_opts.keys()) if store_opts else [""],
        key="prj_vp_paying",
    )
    gross_amount = st.number_input(
        "Gross amount",
        min_value=0.01,
        value=100.0,
        key="prj_vp_gross",
    )
    tds_section = st.text_input("TDS section", key="prj_vp_tds_section")
    tds_rate = st.number_input("TDS rate %", min_value=0.0, value=0.0, key="prj_vp_tds_rate")
    tds_amount = st.number_input("TDS amount", min_value=0.0, value=0.0, key="prj_vp_tds_amt")
    vp_desc = st.text_input("Description (optional)", key="prj_vp_desc")
    if st.button("Record vendor payment", type="primary", key="prj_vp_save"):
        if not vendor_opts or not expense_opts or not store_opts:
            st.error("Vendor, expense, and paying accounts are required")
        else:
            H.run_action(
                lambda: billing_svc.create_vendor_payment(
                    project.id,
                    vendor_account_id=vendor_opts[vendor_label],
                    expense_account_id=expense_opts[expense_label],
                    paying_account_id=store_opts[paying_label],
                    amount=gross_amount - tds_amount,
                    gross_amount=gross_amount,
                    tds_section=tds_section,
                    tds_rate=tds_rate,
                    tds_amount=tds_amount,
                    description=vp_desc,
                ),
                "Vendor payment recorded",
            )


def _render_retention(billing_svc, report_svc, project_id: str):
    if report_svc is None:
        st.info("Reports service is not configured.")
        return
    try:
        retention_rows = report_svc.retention_register(project_id)
    except Exception as exc:
        st.error(str(exc))
        return

    if not retention_rows:
        H.empty_state("No retention entries.")
        return

    st.dataframe(pd.DataFrame(retention_rows), use_container_width=True, hide_index=True)
    for row in retention_rows:
        bal = float(row.get("outstanding_retention") or 0)
        entry_id = row.get("entry_id")
        if not entry_id or bal <= 0:
            continue
        if st.button(
            f"Release retention {row.get('invoice_number', entry_id[:8])}",
            key=f"prj_ret_rel_{entry_id}",
        ):
            H.run_action(
                lambda eid=entry_id: billing_svc.release_retention(eid),
                "Retention released",
            )


def _render_other(services, project, billing_svc, report_svc):
    st.subheader("Write-off")
    wo_amount = st.number_input("Amount", min_value=0.01, value=100.0, key="prj_wo_amt")
    wo_reason = st.text_input("Reason", key="prj_wo_reason")
    if st.button("Write off receivable", type="primary", key="prj_wo_save"):
        H.run_action(
            lambda: billing_svc.write_off_receivable(
                project.id,
                amount=wo_amount,
                reason=wo_reason,
            ),
            "Write-off recorded",
        )

    st.subheader("Cost transfer")
    try:
        other_projects = [
            p for p in services["projects"].list_projects() if p.id != project.id
        ]
    except Exception:
        other_projects = []
    target_labels = {f"{p.project_number} — {p.name}": p.id for p in other_projects}
    target_label = st.selectbox(
        "To project",
        options=list(target_labels.keys()) if target_labels else [""],
        key="prj_xfer_target",
    )
    xfer_amount = st.number_input("Amount", min_value=0.01, value=100.0, key="prj_xfer_amt")
    xfer_reason = st.text_input("Reason", key="prj_xfer_reason")
    if st.button("Transfer cost", type="primary", key="prj_xfer_save"):
        if not target_labels:
            st.error("Select a destination project")
        else:
            H.run_action(
                lambda: billing_svc.transfer_cost(
                    project.id,
                    target_labels[target_label],
                    xfer_amount,
                    xfer_reason,
                ),
                "Cost transferred",
            )

    if report_svc is not None:
        try:
            write_offs = report_svc.write_offs(project.id)
            if write_offs:
                st.subheader("Write-offs")
                st.dataframe(pd.DataFrame(write_offs), use_container_width=True, hide_index=True)
        except Exception as exc:
            st.caption(str(exc))
        try:
            transfers = report_svc.transfers(project.id)
            if transfers:
                st.subheader("Cost transfers")
                st.dataframe(pd.DataFrame(transfers), use_container_width=True, hide_index=True)
        except Exception as exc:
            st.caption(str(exc))
