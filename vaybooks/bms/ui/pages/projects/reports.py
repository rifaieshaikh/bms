"""Project reports — P1 portfolio and per-project profitability views."""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import streamlit as st

from vaybooks.bms.domain.shared.enums import ProjectStatus
from vaybooks.bms.ui.styles import metric_grid

REPORT_TYPES = [
    "Portfolio Summary",
    "Activity Profitability",
    "Man-hours by Worker",
    "Unallocated Costs",
    "WIP / Unbilled Cost",
    "Billing Register",
    "Customer Outstanding",
    "Vendor Payables",
    "Quotation Pipeline",
    "Retention Register",
    "Collections & Outstanding",
    "At-Risk Projects",
    "Variations Log",
    "Cost Transfers",
    "Write-offs",
    "TDS Deducted",
    "PO Committed Cost",
    "Document Inventory",
    "BOQ Status",
    "Measurement Register",
    "RA Register (Claimed vs Certified)",
    "Budget vs Actual",
]


def _date_range_picker(key_prefix: str) -> tuple[date, date]:
    today = date.today()
    default_start = today.replace(day=1)
    cols = st.columns(2)
    start = cols[0].date_input(
        "From",
        value=default_start,
        key=f"{key_prefix}_start",
    )
    end = cols[1].date_input(
        "To",
        value=today,
        key=f"{key_prefix}_end",
    )
    if start > end:
        start, end = end, start
    return start, end


def _as_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _export_csv(df: pd.DataFrame, filename: str) -> None:
    if df.empty:
        return
    st.download_button(
        "Export CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=filename,
        mime="text/csv",
        key=f"export_{filename}",
    )


def _project_picker(services: dict, key: str) -> str | None:
    try:
        projects = services["projects"].list_projects()
    except Exception as exc:
        st.error(f"Could not load projects: {exc}")
        return None
    if not projects:
        st.info("No projects available.")
        return None
    labels = {f"{p.project_number} — {p.name}": p.id for p in projects}
    label = st.selectbox("Project", options=list(labels.keys()), key=key)
    return labels.get(label)


def _filter_portfolio_by_dates(rows: list[dict], services: dict, start: date, end: date) -> list[dict]:
    """Best-effort date filter using project start/created dates."""
    try:
        projects = {p.id: p for p in services["projects"].list_projects()}
    except Exception:
        return rows
    filtered = []
    for row in rows:
        project = projects.get(row.get("project_id"))
        if not project:
            filtered.append(row)
            continue
        ref = _as_date(project.start_date) or _as_date(project.created_at)
        if ref is None or start <= ref <= end:
            filtered.append(row)
    return filtered


def _render_portfolio_summary(services: dict, start: date, end: date) -> None:
    report_svc = services.get("reports_projects")
    if report_svc is None:
        st.warning("Project reports service is not configured.")
        return
    status = st.selectbox(
        "Status filter",
        options=["All"] + [s.value for s in ProjectStatus],
        key="prj_rpt_portfolio_status",
    )
    try:
        status_filter = ProjectStatus(status) if status != "All" else None
        rows = report_svc.portfolio_summary(status=status_filter)
    except Exception as exc:
        st.error(str(exc))
        return

    rows = _filter_portfolio_by_dates(rows, services, start, end)
    if not rows:
        st.info("No rows for the selected period.")
        return

    totals = {
        "projects": len(rows),
        "contract_value": sum(float(r.get("contract_value") or 0) for r in rows),
        "total_cost": sum(float(r.get("total_cost") or 0) for r in rows),
        "person_hours": sum(float(r.get("person_hours") or 0) for r in rows),
    }
    metric_grid(
        [
            ("Projects", totals["projects"]),
            ("Contract value", f"₹{totals['contract_value']:,.0f}"),
            ("Total cost", f"₹{totals['total_cost']:,.0f}"),
            ("Person-hours", f"{totals['person_hours']:,.1f}"),
        ],
        suffix="prj_rpt_portfolio",
    )

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
    _export_csv(df, "project_portfolio_summary.csv")


def _render_activity_profitability(services: dict, start: date, end: date) -> None:
    report_svc = services.get("reports_projects")
    if report_svc is None:
        st.warning("Project reports service is not configured.")
        return
    project_id = _project_picker(services, "prj_rpt_activity_project")
    if not project_id:
        return
    try:
        rows = report_svc.activity_profitability(project_id)
    except Exception as exc:
        st.error(str(exc))
        return
    if not rows:
        st.info("No activity profitability data.")
        return
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
    _export_csv(df, f"activity_profitability_{project_id}.csv")
    st.caption(f"Period: {start:%d %b %Y} → {end:%d %b %Y}")


def _render_man_hours_by_worker(services: dict, start: date, end: date) -> None:
    report_svc = services.get("reports_projects")
    if report_svc is None:
        st.warning("Project reports service is not configured.")
        return
    project_id = _project_picker(services, "prj_rpt_hours_project")
    if not project_id:
        return
    try:
        rows = report_svc.man_hours_by_worker(project_id)
    except Exception as exc:
        st.error(str(exc))
        return
    if not rows:
        st.info("No time logged for this project.")
        return

    time_svc = services.get("project_time")
    if time_svc is not None:
        try:
            entries = time_svc.list_by_project(project_id)
            filtered_workers = {
                e.worker_id or e.worker_name
                for e in entries
                if start <= e.work_date <= end
            }
            rows = [
                r for r in rows
                if (r.get("worker_id") or r.get("worker_name")) in filtered_workers
            ] or rows
        except Exception:
            pass

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
    _export_csv(df, f"man_hours_by_worker_{project_id}.csv")
    st.caption(f"Period: {start:%d %b %Y} → {end:%d %b %Y}")


def _render_unallocated_costs(services: dict, start: date, end: date) -> None:
    report_svc = services.get("reports_projects")
    if report_svc is None:
        st.warning("Project reports service is not configured.")
        return
    project_id = _project_picker(services, "prj_rpt_unalloc_project")
    if not project_id:
        return
    try:
        payload = report_svc.unallocated_costs(project_id)
    except Exception as exc:
        st.error(str(exc))
        return

    expenses = payload.get("expenses") or []
    filtered = [
        e for e in expenses
        if _as_date(e.get("expense_date")) is None
        or start <= _as_date(e.get("expense_date")) <= end
    ]
    total = sum(float(e.get("amount") or 0) for e in filtered)

    metric_grid(
        [
            ("Unallocated cost", f"₹{total:,.0f}"),
            ("Expense lines", len(filtered)),
        ],
        suffix="prj_rpt_unalloc",
    )

    df = pd.DataFrame(filtered)
    if df.empty:
        st.info("No unallocated costs in the selected period.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True)
    _export_csv(df, f"unallocated_costs_{project_id}.csv")


def _optional_project_picker(services: dict, key: str) -> str | None:
    try:
        projects = services["projects"].list_projects()
    except Exception as exc:
        st.error(f"Could not load projects: {exc}")
        return None
    if not projects:
        st.info("No projects available.")
        return None
    labels = {"— All projects —": None}
    labels.update({f"{p.project_number} — {p.name}": p.id for p in projects})
    label = st.selectbox("Project (optional)", options=list(labels.keys()), key=key)
    return labels.get(label)


def _render_wip_unbilled(services: dict, start: date, end: date) -> None:
    report_svc = services.get("reports_projects")
    if report_svc is None:
        st.warning("Project reports service is not configured.")
        return
    project_id = _project_picker(services, "prj_rpt_wip_project")
    if not project_id:
        return
    try:
        payload = report_svc.wip_unbilled(project_id)
    except Exception as exc:
        st.error(str(exc))
        return
    metric_grid(
        [
            ("Unbilled cost", f"₹{float(payload.get('unbilled_cost') or 0):,.0f}"),
            ("Total cost", f"₹{float(payload.get('total_cost') or 0):,.0f}"),
            ("Billed revenue", f"₹{float(payload.get('billed_revenue') or 0):,.0f}"),
        ],
        suffix="prj_rpt_wip",
    )
    st.caption(f"Period: {start:%d %b %Y} → {end:%d %b %Y}")


def _render_billing_register(services: dict, start: date, end: date) -> None:
    report_svc = services.get("reports_projects")
    if report_svc is None:
        st.warning("Project reports service is not configured.")
        return
    project_id = _project_picker(services, "prj_rpt_billing_project")
    if not project_id:
        return
    try:
        payload = report_svc.billing_register(project_id)
    except Exception as exc:
        st.error(str(exc))
        return
    rows = payload.get("rows") or []
    filtered = [
        r for r in rows
        if _as_date(r.get("voucher_date")) is None
        or start <= _as_date(r.get("voucher_date")) <= end
    ]
    st.metric("Total invoiced", f"₹{float(payload.get('total_invoiced') or 0):,.0f}")
    df = pd.DataFrame(filtered or rows)
    if df.empty:
        st.info("No billing vouchers for this project.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True)
    _export_csv(df, f"billing_register_{project_id}.csv")


def _render_customer_outstanding(services: dict, start: date, end: date) -> None:
    report_svc = services.get("reports_projects")
    if report_svc is None:
        st.warning("Project reports service is not configured.")
        return
    project_id = _project_picker(services, "prj_rpt_cust_out_project")
    if not project_id:
        return
    try:
        payload = report_svc.customer_outstanding(project_id)
    except Exception as exc:
        st.error(str(exc))
        return
    st.metric(
        "Customer outstanding",
        f"₹{float(payload.get('customer_outstanding') or 0):,.0f}",
    )
    st.caption(f"Period: {start:%d %b %Y} → {end:%d %b %Y}")


def _render_vendor_payables(services: dict, start: date, end: date) -> None:
    report_svc = services.get("reports_projects")
    if report_svc is None:
        st.warning("Project reports service is not configured.")
        return
    project_id = _project_picker(services, "prj_rpt_vendor_project")
    if not project_id:
        return
    try:
        payload = report_svc.vendor_payables(project_id)
    except Exception as exc:
        st.error(str(exc))
        return
    st.metric("Vendor payable", f"₹{float(payload.get('vendor_payable') or 0):,.0f}")
    st.caption(f"Period: {start:%d %b %Y} → {end:%d %b %Y}")


def _render_quotation_pipeline(services: dict, start: date, end: date) -> None:
    report_svc = services.get("reports_projects")
    if report_svc is None:
        st.warning("Project reports service is not configured.")
        return
    project_id = _optional_project_picker(services, "prj_rpt_quote_pipe")
    try:
        rows = report_svc.quotation_pipeline(project_id)
    except Exception as exc:
        st.error(str(exc))
        return
    filtered = [
        r for r in rows
        if _as_date(r.get("quotation_date")) is None
        or start <= _as_date(r.get("quotation_date")) <= end
    ]
    df = pd.DataFrame(filtered or rows)
    if df.empty:
        st.info("No quotations in the selected scope.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True)
    _export_csv(df, "quotation_pipeline.csv")


def _render_retention_register(services: dict, start: date, end: date) -> None:
    report_svc = services.get("reports_projects")
    if report_svc is None:
        st.warning("Project reports service is not configured.")
        return
    project_id = _project_picker(services, "prj_rpt_retention_project")
    if not project_id:
        return
    try:
        rows = report_svc.retention_register(project_id)
    except Exception as exc:
        st.error(str(exc))
        return
    df = pd.DataFrame(rows)
    if df.empty:
        st.info("No retention entries.")
        return
    total_outstanding = sum(float(r.get("outstanding_retention") or 0) for r in rows)
    st.metric("Outstanding retention", f"₹{total_outstanding:,.0f}")
    st.dataframe(df, use_container_width=True, hide_index=True)
    _export_csv(df, f"retention_register_{project_id}.csv")
    st.caption(f"Period: {start:%d %b %Y} → {end:%d %b %Y}")


def _render_collections_outstanding(services: dict, start: date, end: date) -> None:
    report_svc = services.get("reports_projects")
    if report_svc is None:
        st.warning("Project reports service is not configured.")
        return
    project_id = _project_picker(services, "prj_rpt_collections_project")
    if not project_id:
        return
    try:
        payload = report_svc.collections_outstanding(project_id)
    except Exception as exc:
        st.error(str(exc))
        return
    metric_grid(
        [
            ("Customer outstanding", f"₹{float(payload.get('customer_outstanding') or 0):,.0f}"),
            ("Total receipts", f"₹{float(payload.get('total_receipts') or 0):,.0f}"),
        ],
        suffix="prj_rpt_collections",
    )
    st.caption(f"Period: {start:%d %b %Y} → {end:%d %b %Y}")


def _render_at_risk(services: dict, start: date, end: date) -> None:
    report_svc = services.get("reports_projects")
    if report_svc is None:
        st.warning("Project reports service is not configured.")
        return
    project_id = _optional_project_picker(services, "prj_rpt_at_risk")
    try:
        rows = report_svc.at_risk(project_id)
    except Exception as exc:
        st.error(str(exc))
        return
    if not rows:
        st.info("No at-risk projects.")
        return
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
    _export_csv(df, "at_risk_projects.csv")
    st.caption(f"Period: {start:%d %b %Y} → {end:%d %b %Y}")


def _render_variations_log(services: dict, start: date, end: date) -> None:
    report_svc = services.get("reports_projects")
    if report_svc is None:
        st.warning("Project reports service is not configured.")
        return
    project_id = _project_picker(services, "prj_rpt_variations_project")
    if not project_id:
        return
    try:
        rows = report_svc.variations_log(project_id)
    except Exception as exc:
        st.error(str(exc))
        return
    filtered = [
        r for r in rows
        if _as_date(r.get("variation_date")) is None
        or start <= _as_date(r.get("variation_date")) <= end
    ]
    df = pd.DataFrame(filtered or rows)
    if df.empty:
        st.info("No variations logged.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True)
    _export_csv(df, f"variations_{project_id}.csv")


def _render_cost_transfers(services: dict, start: date, end: date) -> None:
    report_svc = services.get("reports_projects")
    if report_svc is None:
        st.warning("Project reports service is not configured.")
        return
    project_id = _project_picker(services, "prj_rpt_transfers_project")
    if not project_id:
        return
    try:
        rows = report_svc.transfers(project_id)
    except Exception as exc:
        st.error(str(exc))
        return
    df = pd.DataFrame(rows)
    if df.empty:
        st.info("No cost transfers.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True)
    _export_csv(df, f"cost_transfers_{project_id}.csv")
    st.caption(f"Period: {start:%d %b %Y} → {end:%d %b %Y}")


def _render_write_offs(services: dict, start: date, end: date) -> None:
    report_svc = services.get("reports_projects")
    if report_svc is None:
        st.warning("Project reports service is not configured.")
        return
    project_id = _project_picker(services, "prj_rpt_writeoffs_project")
    if not project_id:
        return
    try:
        rows = report_svc.write_offs(project_id)
    except Exception as exc:
        st.error(str(exc))
        return
    df = pd.DataFrame(rows)
    if df.empty:
        st.info("No write-offs.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True)
    _export_csv(df, f"write_offs_{project_id}.csv")
    st.caption(f"Period: {start:%d %b %Y} → {end:%d %b %Y}")


def _render_po_committed(services: dict, start: date, end: date) -> None:
    report_svc = services.get("reports_projects")
    if report_svc is None:
        st.warning("Project reports service is not configured.")
        return
    project_id = _project_picker(services, "prj_rpt_po_committed_project")
    if not project_id:
        return
    try:
        rows = report_svc.po_committed(project_id)
    except Exception as exc:
        st.error(str(exc))
        return
    df = pd.DataFrame(rows)
    if df.empty:
        st.info("No open purchase orders tagged to this project.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True)
    total = sum(float(r.get("open_amount") or 0) for r in rows)
    st.metric("Committed cost", f"₹{total:,.0f}")
    _export_csv(df, f"po_committed_{project_id}.csv")
    st.caption(f"Period: {start:%d %b %Y} → {end:%d %b %Y}")


def _render_tds_deducted(services: dict, start: date, end: date) -> None:
    report_svc = services.get("reports_projects")
    if report_svc is None:
        st.warning("Project reports service is not configured.")
        return
    project_id = _project_picker(services, "prj_rpt_tds_project")
    if not project_id:
        return
    try:
        rows = report_svc.tds_deducted(project_id)
    except Exception as exc:
        st.error(str(exc))
        return
    filtered = [
        r for r in rows
        if _as_date(r.get("voucher_date")) is None
        or start <= _as_date(r.get("voucher_date")) <= end
    ]
    df = pd.DataFrame(filtered or rows)
    if df.empty:
        st.info("No TDS deductions recorded.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True)
    _export_csv(df, f"tds_deducted_{project_id}.csv")


def _render_document_inventory(services: dict, start: date, end: date) -> None:
    report_svc = services.get("reports_projects")
    if report_svc is None:
        st.warning("Project reports service is not configured.")
        return
    project_id = _project_picker(services, "prj_rpt_docs_project")
    if not project_id:
        return
    try:
        rows = report_svc.document_inventory(project_id)
    except Exception as exc:
        st.error(str(exc))
        return
    df = pd.DataFrame(rows)
    if df.empty:
        st.info("No documents on file.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True)
    _export_csv(df, f"document_inventory_{project_id}.csv")
    st.caption(f"Period: {start:%d %b %Y} → {end:%d %b %Y}")


def _render_boq_status(services: dict, start: date, end: date) -> None:
    report_svc = services.get("reports_projects")
    if report_svc is None:
        st.warning("Project reports service is not configured.")
        return
    project_id = _project_picker(services, "prj_rpt_boq_project")
    if not project_id:
        return
    try:
        rows = report_svc.boq_status_report(project_id)
    except Exception as exc:
        st.error(str(exc))
        return
    df = pd.DataFrame(rows)
    if df.empty:
        st.info("No BOQ items for this project.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True)
    _export_csv(df, f"boq_status_{project_id}.csv")


def _render_measurement_register(services: dict, start: date, end: date) -> None:
    report_svc = services.get("reports_projects")
    if report_svc is None:
        st.warning("Project reports service is not configured.")
        return
    project_id = _project_picker(services, "prj_rpt_meas_project")
    if not project_id:
        return
    try:
        rows = report_svc.measurement_register(project_id)
    except Exception as exc:
        st.error(str(exc))
        return
    filtered = [
        r for r in rows
        if _as_date(r.get("measurement_date")) is None
        or start <= _as_date(r.get("measurement_date")) <= end
    ]
    df = pd.DataFrame(filtered or rows)
    if df.empty:
        st.info("No measurements recorded.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True)
    _export_csv(df, f"measurement_register_{project_id}.csv")


def _render_ra_register_dual(services: dict, start: date, end: date) -> None:
    report_svc = services.get("reports_projects")
    if report_svc is None:
        st.warning("Project reports service is not configured.")
        return
    project_id = _project_picker(services, "prj_rpt_ra_dual_project")
    if not project_id:
        return
    try:
        rows = report_svc.ra_register_dual(project_id)
    except Exception as exc:
        st.error(str(exc))
        return
    filtered = [
        r for r in rows
        if _as_date(r.get("ra_date")) is None
        or start <= _as_date(r.get("ra_date")) <= end
    ]
    df = pd.DataFrame(filtered or rows)
    if df.empty:
        st.info("No RA bills for this project.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True)
    _export_csv(df, f"ra_register_{project_id}.csv")


def _render_budget_vs_actual(services: dict, start: date, end: date) -> None:
    report_svc = services.get("reports_projects")
    if report_svc is None:
        st.warning("Project reports service is not configured.")
        return
    project_id = _project_picker(services, "prj_rpt_budget_project")
    if not project_id:
        return
    try:
        payload = report_svc.budget_vs_actual(project_id)
    except Exception as exc:
        st.error(str(exc))
        return
    metric_grid(
        [
            ("Original", f"₹{float(payload.get('original_total') or 0):,.0f}"),
            ("Revised", f"₹{float(payload.get('revised_total') or 0):,.0f}"),
            ("Actual", f"₹{float(payload.get('actual') or 0):,.0f}"),
            ("Remaining", f"₹{float(payload.get('remaining') or 0):,.0f}"),
        ],
        suffix="prj_rpt_budget",
    )
    lines = payload.get("lines") or []
    if lines:
        st.dataframe(pd.DataFrame(lines), use_container_width=True, hide_index=True)
        _export_csv(pd.DataFrame(lines), f"budget_vs_actual_{project_id}.csv")
    st.caption(f"Period: {start:%d %b %Y} → {end:%d %b %Y}")


def render(services: dict) -> None:
    st.header("Project Reports")

    report_type = st.selectbox("Report", REPORT_TYPES, key="prj_report_type")
    start, end = _date_range_picker("prj_report")

    if report_type == "Portfolio Summary":
        _render_portfolio_summary(services, start, end)
    elif report_type == "Activity Profitability":
        _render_activity_profitability(services, start, end)
    elif report_type == "Man-hours by Worker":
        _render_man_hours_by_worker(services, start, end)
    elif report_type == "Unallocated Costs":
        _render_unallocated_costs(services, start, end)
    elif report_type == "WIP / Unbilled Cost":
        _render_wip_unbilled(services, start, end)
    elif report_type == "Billing Register":
        _render_billing_register(services, start, end)
    elif report_type == "Customer Outstanding":
        _render_customer_outstanding(services, start, end)
    elif report_type == "Vendor Payables":
        _render_vendor_payables(services, start, end)
    elif report_type == "Quotation Pipeline":
        _render_quotation_pipeline(services, start, end)
    elif report_type == "Retention Register":
        _render_retention_register(services, start, end)
    elif report_type == "Collections & Outstanding":
        _render_collections_outstanding(services, start, end)
    elif report_type == "At-Risk Projects":
        _render_at_risk(services, start, end)
    elif report_type == "Variations Log":
        _render_variations_log(services, start, end)
    elif report_type == "Cost Transfers":
        _render_cost_transfers(services, start, end)
    elif report_type == "Write-offs":
        _render_write_offs(services, start, end)
    elif report_type == "TDS Deducted":
        _render_tds_deducted(services, start, end)
    elif report_type == "PO Committed Cost":
        _render_po_committed(services, start, end)
    elif report_type == "Document Inventory":
        _render_document_inventory(services, start, end)
    elif report_type == "BOQ Status":
        _render_boq_status(services, start, end)
    elif report_type == "Measurement Register":
        _render_measurement_register(services, start, end)
    elif report_type == "RA Register (Claimed vs Certified)":
        _render_ra_register_dual(services, start, end)
    elif report_type == "Budget vs Actual":
        _render_budget_vs_actual(services, start, end)
