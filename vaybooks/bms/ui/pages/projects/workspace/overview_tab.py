"""Overview tab — project control dashboard (AC-004)."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.domain.shared.enums import (
    ProjectActivityStatus,
    ProjectQuotationStatus,
    ProjectRABillStatus,
    VoucherType,
)
from vaybooks.bms.ui.pages.projects.workspace import helpers as H
from vaybooks.bms.ui.styles import metric_grid


def render_overview(services: dict, project) -> None:
    projects_svc = services["projects"]
    billing_svc = services.get("project_billing")
    budget_svc = services.get("project_budget")
    boq_svc = services.get("project_boq")
    report_svc = services.get("reports_projects")
    quote_svc = services.get("project_quotations")
    time_svc = services.get("project_time")
    expense_svc = services.get("project_expenses")

    party = {}
    wip = {}
    books_info = None
    budget_summary = None
    boq_totals = None
    blockers: list = []

    if billing_svc is not None:
        try:
            party = billing_svc.get_party_balances(project.id)
            wip = billing_svc.get_wip_balances(project.id)
            books_info = billing_svc.books_match(project.id)
        except Exception:
            pass

    if budget_svc is not None:
        try:
            budget_summary = budget_svc.budget_summary(project.id)
        except Exception:
            pass

    if boq_svc is not None:
        try:
            boq_totals = boq_svc.rollup_totals(project.id)
        except Exception:
            pass

    try:
        blockers = projects_svc.get_closure_blockers(
            project.id,
            billing_service=billing_svc,
            measurement_service=services.get("project_measurement"),
        )
    except Exception:
        pass

    original = float(
        project.original_contract_value
        or project.contract_value
        or 0
    )
    revised = float(
        project.revised_contract_value
        or project.contract_value
        or 0
    )

    weighted_pct = 0.0
    try:
        weighted_pct = projects_svc.get_weighted_progress(project.id)
    except Exception:
        pass

    retention = 0.0
    advances = 0.0
    invoiced = 0.0
    collected = 0.0
    if report_svc is not None:
        try:
            for row in report_svc.retention_register(project.id):
                retention += float(row.get("outstanding_retention") or 0)
        except Exception:
            pass
        try:
            register = report_svc.billing_register(project.id)
            for row in register.get("rows") or []:
                vtype = row.get("voucher_type")
                amount = float(row.get("net") or row.get("gross") or 0)
                if vtype == VoucherType.ADVANCE.value:
                    advances += amount
                elif vtype == VoucherType.SALES_INVOICE.value:
                    invoiced += amount
                elif vtype == VoucherType.RECEIPT.value:
                    collected += amount
        except Exception:
            pass

    if billing_svc is not None and invoiced == 0 and collected == 0:
        try:
            wip_billed = float(wip.get("billed_revenue") or 0)
            if wip_billed:
                invoiced = wip_billed
            outstanding = float(party.get("customer_outstanding") or 0)
            if invoiced:
                collected = max(invoiced - outstanding, 0.0)
        except Exception:
            pass

    recognised = 0.0
    recognition_svc = services.get("project_recognition")
    if recognition_svc is not None:
        try:
            entries = recognition_svc.list_entries(project.id)
            if entries:
                latest = max(entries, key=lambda e: (e.period_end, e.created_at))
                recognised = float(latest.prior_recognised or 0) + float(
                    latest.current_recognised or 0
                )
        except Exception:
            pass

    measured_qty = float(boq_totals.get("measured_qty_total") or 0) if boq_totals else 0.0
    certified_qty = float(boq_totals.get("certified_qty_total") or 0) if boq_totals else 0.0

    st.subheader("Control facts")
    st.caption(
        "Six separate control facts — never combined into a single progress number."
    )
    control_facts = [
        ("Physical %", f"{weighted_pct:.1f}%"),
        ("Measured qty", f"{measured_qty:,.2f}"),
        ("Certified qty", f"{certified_qty:,.2f}"),
        ("Invoiced", H.fmt_money(invoiced)),
        ("Collected", H.fmt_money(collected)),
        ("Recognised", H.fmt_money(recognised)),
    ]
    metric_grid(control_facts, suffix="prj_overview_facts")

    metrics = [
        ("Contract (original)", H.fmt_money(original)),
        ("Contract (revised)", H.fmt_money(revised)),
        (
            "Budget / Actual / Remaining",
            " / ".join(
                [
                    H.fmt_money(budget_summary.get("revised_total") if budget_summary else None),
                    H.fmt_money(budget_summary.get("actual") if budget_summary else None),
                    H.fmt_money(budget_summary.get("remaining") if budget_summary else None),
                ]
            )
            if budget_summary
            else "—",
        ),
        ("Customer outstanding", H.fmt_money(party.get("customer_outstanding"))),
        ("Retention held", H.fmt_money(retention)),
        ("Advances", H.fmt_money(advances)),
    ]
    metric_grid(metrics, suffix="prj_overview_kpi")
    H.render_badge(project.status.value)

    st.subheader("Closure blockers")
    blocking = [b for b in blockers if b.get("severity") == "block"]
    if blocking:
        for blocker in blocking:
            st.warning(blocker.get("message", blocker.get("type", "Blocker")))
    elif blockers:
        for blocker in blockers:
            st.info(blocker.get("message", blocker.get("type", "Warning")))
    else:
        st.success("No closure blockers detected.")

    action_cols = st.columns(3)
    if action_cols[0].button("Mark physically completed", key="prj_ov_phys_complete"):
        H.run_action(
            lambda: projects_svc.mark_physically_completed(project.id),
            "Marked physically completed",
        )
    if action_cols[1].button("Mark DLP", key="prj_ov_dlp"):
        H.run_action(
            lambda: projects_svc.mark_dlp(project.id),
            "Entered DLP",
        )
    force_close = st.checkbox("Force financial close", value=False, key="prj_ov_force_close")
    if action_cols[2].button("Financial close", key="prj_ov_fin_close"):
        H.run_action(
            lambda: projects_svc.close_project(
                project.id,
                force=force_close,
                billing_service=billing_svc,
                measurement_service=services.get("project_measurement"),
            ),
            "Project financially closed",
        )

    col1, col2 = st.columns(2)

    with col1:
        _work_snapshot(project, weighted_pct)
        _costs_snapshot(services, project, expense_svc, budget_summary)
        _billing_snapshot(services, project, quote_svc, billing_svc, report_svc)

    with col2:
        _money_snapshot(party, wip, retention, advances)
        _books_snapshot(books_info, services.get("projects_profitability"), project.id)
        _recent_snapshot(services, project, time_svc, expense_svc)


def _work_snapshot(project, weighted_pct: float) -> None:
    st.subheader("Work snapshot")
    st.write(f"**Weighted progress:** {weighted_pct:.1f}%")
    counts: dict[str, int] = {}
    for activity in project.activities:
        status = activity.status.value
        counts[status] = counts.get(status, 0) + 1
    if not counts:
        st.caption("No activities yet.")
    else:
        for status in [s.value for s in ProjectActivityStatus]:
            if counts.get(status):
                st.write(f"**{status}:** {counts[status]}")
    st.caption("Use the **Work** tab to manage phases and activities.")


def _costs_snapshot(services, project, expense_svc, budget_summary) -> None:
    st.subheader("Costs snapshot")
    expense_count = 0
    if expense_svc is not None:
        try:
            expense_count = len(expense_svc.list_by_project(project.id))
        except Exception:
            pass
    st.write(f"**Expenses:** {expense_count}")
    if budget_summary:
        st.write(f"**Budget actual:** {H.fmt_money(budget_summary.get('actual'))}")
        st.write(f"**Committed:** {H.fmt_money(budget_summary.get('committed'))}")
    st.caption("Use the **Costs** and **Budget** tabs for detail.")


def _billing_snapshot(services, project, quote_svc, billing_svc, report_svc) -> None:
    st.subheader("Billing snapshot")
    open_quotes = 0
    if quote_svc is not None:
        try:
            open_statuses = {
                ProjectQuotationStatus.DRAFT.value,
                ProjectQuotationStatus.PENDING_APPROVAL.value,
                ProjectQuotationStatus.APPROVED.value,
                ProjectQuotationStatus.SENT.value,
            }
            quotes = quote_svc.list_by_project(project.id)
            open_quotes = sum(1 for q in quotes if q.status.value in open_statuses)
        except Exception:
            pass
    st.write(f"**Open quotations:** {open_quotes}")

    latest_invoice = "—"
    if report_svc is not None:
        try:
            register = report_svc.billing_register(project.id)
            inv_rows = [
                r
                for r in register.get("rows") or []
                if r.get("voucher_type") == VoucherType.SALES_INVOICE.value
            ]
            if inv_rows:
                latest_invoice = (
                    f"{inv_rows[0].get('voucher_number')} "
                    f"({H.fmt_money(inv_rows[0].get('net'))})"
                )
        except Exception:
            pass
    st.write(f"**Latest invoice:** {latest_invoice}")

    open_ras = 0
    if billing_svc is not None:
        try:
            ras = billing_svc.list_ra_bills(project.id)
            open_ras = sum(
                1
                for r in ras
                if (
                    r.status.value if hasattr(r.status, "value") else r.status
                )
                in (
                    ProjectRABillStatus.DRAFT.value,
                    ProjectRABillStatus.SUBMITTED.value,
                    ProjectRABillStatus.CLAIMED.value,
                    ProjectRABillStatus.CERTIFIED.value,
                    ProjectRABillStatus.PARTIALLY_CERTIFIED.value,
                )
            )
        except Exception:
            pass
    st.write(f"**Open RA bills:** {open_ras}")
    st.caption("Use the **Billing** tab for quotations, RA, and invoices.")


def _money_snapshot(party, wip, retention, advances) -> None:
    st.subheader("Money snapshot")
    st.write(f"**Customer outstanding:** {H.fmt_money(party.get('customer_outstanding'))}")
    st.write(f"**Advances (liability):** {H.fmt_money(advances)}")
    st.write(f"**Retention held:** {H.fmt_money(retention)}")
    st.write(f"**Unbilled cost:** {H.fmt_money(wip.get('unbilled_cost'))}")
    st.caption("Use the **Money** tab for receipts and payments.")


def _books_snapshot(books_info, profitability, project_id: str) -> None:
    st.subheader("Books match")
    if books_info is not None:
        match_icon = "✓" if books_info.get("books_match") else "✗"
        st.write(f"**Match:** {match_icon}")
        st.caption(
            f"Outstanding {H.fmt_money(books_info.get('customer_outstanding'))} · "
            f"Vendor {H.fmt_money(books_info.get('vendor_payable'))}"
        )
    elif profitability is not None:
        try:
            check = profitability.books_match_check(project_id)
            match_icon = "✓" if check.get("all_match") else "✗"
            st.write(f"**Match:** {match_icon}")
        except Exception:
            st.caption("Books match unavailable.")
    else:
        st.caption("Billing service not configured.")


def _recent_snapshot(services, project, time_svc, expense_svc) -> None:
    st.subheader("Recent")
    if time_svc is not None:
        try:
            entries = sorted(
                time_svc.list_by_project(project.id),
                key=lambda e: e.work_date,
                reverse=True,
            )[:3]
            if entries:
                st.markdown("**Time**")
                for entry in entries:
                    st.caption(
                        f"{entry.work_date} · {entry.worker_name} · "
                        f"{entry.duration_minutes} min · {H.fmt_money(entry.labour_cost)}"
                    )
        except Exception:
            pass

    if expense_svc is not None:
        try:
            expenses = sorted(
                expense_svc.list_by_project(project.id),
                key=lambda e: e.expense_date,
                reverse=True,
            )[:3]
            if expenses:
                st.markdown("**Expenses**")
                for exp in expenses:
                    st.caption(
                        f"{exp.expense_date} · {exp.expense_name} · {H.fmt_money(exp.amount)}"
                    )
        except Exception:
            pass

    st.caption("Use the **Time** tab to record labour.")
