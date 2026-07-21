"""Budget tab — KPIs + dialog add/revise (Customization-style)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from vaybooks.bms.domain.shared.enums import ProjectCostCategory
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler
from vaybooks.bms.ui.pages.projects.workspace import helpers as H

BGT_ADD = "prj_budget_add_dialog"
BGT_REV = "prj_budget_rev_dialog"
BGT_REV_ID = "prj_budget_rev_id"


@st.dialog("Add budget line", width="large", on_dismiss=make_dismiss_handler(BGT_ADD))
def _add_budget_dialog(budget_svc, services, project) -> None:
    boq_svc = services.get("project_boq")
    boq_pick: dict[str, str | None] = {"— None —": None}
    if boq_svc:
        try:
            for item in boq_svc.list_items(project.id):
                if item.item_type.value == "Item":
                    boq_pick[f"{item.code} — {item.description}"] = item.id
        except Exception:
            pass
    act_pick = (
        H.activity_tree_options(project, include_blank=True)
        if project.activities
        else {"— None —": None}
    )

    category = st.selectbox(
        "Cost category",
        options=[c.value for c in ProjectCostCategory],
        key="prj_bgt_dlg_cat",
    )
    amount = st.number_input(
        "Amount", min_value=0.0, value=0.0, step=1000.0, key="prj_bgt_dlg_amt"
    )
    boq_label = st.selectbox(
        "BOQ item (optional)", options=list(boq_pick.keys()), key="prj_bgt_dlg_boq"
    )
    act_label = st.selectbox(
        "Activity (optional)", options=list(act_pick.keys()), key="prj_bgt_dlg_act"
    )
    notes = st.text_input("Notes", key="prj_bgt_dlg_notes")

    cols = st.columns(2)
    if cols[0].button("Cancel", use_container_width=True):
        st.session_state.pop(BGT_ADD, None)
        st.rerun()
    if cols[1].button("Add line", type="primary", use_container_width=True):
        H.run_action(
            lambda: budget_svc.add_line(
                project.id,
                category,
                amount,
                boq_item_id=boq_pick.get(boq_label) or "",
                activity_id=act_pick.get(act_label) or "",
                notes=notes,
            ),
            "Budget line added",
        )
        st.session_state.pop(BGT_ADD, None)


@st.dialog(
    "Revise budget line",
    width="medium",
    on_dismiss=make_dismiss_handler(BGT_REV, BGT_REV_ID),
)
def _revise_budget_dialog(budget_svc, line_id: str) -> None:
    project_id = st.session_state.get(H.WORKSPACE_ID)
    if not project_id:
        st.error("Project not found")
        return
    lines = budget_svc.list_lines(project_id)
    line = next((ln for ln in lines if ln.id == line_id), None)
    if not line:
        st.error("Budget line not found")
        return

    st.caption("Original amounts are fixed; only revised amounts can change.")
    st.write(f"Original (readonly): {H.fmt_money(line.original_amount)}")
    revised = st.number_input(
        "Revised amount",
        min_value=0.0,
        value=float(line.revised_amount or 0),
        step=1000.0,
        key="prj_bgt_rev_amt",
    )
    forecast_eac = st.number_input(
        "Forecast EAC",
        min_value=0.0,
        value=float(line.forecast_eac or 0),
        step=1000.0,
        key="prj_bgt_rev_eac",
    )
    forecast_etc = st.number_input(
        "Forecast ETC",
        min_value=0.0,
        value=float(line.forecast_etc or 0),
        step=1000.0,
        key="prj_bgt_rev_etc",
    )
    reason = st.text_input("Reason", value="Budget revision", key="prj_bgt_rev_reason")
    cols = st.columns(2)
    if cols[0].button("Cancel", use_container_width=True):
        st.session_state.pop(BGT_REV, None)
        st.session_state.pop(BGT_REV_ID, None)
        st.rerun()
    if cols[1].button("Save revision", type="primary", use_container_width=True):
        H.run_action(
            lambda: budget_svc.revise_line(
                line.id,
                revised,
                reason=reason,
                forecast_eac=forecast_eac,
                forecast_etc=forecast_etc,
            ),
            "Budget revised",
        )
        st.session_state.pop(BGT_REV, None)
        st.session_state.pop(BGT_REV_ID, None)


def render_budget(services: dict, project) -> None:
    budget_svc = services.get("project_budget")
    if budget_svc is None:
        st.warning("Budget service is not configured.")
        return

    try:
        summary = budget_svc.budget_summary(project.id)
        lines = budget_svc.list_lines(project.id)
    except Exception as exc:
        st.error(str(exc))
        return

    st.metric("Original budget", H.fmt_money(summary.get("original_total")))
    cols = st.columns(4)
    cols[0].metric("Revised budget", H.fmt_money(summary.get("revised_total")))
    cols[1].metric("Actual spend", H.fmt_money(summary.get("actual")))
    cols[2].metric("Committed (POs)", H.fmt_money(summary.get("committed")))
    cols[3].metric("Remaining", H.fmt_money(summary.get("remaining")))
    forecast_cols = st.columns(2)
    forecast_cols[0].metric("Forecast EAC", H.fmt_money(summary.get("forecast_eac")))
    forecast_cols[1].metric("Forecast ETC", H.fmt_money(summary.get("forecast_etc")))
    st.caption(
        f"Committed from budget summary: {H.fmt_money(summary.get('committed'))}"
    )

    if project.hard_budget_check:
        st.warning(
            "Hard budget check is enabled — expenses that would exceed the revised "
            "budget may be blocked."
        )
    else:
        st.caption(
            "Hard budget check is off. Enable it under Settings to block over-budget spend."
        )

    header = None
    if hasattr(budget_svc, "get_or_create_header"):
        try:
            header = budget_svc.get_or_create_header(project.id)
            st.caption(f"Budget status: **{header.status.value}**")
        except Exception:
            header = None
    status_cols = st.columns(3)
    if status_cols[0].button("Submit budget", key="prj_bgt_submit"):
        H.run_action(lambda: budget_svc.submit_budget(project.id), "Budget submitted")
    if status_cols[1].button("Approve budget", type="primary", key="prj_bgt_approve"):
        H.run_action(lambda: budget_svc.approve_budget(project.id), "Budget approved")

    if st.button("Add budget line", type="primary", key="prj_bgt_add_btn"):
        st.session_state[BGT_ADD] = True
        st.rerun()

    if lines:
        boq_svc = services.get("project_boq")
        boq_labels: dict[str, str] = {}
        if boq_svc:
            try:
                for item in boq_svc.list_items(project.id):
                    boq_labels[item.id] = f"{item.code} — {item.description}"
            except Exception:
                pass
        act_labels = {a.id: a.name for a in project.activities} if project.activities else {}

        reg_rows = []
        for line in lines:
            reg_rows.append(
                {
                    "id": line.id,
                    "category": line.cost_category.value,
                    "original": line.original_amount,
                    "revised": line.revised_amount,
                    "forecast_eac": line.forecast_eac,
                    "forecast_etc": line.forecast_etc,
                    "BOQ": boq_labels.get(line.boq_item_id, line.boq_item_id or "—"),
                    "activity": act_labels.get(line.activity_id, line.activity_id or "—"),
                    "notes": line.notes or "—",
                }
            )
        st.dataframe(
            pd.DataFrame([{k: v for k, v in r.items() if k != "id"} for r in reg_rows]),
            use_container_width=True,
            hide_index=True,
        )
        line_opts = {
            f"{r['category']} · {H.fmt_money(r['revised'])}": r["id"] for r in reg_rows
        }
        pick = st.selectbox("Line to revise", options=list(line_opts.keys()), key="prj_bgt_pick")
        if st.button("Revise selected", key="prj_bgt_rev_btn"):
            st.session_state[BGT_REV] = True
            st.session_state[BGT_REV_ID] = line_opts[pick]
            st.rerun()
    else:
        H.empty_state("No budget lines yet.")

    if st.session_state.get(BGT_ADD):
        _add_budget_dialog(budget_svc, services, project)
    if st.session_state.get(BGT_REV) and st.session_state.get(BGT_REV_ID):
        _revise_budget_dialog(budget_svc, st.session_state[BGT_REV_ID])
