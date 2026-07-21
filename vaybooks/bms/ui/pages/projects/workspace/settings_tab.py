"""Settings tab — project identity, structure, billing, accounting."""

from __future__ import annotations

from datetime import date

import streamlit as st

from vaybooks.bms.domain.shared.enums import (
    PlaceOfSupplyMode,
    ProjectBillingMode,
    ProjectStatus,
    ProjectWbsNodeType,
)
from vaybooks.bms.domain.shared.india import INDIAN_STATES
from vaybooks.bms.ui.pages.projects.workspace import helpers as H


def render_settings(services: dict, project) -> None:
    billing_svc = services.get("project_billing")
    projects_svc = services["projects"]

    books_match = True
    if billing_svc is not None:
        try:
            books_match = bool(billing_svc.books_match(project.id).get("books_match"))
        except Exception:
            pass

    st.subheader("Contract baseline")
    st.caption(
        f"Contract approved: {'Yes' if project.contract_approved else 'No'}"
    )
    with st.form("prj_settings_contract"):
        original = float(project.original_contract_value or project.contract_value or 0)
        revised = float(
            project.revised_contract_value or project.contract_value or 0
        )
        if project.contract_approved:
            st.number_input(
                "Original contract value (readonly)",
                min_value=0.0,
                value=original,
                disabled=True,
            )
        else:
            original = st.number_input(
                "Original contract value",
                min_value=0.0,
                value=original,
                step=1000.0,
            )
        revised = st.number_input(
            "Revised contract value",
            min_value=0.0,
            value=revised,
            step=1000.0,
        )
        advance_terms = st.text_area(
            "Advance terms",
            value=project.advance_terms or "",
        )
        dlp_months = st.number_input(
            "DLP months",
            min_value=0,
            value=int(project.dlp_months or 0),
        )
        project_manager = st.text_input(
            "Project manager",
            value=project.project_manager or "",
        )
        consultant_name = st.text_input(
            "Consultant name",
            value=project.consultant_name or "",
        )
        owner_name = st.text_input(
            "Owner name",
            value=project.owner_name or "",
        )
        hard_budget_check = st.checkbox(
            "Hard budget check",
            value=bool(project.hard_budget_check),
        )
        save_contract = st.form_submit_button("Save contract settings", type="primary")

    if save_contract:
        def _save_contract():
            kwargs = dict(
                advance_terms=advance_terms,
                dlp_months=int(dlp_months),
                project_manager=project_manager,
                consultant_name=consultant_name,
                owner_name=owner_name,
                hard_budget_check=hard_budget_check,
                revised_contract_value=revised,
            )
            if not project.contract_approved:
                kwargs["original_contract_value"] = original
            projects_svc.update_project_settings(project.id, **kwargs)

        H.run_action(_save_contract, "Contract settings saved")

    st.subheader("Accounting")
    lock_cols = st.columns(3)
    lock_cols[0].caption(
        f"Billing period: {'Locked' if project.period_locked else 'Open'}"
    )
    if lock_cols[1].button("Lock period", key="prj_lock_period", use_container_width=True):
        H.run_action(
            lambda: projects_svc.lock_period(project.id),
            "Billing period locked",
        )
    if lock_cols[2].button("Unlock period", key="prj_unlock_period", use_container_width=True):
        H.run_action(
            lambda: projects_svc.unlock_period(project.id),
            "Billing period unlocked",
        )

    gst_policies = ["", "Proportional", "Full on advance", "None"]
    current_gst = project.advance_gst_policy or ""
    if current_gst and current_gst not in gst_policies:
        gst_policies.append(current_gst)

    state_labels = [f"{s['code']} — {s['name']}" for s in INDIAN_STATES]
    code_by_label = {label: s["code"] for label, s in zip(state_labels, INDIAN_STATES)}
    label_by_code = {s["code"]: label for label, s in zip(state_labels, INDIAN_STATES)}
    current_label = label_by_code.get(project.site_state_code, "")

    with st.form("prj_settings_identity"):
        st.markdown("**Identity**")
        name = st.text_input("Project name", value=project.name)
        site_address = st.text_area("Site address", value=project.site_address)
        site_state_label = st.selectbox(
            "Site state",
            options=[""] + state_labels,
            index=(state_labels.index(current_label) + 1) if current_label in state_labels else 0,
        )
        notes = st.text_area("Notes", value=project.notes)
        start_date = st.date_input("Start date", value=project.start_date or date.today())
        expected_end = st.date_input(
            "Expected end date",
            value=project.expected_end_date or date.today(),
        )
        status = st.selectbox(
            "Status",
            options=[s.value for s in ProjectStatus],
            index=[s.value for s in ProjectStatus].index(project.status.value),
        )
        save_identity = st.form_submit_button("Save identity", type="primary")

    if save_identity:
        H.run_action(
            lambda: projects_svc.update_project_settings(
                project.id,
                name=name,
                site_address=site_address,
                site_state_code=code_by_label.get(site_state_label, ""),
                notes=notes,
                start_date=start_date,
                expected_end_date=expected_end,
                status=ProjectStatus(status),
            ),
            "Identity saved",
        )

    with st.form("prj_settings_structure"):
        st.markdown("**Structure**")
        phases_enabled = st.checkbox("Phases enabled", value=project.phases_enabled)
        max_activity_depth = st.number_input(
            "Max activity depth",
            min_value=1,
            max_value=10,
            value=int(project.max_activity_depth or 3),
        )
        save_structure = st.form_submit_button("Save structure", type="primary")

    if save_structure:
        H.run_action(
            lambda: projects_svc.update_project_settings(
                project.id,
                phases_enabled=phases_enabled,
                max_activity_depth=int(max_activity_depth),
            ),
            "Structure saved",
        )

    quality = services.get("project_quality_config")
    if quality is not None:
        st.markdown("**WBS structure**")
        st.caption("Build the work-breakdown hierarchy used for cost and progress dimensions.")
        try:
            wbs_nodes = quality.list_wbs_nodes(project.id)
        except Exception:
            wbs_nodes = []
        if wbs_nodes:
            st.dataframe(
                [
                    {
                        "Code": n.code or "—",
                        "Name": n.name,
                        "Type": getattr(n.node_type, "value", n.node_type),
                        "Parent": next(
                            (p.name for p in wbs_nodes if p.id == n.parent_id),
                            "—",
                        ),
                        "Manager": n.manager or "—",
                    }
                    for n in sorted(wbs_nodes, key=lambda x: (x.sort_order, x.name))
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption("No WBS nodes yet.")
        parent_opts = {"— Root —": None}
        for n in wbs_nodes:
            parent_opts[f"{n.code + ' — ' if n.code else ''}{n.name}"] = n.id
        with st.form("prj_settings_wbs_add"):
            wbs_name = st.text_input("Node name", key="prj_wbs_name")
            wbs_code = st.text_input("Code", key="prj_wbs_code")
            wbs_type = st.selectbox(
                "Node type",
                options=[t.value for t in ProjectWbsNodeType],
                key="prj_wbs_type",
            )
            wbs_parent_label = st.selectbox(
                "Parent",
                options=list(parent_opts.keys()),
                key="prj_wbs_parent",
            )
            wbs_manager = st.text_input("Manager", key="prj_wbs_manager")
            wbs_sort = st.number_input(
                "Sort order", min_value=0, value=len(wbs_nodes), key="prj_wbs_sort"
            )
            add_wbs = st.form_submit_button("Add WBS node", type="primary")
        if add_wbs:
            H.run_action(
                lambda: quality.add_wbs_node(
                    project.id,
                    wbs_name,
                    ProjectWbsNodeType(wbs_type),
                    code=wbs_code,
                    parent_id=parent_opts.get(wbs_parent_label),
                    manager=wbs_manager,
                    sort_order=int(wbs_sort or 0),
                ),
                "WBS node added",
            )

    with st.form("prj_settings_billing"):
        st.markdown("**Billing**")
        contract_value = st.number_input(
            "Contract value",
            min_value=0.0,
            value=float(project.contract_value),
            step=1000.0,
        )
        billing_mode = st.selectbox(
            "Billing mode",
            options=[m.value for m in ProjectBillingMode],
            index=[m.value for m in ProjectBillingMode].index(project.billing_mode.value),
        )
        retention_pct = st.number_input(
            "Retention %",
            min_value=0.0,
            max_value=100.0,
            value=float(project.retention_pct),
        )
        overhead_allocation_pct = st.number_input(
            "Overhead allocation %",
            min_value=0.0,
            max_value=100.0,
            value=float(project.overhead_allocation_pct or 0.0),
        )
        currency_code = st.text_input(
            "Currency code",
            value=(getattr(project, "currency_code", None) or "INR"),
            max_chars=3,
            help="ISO currency; multi-currency rates are stubbed (default INR).",
        )
        advance_gst_policy = st.selectbox(
            "Advance GST policy",
            options=gst_policies,
            index=gst_policies.index(current_gst) if current_gst in gst_policies else 0,
        )
        default_rate = st.number_input(
            "Default hourly rate",
            min_value=0.0,
            value=float(project.default_hourly_rate),
        )
        pos_mode = st.selectbox(
            "Place of supply",
            options=[m.value for m in PlaceOfSupplyMode],
            index=[m.value for m in PlaceOfSupplyMode].index(
                project.place_of_supply_mode.value
            ),
        )
        save_billing = st.form_submit_button("Save billing", type="primary")

    if save_billing:
        H.run_action(
            lambda: projects_svc.update_project_settings(
                project.id,
                contract_value=contract_value,
                billing_mode=ProjectBillingMode(billing_mode),
                retention_pct=retention_pct,
                default_hourly_rate=default_rate,
                place_of_supply_mode=PlaceOfSupplyMode(pos_mode),
                overhead_allocation_pct=overhead_allocation_pct,
                currency_code=currency_code,
                advance_gst_policy=advance_gst_policy,
            ),
            "Billing settings saved",
        )

    st.markdown("**Closure actions**")
    closure_cols = st.columns(3)
    if closure_cols[0].button("Mark physically completed", key="prj_set_phys_complete"):
        H.run_action(
            lambda: projects_svc.mark_physically_completed(project.id),
            "Marked physically completed",
        )
    if closure_cols[1].button("Mark DLP", key="prj_set_dlp"):
        H.run_action(
            lambda: projects_svc.mark_dlp(project.id),
            "Entered DLP",
        )
    force_close = st.checkbox(
        "Force close (ignore books mismatch)",
        value=False,
        disabled=books_match,
        help="Required when customer, vendor, or WIP balances are unsettled.",
        key="prj_settings_force_close",
    )
    if closure_cols[2].button("Financial close", type="primary", key="prj_close_project"):
        H.run_action(
            lambda: projects_svc.close_project(
                project.id,
                force=force_close,
                billing_service=billing_svc,
                measurement_service=services.get("project_measurement"),
            ),
            "Project financially closed",
        )

    st.markdown("**Reopen / configuration**")
    reopen_reason = st.text_input("Reopen reason", key="prj_reopen_reason")
    if st.button("Reopen closed project", key="prj_reopen_btn"):
        H.run_action(
            lambda: projects_svc.reopen_project(project.id, reopen_reason),
            "Project reopened",
        )
    if quality is not None:
        arch = st.selectbox(
            "Archetype",
            options=[
                "Structural",
                "Full Construction",
                "Architectural",
                "Interior",
                "Truss",
                "Aluminium Fabrication",
                "Custom",
            ],
            key="prj_cfg_arch",
        )
        scale = st.selectbox(
            "Scale", options=["Small", "Medium", "Large"], key="prj_cfg_scale"
        )
        if st.button("Publish config snapshot", key="prj_cfg_publish"):
            H.run_action(
                lambda: quality.publish_config_snapshot(
                    project.id,
                    archetype=arch,
                    scale=scale,
                    change_reason="Manual publish from settings",
                ),
                "Configuration snapshot published",
            )
        try:
            snaps = quality.list_config_snapshots(project.id)
        except Exception:
            snaps = []
        if snaps:
            st.caption("Published configuration revisions (immutable)")
            st.dataframe(
                [
                    {
                        "Rev": s.revision,
                        "Archetype": getattr(s.archetype, "value", s.archetype),
                        "Scale": getattr(s.scale, "value", s.scale),
                        "Modules": ", ".join(s.modules or []),
                        "Reason": s.change_reason or "—",
                    }
                    for s in sorted(snaps, key=lambda x: x.revision, reverse=True)
                ],
                use_container_width=True,
                hide_index=True,
            )
        hybrid_phase = st.text_input(
            "Add hybrid phase package", key="prj_hybrid_phase"
        )
        if snaps and st.button("Compose hybrid from latest", key="prj_hybrid_btn"):
            latest = max(snaps, key=lambda x: x.revision)
            H.run_action(
                lambda: quality.compose_hybrid(
                    project.id,
                    latest.id,
                    [hybrid_phase] if hybrid_phase.strip() else [],
                ),
                "Hybrid configuration composed",
            )
