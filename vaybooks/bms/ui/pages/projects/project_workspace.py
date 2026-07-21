"""Project workspace — order-detail style: header panel + st.tabs."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.pages.projects.workspace import helpers as H
from vaybooks.bms.ui.pages.projects.workspace.billing_tab import render_billing
from vaybooks.bms.ui.pages.projects.workspace.boq_tab import render_boq
from vaybooks.bms.ui.pages.projects.workspace.budget_tab import render_budget
from vaybooks.bms.ui.pages.projects.workspace.costs_tab import render_costs
from vaybooks.bms.ui.pages.projects.session_user import ensure_default_session_user
from vaybooks.bms.ui.pages.projects.workspace.documents_tab import render_documents
from vaybooks.bms.ui.pages.projects.workspace.history_tab import render_history
from vaybooks.bms.ui.pages.projects.workspace.money_tab import render_money
from vaybooks.bms.ui.pages.projects.workspace.overview_tab import render_overview
from vaybooks.bms.ui.pages.projects.workspace.procurement_tab import render_procurement
from vaybooks.bms.ui.pages.projects.workspace.profit_tab import render_profit
from vaybooks.bms.ui.pages.projects.workspace.quality_accounting_tab import (
    render_accounting,
    render_dpr_section,
    render_quality,
)
from vaybooks.bms.ui.pages.projects.workspace.settings_tab import render_settings
from vaybooks.bms.ui.pages.projects.workspace.time_tab import render_time
from vaybooks.bms.ui.pages.projects.workspace.work import render_work
from vaybooks.bms.ui.styles import panel, status_badge


def _resolve_project_id() -> str | None:
    param_id = navigation.consume_list_param("project_workspace", "project")
    if param_id:
        st.session_state[H.WORKSPACE_ID] = param_id
    detail_id = navigation.current_detail_id("project_detail")
    if detail_id:
        st.session_state[H.WORKSPACE_ID] = detail_id
    return st.session_state.get(H.WORKSPACE_ID)


def _load_project(services: dict, project_id: str):
    try:
        return services["projects"].get_project(project_id)
    except Exception:
        return None


def render(services: dict) -> None:
    ensure_default_session_user(services)
    project_id = _resolve_project_id()
    if not project_id:
        st.warning("No project selected.")
        if st.button("← Back to projects", key="prj_ws_back_empty"):
            navigation.go_to_list("projects_list")
        return

    project = _load_project(services, project_id)
    if not project:
        st.error("Project not found.")
        st.session_state.pop(H.WORKSPACE_ID, None)
        if st.button("← Back to projects", key="prj_ws_back_missing"):
            navigation.go_to_list("projects_list")
        return

    if st.button("← Back to projects", key="prj_ws_back"):
        navigation.go_back_to_list("projects", "projects_list")
        return

    st.title(project.project_number)

    with panel(f"prj_head_{project.id}"):
        with st.container(border=True):
            head = st.columns([2, 3])
            with head[0]:
                st.caption("Status")
                st.markdown(
                    status_badge(project.status.value), unsafe_allow_html=True
                )
            with head[1]:
                st.markdown(f"**{project.name}**")
                st.caption(f"{project.customer_name}")
                contract = float(
                    project.revised_contract_value
                    or project.contract_value
                    or 0
                )
                st.caption(f"Contract ₹{contract:,.0f}")
            if getattr(project, "enquiry_id", ""):
                st.caption(f"Enquiry: {project.enquiry_id[:12]}…")
            if project.site_address or project.site_state_code:
                site_bits = [b for b in (project.site_address, project.site_state_code) if b]
                st.caption("Site: " + " · ".join(site_bits))
            if project.notes:
                st.caption(f"Notes: {project.notes}")

    (
        tab_overview,
        tab_work,
        tab_boq,
        tab_budget,
        tab_time,
        tab_costs,
        tab_procure,
        tab_billing,
        tab_money,
        tab_quality,
        tab_docs,
        tab_profit,
        tab_accounting,
        tab_history,
        tab_settings,
    ) = st.tabs(
        [
            "Overview",
            "Work",
            "BOQ",
            "Budget",
            "Time",
            "Costs",
            "Procurement",
            "Billing",
            "Money",
            "Quality",
            "Documents",
            "Profit",
            "Accounting",
            "History",
            "Settings",
        ]
    )

    with tab_overview:
        render_overview(services, project)
        render_dpr_section(services, project)
    with tab_work:
        render_work(services, project)
    with tab_boq:
        render_boq(services, project)
    with tab_budget:
        render_budget(services, project)
    with tab_time:
        render_time(services, project)
    with tab_costs:
        render_costs(services, project)
    with tab_procure:
        render_procurement(services, project)
    with tab_billing:
        render_billing(services, project)
    with tab_money:
        render_money(services, project)
    with tab_quality:
        render_quality(services, project)
    with tab_docs:
        render_documents(services, project)
    with tab_profit:
        render_profit(services, project)
    with tab_accounting:
        render_accounting(services, project)
    with tab_history:
        render_history(services, project)
    with tab_settings:
        render_settings(services, project)
