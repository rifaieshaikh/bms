"""Projects portfolio dashboard — live metrics when profitability is wired."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.styles import metric_grid

DASH_VIEW_MODE = "projects_dashboard_view_mode"


def _fmt_currency(value: float) -> str:
    return f"₹{float(value or 0):,.0f}"


def _aggregate_portfolio(rows: list[dict]) -> dict:
    totals = {
        "projects": len(rows),
        "contract_value": 0.0,
        "total_cost": 0.0,
        "planned_revenue": 0.0,
        "billed_revenue": 0.0,
        "person_hours": 0.0,
        "unallocated_cost": 0.0,
        "unbilled_cost": 0.0,
    }
    for row in rows:
        totals["contract_value"] += float(row.get("contract_value") or 0)
        totals["total_cost"] += float(row.get("total_cost") or 0)
        totals["planned_revenue"] += float(row.get("planned_revenue") or 0)
        totals["billed_revenue"] += float(row.get("billed_revenue") or 0)
        totals["person_hours"] += float(row.get("person_hours") or 0)
        totals["unallocated_cost"] += float(row.get("unallocated_cost") or 0)
        totals["unbilled_cost"] += float(row.get("unbilled_cost") or 0)
    return totals


def _enrich_with_billing(services: dict, rows: list[dict]) -> list[dict]:
    billing_svc = services.get("project_billing")
    if billing_svc is None:
        return rows
    enriched = []
    for row in rows:
        copy = dict(row)
        project_id = copy.get("project_id")
        if not project_id:
            enriched.append(copy)
            continue
        try:
            wip = billing_svc.get_wip_balances(project_id)
            copy["unbilled_cost"] = wip.get("unbilled_cost", 0.0)
            copy["billed_revenue"] = wip.get("billed_revenue", copy.get("billed_revenue", 0.0))
        except Exception:
            pass
        try:
            party = billing_svc.get_party_balances(project_id)
            copy["customer_outstanding"] = party.get("customer_outstanding", 0.0)
            copy["books_match"] = billing_svc.books_match(project_id).get("books_match")
        except Exception:
            copy.setdefault("books_match", True)
        enriched.append(copy)
    return enriched


def _count_books_attention(rows: list[dict]) -> int:
    return sum(1 for row in rows if row.get("books_match") is False)


def _load_portfolio_rows(services: dict) -> tuple[list[dict], str]:
    profitability = services.get("projects_profitability")
    if profitability is not None:
        try:
            rows = profitability.portfolio_summary()
            return _enrich_with_billing(services, rows), "profitability"
        except Exception as exc:
            st.warning(f"Portfolio summary unavailable: {exc}")

    projects_svc = services.get("projects")
    if projects_svc is None:
        return [], "none"

    try:
        projects = projects_svc.list_projects()
    except Exception as exc:
        st.error(f"Could not load projects: {exc}")
        return [], "none"

    rows = [
        {
            "project_id": p.id,
            "project_number": p.project_number,
            "project_name": p.name,
            "customer_name": p.customer_name,
            "status": p.status.value if hasattr(p.status, "value") else str(p.status),
            "contract_value": p.contract_value,
            "person_hours": 0.0,
            "total_cost": 0.0,
            "planned_revenue": 0.0,
            "billed_revenue": 0.0,
            "unallocated_cost": 0.0,
            "unbilled_cost": 0.0,
        }
        for p in projects
    ]
    return _enrich_with_billing(services, rows), "projects"


def render(services: dict) -> None:
    st.header("Projects Dashboard")

    rows, source = _load_portfolio_rows(services)
    if not rows:
        st.info("No projects yet. Create one from the Projects list.")
        return

    totals = _aggregate_portfolio(rows)
    active = sum(1 for r in rows if r.get("status") in ("Active", "Draft", "On Hold"))
    books_attention = _count_books_attention(rows)

    view_mode = st.radio(
        "View",
        options=["Accrual", "Cash"],
        horizontal=True,
        key=DASH_VIEW_MODE,
    )

    revenue_label = "Billed revenue" if view_mode == "Accrual" else "Collected (est.)"
    if view_mode == "Accrual":
        revenue_value = totals["billed_revenue"]
        revenue_caption = "Recognized on invoices"
    else:
        revenue_value = sum(
            max(
                0.0,
                float(r.get("billed_revenue") or 0)
                - float(r.get("customer_outstanding") or 0),
            )
            for r in rows
        )
        revenue_caption = "Billed minus outstanding (portfolio estimate)"

    metric_grid(
        [
            ("Projects", totals["projects"]),
            ("Active / open", active),
            ("Contract value", _fmt_currency(totals["contract_value"])),
            ("Person-hours", f"{totals['person_hours']:,.1f}"),
            ("Total cost", _fmt_currency(totals["total_cost"])),
            ("Unbilled cost", _fmt_currency(totals["unbilled_cost"])),
            ("Books need attention", books_attention),
            (revenue_label, _fmt_currency(revenue_value)),
            ("Unallocated cost", _fmt_currency(totals["unallocated_cost"])),
        ],
        suffix="projects_dashboard",
    )

    st.caption(
        f"{view_mode} view — {revenue_caption}."
        if source == "profitability"
        else "Profitability metrics appear when the projects profitability service is available."
    )

    report_svc = services.get("reports_projects")
    if report_svc is not None:
        try:
            at_risk = report_svc.at_risk()
        except Exception as exc:
            st.warning(f"At-risk report unavailable: {exc}")
            at_risk = []
        if at_risk:
            with st.expander("At-risk projects", expanded=True):
                st.dataframe(at_risk, use_container_width=True, hide_index=True)

    quick_cols = st.columns(3)
    if quick_cols[0].button("View all projects", use_container_width=True):
        navigation.go_to_list("projects_list")
    if quick_cols[1].button("Project reports", use_container_width=True):
        navigation.go_to_list("projects_reports")
    if quick_cols[2].button("Create project", use_container_width=True):
        navigation.go_to_list("projects_list")

    with st.expander("Portfolio detail", expanded=False):
        st.dataframe(rows, use_container_width=True, hide_index=True)
