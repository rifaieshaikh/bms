"""Profit tab — profitability by activity."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from vaybooks.bms.ui.pages.projects.workspace import helpers as H
from vaybooks.bms.ui.styles import metric_grid


def render_profit(services: dict, project) -> None:
    profitability = services.get("projects_profitability")
    if profitability is None:
        st.warning("Profitability service is not configured.")
        return

    billing_svc = services.get("project_billing")
    if billing_svc is not None:
        try:
            wip = billing_svc.get_wip_balances(project.id)
            unbilled = float(wip.get("unbilled_cost") or 0.0)
            if unbilled > 0:
                st.warning(f"Unbilled cost on books: {H.fmt_money(unbilled)}")
        except Exception:
            pass

    try:
        summary = profitability.get_project_profitability(project.id)
    except Exception as exc:
        st.error(str(exc))
        return

    leaves = {a.id for a in H.leaf_activities(project)}
    missing_revenue = []
    for row in summary.activity_rows:
        if row.activity_id in leaves and row.total_cost > 0 and row.planned_revenue <= 0:
            missing_revenue.append(row.activity_name)
    if missing_revenue:
        st.warning(
            "Missing planned revenue for activities with cost: "
            + ", ".join(missing_revenue)
        )

    metrics = [
        ("Person-hours", H.fmt_hours(summary.person_hours)),
        ("Labour cost", H.fmt_money(summary.labour_cost)),
        ("Other cost", H.fmt_money(summary.other_cost)),
        ("Total cost", H.fmt_money(summary.total_cost)),
        ("Planned revenue", H.fmt_money(summary.planned_revenue)),
        ("Billed revenue", H.fmt_money(summary.billed_revenue)),
        ("Budget margin", H.fmt_money(summary.budget_margin)),
        ("Unallocated cost", H.fmt_money(summary.unallocated_cost)),
    ]
    if summary.billed_margin is not None:
        metrics.append(("Billed margin", H.fmt_money(summary.billed_margin)))
    if summary.billed_mph is not None:
        metrics.append(("Billed MPH", H.fmt_money(summary.billed_mph)))
    metric_grid(metrics, suffix="prj_profit_summary")

    if not summary.activity_rows:
        H.empty_state("No activity data yet.")
        return

    rows = []
    for row in summary.activity_rows:
        activity_row = {
            "Activity": row.activity_name,
            "Hours": row.person_hours,
            "Labour": row.labour_cost,
            "Other": row.other_cost,
            "Total cost": row.total_cost,
            "Planned rev.": row.planned_revenue,
            "Billed rev.": row.billed_revenue,
            "Budget margin": row.budget_margin,
        }
        if row.billed_margin is not None:
            activity_row["Billed margin"] = row.billed_margin
        if row.billed_mph is not None:
            activity_row["Billed MPH"] = row.billed_mph
        rows.append(activity_row)

    st.subheader("By activity")
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
