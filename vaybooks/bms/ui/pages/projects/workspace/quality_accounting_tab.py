"""Quality, accounting (WIP/reconcile), and related project workspace tabs."""

from __future__ import annotations

from datetime import date

import streamlit as st

from vaybooks.bms.domain.shared.enums import ProjectRecognitionMethod
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler
from vaybooks.bms.ui.pages.projects.workspace import helpers as H

QI_DIALOG = "prj_qi_add_dialog"
DPR_DIALOG = "prj_dpr_add_dialog"


@st.dialog("New quality issue", on_dismiss=make_dismiss_handler(QI_DIALOG))
def _qi_dialog(services: dict, project) -> None:
    title = st.text_input("Title", key="prj_qi_title")
    issue_type = st.selectbox(
        "Type", options=["Snag", "Rework", "NCR"], key="prj_qi_type"
    )
    description = st.text_area("Description", key="prj_qi_desc")
    cost_impact = st.number_input(
        "Cost impact (₹)", min_value=0.0, value=0.0, key="prj_qi_cost"
    )
    is_rework = st.checkbox(
        "Tag as rework cost",
        value=issue_type == "Rework",
        key="prj_qi_rework_cost",
    )
    cols = st.columns(2)
    if cols[0].button("Cancel", use_container_width=True):
        st.session_state.pop(QI_DIALOG, None)
        st.rerun()
    if cols[1].button("Create", type="primary", use_container_width=True):
        try:
            services["project_quality_config"].create_quality_issue(
                project.id,
                title,
                issue_type=issue_type,
                description=description or "",
                cost_impact=cost_impact,
                is_rework_cost=is_rework,
            )
            st.session_state.pop(QI_DIALOG, None)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


@st.dialog("Submit DPR", width="large", on_dismiss=make_dismiss_handler(DPR_DIALOG))
def _dpr_dialog(services: dict, project) -> None:
    report_date = st.date_input("Date", value=date.today(), key="prj_dpr_date")
    weather = st.text_input("Weather", key="prj_dpr_weather")
    notes = st.text_area("Notes", key="prj_dpr_notes")
    photo_ids_raw = st.text_input(
        "Photo document IDs (comma-separated)", key="prj_dpr_photos"
    )
    activity_options = {a.name: a.id for a in project.activities}
    activity_name = st.selectbox(
        "Activity", options=[""] + list(activity_options.keys()), key="prj_dpr_act"
    )
    hours = st.number_input("Hours", min_value=0.0, value=0.0, key="prj_dpr_hours")
    cols = st.columns(2)
    if cols[0].button("Cancel", use_container_width=True):
        st.session_state.pop(DPR_DIALOG, None)
        st.rerun()
    if cols[1].button("Create", type="primary", use_container_width=True):
        lines = []
        if activity_name:
            lines.append(
                {"activity_id": activity_options[activity_name], "hours": hours}
            )
        photo_ids = [
            p.strip() for p in (photo_ids_raw or "").split(",") if p.strip()
        ]
        try:
            dpr = services["project_dpr"].create_dpr(
                project.id,
                report_date,
                weather=weather,
                notes=notes,
                lines=lines,
                photo_document_ids=photo_ids,
            )
            services["project_dpr"].submit(dpr.id)
            st.session_state.pop(DPR_DIALOG, None)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def render_quality(services: dict, project) -> None:
    svc = services.get("project_quality_config")
    if svc is None:
        st.warning("Quality service is not configured.")
        return
    if st.button("New issue", key="prj_qi_new"):
        st.session_state[QI_DIALOG] = True
    if st.session_state.get(QI_DIALOG):
        _qi_dialog(services, project)
    issues = svc.list_quality_issues(project.id)
    if not issues:
        H.empty_state("No quality issues.")
    for issue in issues:
        rework = " · rework cost" if getattr(issue, "is_rework_cost", False) else ""
        cost = (
            f" · {H.fmt_money(issue.cost_impact)}"
            if float(issue.cost_impact or 0) > 0
            else ""
        )
        st.write(
            f"**{issue.title}** · {issue.issue_type.value} · {issue.status.value}"
            f"{cost}{rework}"
        )


def render_accounting(services: dict, project) -> None:
    recog = services.get("project_recognition")
    petty = services.get("project_petty_cash")
    billing = services.get("project_billing")
    profitability = services.get("projects_profitability")
    if recog is None:
        st.warning("Recognition service is not configured.")
        return
    st.subheader("Revenue recognition / WIP")
    method = st.selectbox(
        "Method",
        options=[m.value for m in ProjectRecognitionMethod],
        key="prj_recog_method",
    )
    period_end = st.date_input("Period end", value=date.today(), key="prj_recog_period")
    pct = st.number_input("% complete", min_value=0.0, max_value=100.0, value=0.0)
    cost = st.number_input("Total cost", min_value=0.0, value=0.0)
    billed = st.number_input("Billed to date", min_value=0.0, value=0.0)
    if st.button("Draft recognition", key="prj_recog_draft"):
        try:
            entry = recog.draft_recognition(
                project.id,
                period_end,
                method,
                percent_complete=pct,
                total_cost=cost,
                billed_to_date=billed,
            )
            st.success(
                f"Draft recognised {H.fmt_money(entry.current_recognised)} "
                f"(WIP adj {H.fmt_money(entry.wip_adjustment)})"
            )
        except Exception as exc:
            st.error(str(exc))
    for entry in recog.list_entries(project.id):
        stub_note = ""
        if entry.journal_stub:
            via = entry.journal_stub.get("posted_via", "stub")
            stub_note = f" · journal={via}"
        st.caption(
            f"{entry.period_end} · {entry.method.value} · {entry.status.value} · "
            f"{H.fmt_money(entry.current_recognised)}{stub_note}"
        )
        if entry.status.value == "Approved":
            if st.button("Post", key=f"prj_recog_post_{entry.id}"):
                H.run_action(lambda e=entry: recog.post(e.id), "Recognition posted")

    if st.button("Allocate overhead", key="prj_overhead_alloc"):
        try:
            result = recog.allocate_overhead(project.id)
            st.success(
                f"Overhead {H.fmt_money(result.get('amount', 0))} "
                f"({result.get('overhead_allocation_pct', 0)}% of "
                f"{H.fmt_money(result.get('base_cost', 0))})"
            )
        except Exception as exc:
            st.error(str(exc))

    st.subheader("Reconciliation (UC-044)")
    as_of = st.date_input("As of", value=date.today(), key="prj_recon_as_of")
    c1, c2 = st.columns(2)
    subledger = c1.number_input("Project subledger", value=0.0, key="prj_recon_sub")
    gl_balance = c2.number_input("GL balance", value=0.0, key="prj_recon_gl")
    c3, c4 = st.columns(2)
    ar_balance = c3.number_input("AR balance", value=0.0, key="prj_recon_ar")
    ap_balance = c4.number_input("AP balance", value=0.0, key="prj_recon_ap")
    if st.button("Create reconciliation", key="prj_recon_create"):
        try:
            recon = recog.create_reconciliation(
                project.id,
                as_of,
                project_subledger=subledger,
                gl_balance=gl_balance,
                ar_balance=ar_balance,
                ap_balance=ap_balance,
            )
            st.success(f"Reconciliation saved ({recon.id[:8]}…)")
        except Exception as exc:
            st.error(str(exc))

    match_source = None
    match_result = None
    if billing is not None:
        try:
            match_result = billing.books_match(project.id)
            match_source = "billing"
        except Exception:
            match_result = None
    if match_result is None and profitability is not None:
        try:
            match_result = profitability.books_match_check(project.id)
            match_source = "profitability"
        except Exception:
            match_result = None
    if match_result is not None:
        all_match = match_result.get("books_match", match_result.get("all_match"))
        st.caption(
            f"Books match ({match_source}): "
            f"{'✓ matched' if all_match else '✗ attention needed'}"
        )
        for check in match_result.get("checks") or []:
            name = check.get("name") or check.get("label") or "Check"
            ok = check.get("match", check.get("ok", True))
            pv = check.get("project_value", check.get("project", ""))
            bv = check.get("books_value", check.get("books", ""))
            st.caption(
                f"{'✓' if ok else '✗'} {name} — project={pv} · books={bv}"
            )

    for recon in recog.list_reconciliations(project.id):
        delta = round(
            float(recon.project_subledger or 0) - float(recon.gl_balance or 0), 2
        )
        st.write(
            f"**{recon.as_of}** · {recon.status.value} · "
            f"subledger {H.fmt_money(recon.project_subledger)} · "
            f"GL {H.fmt_money(recon.gl_balance)} · Δ {H.fmt_money(delta)}"
        )
        for exc in recon.exceptions or []:
            st.caption(
                f"  ↳ {exc.category}: {exc.description} "
                f"({H.fmt_money(exc.amount)}) [{exc.source_ref}]"
            )

    st.subheader("Petty cash")
    if petty is None:
        st.caption("Petty cash unavailable.")
        return
    for advance in petty.list_advances(project.id):
        st.write(
            f"**{advance.advance_number}** · {advance.custodian} · "
            f"{H.fmt_money(advance.amount)} · {advance.status.value}"
        )


def render_dpr_section(services: dict, project) -> None:
    if st.button("Submit DPR", key="prj_dpr_btn"):
        st.session_state[DPR_DIALOG] = True
    if st.session_state.get(DPR_DIALOG):
        _dpr_dialog(services, project)
    dpr_svc = services.get("project_dpr")
    if dpr_svc is None:
        return
    for dpr in dpr_svc.list_dprs(project.id)[:10]:
        photos = len(getattr(dpr, "photo_document_ids", None) or [])
        photo_note = f" · {photos} photo(s)" if photos else ""
        cols = st.columns([4, 1])
        cols[0].caption(
            f"DPR {dpr.report_date} · {dpr.status.value} · applied={dpr.applied}"
            f"{photo_note}"
        )
        if not dpr.applied and dpr.status.value in ("Submitted", "Draft"):
            if cols[1].button("Approve", key=f"prj_dpr_approve_{dpr.id}"):
                H.run_action(
                    lambda d=dpr: dpr_svc.approve_and_apply(d.id),
                    "DPR approved",
                )
