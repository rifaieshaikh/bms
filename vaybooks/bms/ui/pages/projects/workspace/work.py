"""Work tab — catalog-based activities grouped by phase."""

from __future__ import annotations

from typing import Optional

import pandas as pd
import streamlit as st

from vaybooks.bms.domain.shared.enums import ProjectBoqItemType
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler
from vaybooks.bms.ui.pages.projects.workspace import helpers as H

ADD_ACTIVITIES = "prj_work_add_activities_dialog"
ADD_PHASE = "prj_work_add_phase_dialog"
EDIT_PHASE = "prj_work_edit_phase_dialog"
EDIT_PHASE_ID = "prj_work_edit_phase_id"
REMOVE_PHASE = "prj_work_remove_phase_dialog"
REMOVE_PHASE_ID = "prj_work_remove_phase_id"
CHANGE_STATUS = "prj_work_change_status_dialog"
CHANGE_STATUS_ID = "prj_work_change_status_id"
EDIT_AMOUNT = "prj_work_edit_amount_dialog"
EDIT_AMOUNT_ID = "prj_work_edit_amount_id"
ASSIGN_PHASE = "prj_work_assign_phase_dialog"
ASSIGN_PHASE_ID = "prj_work_assign_phase_id"
REMOVE_ACTIVITY = "prj_work_remove_activity_dialog"
REMOVE_ACTIVITY_ID = "prj_work_remove_activity_id"


def _activity_statuses(services: dict, activity) -> list[str]:
    allowed = ["Created", "Completed"]
    config_svc = services.get("project_activity_configs")
    if activity.activity_config_id and config_svc:
        config = config_svc.get_activity(activity.activity_config_id)
        if config:
            allowed = list(config.statuses)
    return allowed


def _phase_sections(project) -> list[tuple[Optional[str], str]]:
    sections = [
        (phase.id, phase.name)
        for phase in sorted(project.phases, key=lambda p: p.sort_order)
    ]
    sections.append((None, "Unassigned"))
    return sections


def _activities_for_phase(project, phase_id: Optional[str]) -> list:
    activities = sorted(project.activities, key=lambda a: (a.sort_order, a.name))
    if phase_id is None:
        return [a for a in activities if not a.phase_id]
    return [a for a in activities if a.phase_id == phase_id]


def _phase_material_rows(services: dict, project, phase_id: Optional[str]) -> list[dict]:
    boq_svc = services.get("project_boq")
    if not boq_svc:
        return []
    try:
        items = boq_svc.list_items(project.id)
    except Exception:
        return []
    rows = []
    for item in items:
        if item.item_type != ProjectBoqItemType.ITEM:
            continue
        item_phase = getattr(item, "phase_id", None)
        if item_phase != phase_id:
            continue
        qty = item.estimated_qty or item.contracted_qty or 0.0
        rows.append(
            {
                "Code": item.code,
                "Description": item.description,
                "Unit": item.unit,
                "Qty": qty,
            }
        )
    return rows


@st.dialog("Add activities from catalog", width="large", on_dismiss=make_dismiss_handler(ADD_ACTIVITIES))
def _add_activities_dialog(services: dict, project) -> None:
    config_svc = services.get("project_activity_configs")
    projects_svc = services["projects"]
    if config_svc is None:
        st.error("Project activity catalog is not configured.")
        return

    try:
        catalog = config_svc.list_activities(active_only=True)
    except Exception as exc:
        st.error(str(exc))
        return

    existing_config_ids = {
        a.activity_config_id for a in project.activities if a.activity_config_id
    }
    available = [c for c in catalog if c.id not in existing_config_ids]
    if not catalog:
        st.info("No activities in the catalog. Add them under Settings → Project Activities.")
        return
    if not available:
        st.info("All catalog activities are already on this project.")
        return

    options = {c.activity_name: c.id for c in available}
    picked = st.multiselect(
        "Activities",
        options=list(options.keys()),
        key="prj_work_add_act_pick",
    )

    phase_id = None
    if project.phases:
        phase_map = {"— Unassigned —": None}
        phase_map.update({p.name: p.id for p in sorted(project.phases, key=lambda p: p.sort_order)})
        phase_label = st.selectbox(
            "Assign to phase",
            options=list(phase_map.keys()),
            key="prj_work_add_act_phase",
        )
        phase_id = phase_map[phase_label]

    cols = st.columns(2)
    if cols[0].button("Cancel", use_container_width=True):
        st.session_state.pop(ADD_ACTIVITIES, None)
        st.rerun()
    if cols[1].button("Add selected", type="primary", use_container_width=True):
        if not picked:
            st.error("Select at least one activity")
            return
        config_ids = [options[name] for name in picked]
        H.run_action(
            lambda: projects_svc.add_activities_from_catalog(
                project.id, config_ids, phase_id=phase_id
            ),
            "Activities added",
        )
        st.session_state.pop(ADD_ACTIVITIES, None)


@st.dialog("Add phase", on_dismiss=make_dismiss_handler(ADD_PHASE))
def _add_phase_dialog(services: dict, project) -> None:
    name = st.text_input("Phase name", key="prj_work_new_phase_name")
    cols = st.columns(2)
    if cols[0].button("Cancel", use_container_width=True):
        st.session_state.pop(ADD_PHASE, None)
        st.rerun()
    if cols[1].button("Add phase", type="primary", use_container_width=True):
        if not name.strip():
            st.error("Phase name is required")
            return
        H.run_action(
            lambda: services["projects"].add_phase(project.id, name),
            "Phase added",
        )
        st.session_state.pop(ADD_PHASE, None)


@st.dialog("Edit phase", on_dismiss=make_dismiss_handler(EDIT_PHASE, EDIT_PHASE_ID))
def _edit_phase_dialog(services: dict, project, phase_id: str) -> None:
    phase = next((p for p in project.phases if p.id == phase_id), None)
    if not phase:
        st.error("Phase not found")
        return
    name = st.text_input("Phase name", value=phase.name, key="prj_work_edit_phase_name")
    sort_order = st.number_input(
        "Sort order",
        min_value=0,
        value=int(phase.sort_order or 0),
        key="prj_work_edit_phase_order",
    )
    cols = st.columns(2)
    if cols[0].button("Cancel", use_container_width=True):
        st.session_state.pop(EDIT_PHASE, None)
        st.session_state.pop(EDIT_PHASE_ID, None)
        st.rerun()
    if cols[1].button("Save", type="primary", use_container_width=True):
        if not name.strip():
            st.error("Phase name is required")
            return
        H.run_action(
            lambda: services["projects"].update_phase(
                project.id, phase_id, name=name, sort_order=int(sort_order)
            ),
            "Phase updated",
        )
        st.session_state.pop(EDIT_PHASE, None)
        st.session_state.pop(EDIT_PHASE_ID, None)


@st.dialog("Remove phase", on_dismiss=make_dismiss_handler(REMOVE_PHASE, REMOVE_PHASE_ID))
def _remove_phase_dialog(services: dict, project, phase_id: str) -> None:
    phase = next((p for p in project.phases if p.id == phase_id), None)
    if not phase:
        st.error("Phase not found")
        return
    st.write(f"Remove phase **{phase.name}**? Activities in this phase become unassigned.")
    cols = st.columns(2)
    if cols[0].button("Cancel", use_container_width=True):
        st.session_state.pop(REMOVE_PHASE, None)
        st.session_state.pop(REMOVE_PHASE_ID, None)
        st.rerun()
    if cols[1].button("Remove", type="primary", use_container_width=True):
        H.run_action(
            lambda: services["projects"].delete_phase(project.id, phase_id),
            "Phase removed",
        )
        st.session_state.pop(REMOVE_PHASE, None)
        st.session_state.pop(REMOVE_PHASE_ID, None)


@st.dialog("Change status", on_dismiss=make_dismiss_handler(CHANGE_STATUS, CHANGE_STATUS_ID))
def _change_status_dialog(services: dict, project, activity_id: str) -> None:
    activity = next((a for a in project.activities if a.id == activity_id), None)
    if not activity:
        st.error("Activity not found")
        return
    statuses = _activity_statuses(services, activity)
    current = activity.current_status or statuses[0]
    try:
        idx = statuses.index(current)
    except ValueError:
        idx = 0
    new_status = st.selectbox(
        "Workflow status",
        options=statuses,
        index=idx,
        key="prj_work_status_pick",
    )
    st.caption("Flow: " + " → ".join(statuses))
    cols = st.columns(2)
    if cols[0].button("Cancel", use_container_width=True):
        st.session_state.pop(CHANGE_STATUS, None)
        st.session_state.pop(CHANGE_STATUS_ID, None)
        st.rerun()
    if cols[1].button("Save", type="primary", use_container_width=True):
        H.run_action(
            lambda: services["projects"].set_activity_workflow_status(
                project.id, activity_id, new_status
            ),
            "Status updated",
        )
        st.session_state.pop(CHANGE_STATUS, None)
        st.session_state.pop(CHANGE_STATUS_ID, None)


@st.dialog("Edit amount", on_dismiss=make_dismiss_handler(EDIT_AMOUNT, EDIT_AMOUNT_ID))
def _edit_amount_dialog(services: dict, project, activity_id: str) -> None:
    activity = next((a for a in project.activities if a.id == activity_id), None)
    if not activity:
        st.error("Activity not found")
        return
    amount = st.number_input(
        "Amount (₹)",
        min_value=0.0,
        value=float(activity.amount or activity.planned_revenue_amount or 0),
        step=100.0,
        key="prj_work_amount_input",
    )
    cols = st.columns(2)
    if cols[0].button("Cancel", use_container_width=True):
        st.session_state.pop(EDIT_AMOUNT, None)
        st.session_state.pop(EDIT_AMOUNT_ID, None)
        st.rerun()
    if cols[1].button("Save", type="primary", use_container_width=True):
        H.run_action(
            lambda: services["projects"].update_activity_amount(
                project.id, activity_id, amount
            ),
            "Amount updated",
        )
        st.session_state.pop(EDIT_AMOUNT, None)
        st.session_state.pop(EDIT_AMOUNT_ID, None)


@st.dialog("Assign phase", on_dismiss=make_dismiss_handler(ASSIGN_PHASE, ASSIGN_PHASE_ID))
def _assign_phase_dialog(services: dict, project, activity_id: str) -> None:
    activity = next((a for a in project.activities if a.id == activity_id), None)
    if not activity:
        st.error("Activity not found")
        return
    phase_map = {"— Unassigned —": None}
    phase_map.update({p.name: p.id for p in sorted(project.phases, key=lambda p: p.sort_order)})
    inv = {v: k for k, v in phase_map.items()}
    current = inv.get(activity.phase_id, "— Unassigned —")
    phase_names = list(phase_map.keys())
    phase_label = st.selectbox(
        "Phase",
        options=phase_names,
        index=phase_names.index(current) if current in phase_names else 0,
        key="prj_work_assign_phase_pick",
    )
    cols = st.columns(2)
    if cols[0].button("Cancel", use_container_width=True):
        st.session_state.pop(ASSIGN_PHASE, None)
        st.session_state.pop(ASSIGN_PHASE_ID, None)
        st.rerun()
    if cols[1].button("Save", type="primary", use_container_width=True):
        H.run_action(
            lambda: services["projects"].assign_activity_phase(
                project.id, activity_id, phase_map[phase_label]
            ),
            "Phase assigned",
        )
        st.session_state.pop(ASSIGN_PHASE, None)
        st.session_state.pop(ASSIGN_PHASE_ID, None)


@st.dialog("Remove activity", on_dismiss=make_dismiss_handler(REMOVE_ACTIVITY, REMOVE_ACTIVITY_ID))
def _remove_activity_dialog(services: dict, project, activity_id: str) -> None:
    activity = next((a for a in project.activities if a.id == activity_id), None)
    if not activity:
        st.error("Activity not found")
        return
    st.write(f"Remove **{activity.name}** from this project?")
    cols = st.columns(2)
    if cols[0].button("Cancel", use_container_width=True):
        st.session_state.pop(REMOVE_ACTIVITY, None)
        st.session_state.pop(REMOVE_ACTIVITY_ID, None)
        st.rerun()
    if cols[1].button("Remove", type="primary", use_container_width=True):
        time_repo = getattr(services.get("project_time"), "_time_repo", None)
        expense_repo = getattr(services.get("project_expenses"), "_expense_repo", None)
        H.run_action(
            lambda: services["projects"].delete_activity(
                project.id,
                activity_id,
                time_repo=time_repo,
                expense_repo=expense_repo,
            ),
            "Activity removed",
        )
        st.session_state.pop(REMOVE_ACTIVITY, None)
        st.session_state.pop(REMOVE_ACTIVITY_ID, None)


def _render_activity_card(services: dict, project, activity, index: int) -> None:
    with st.container(border=True):
        st.markdown(f"**{activity.name}**")
        category = activity.activity_category or "—"
        amount = float(activity.amount or activity.planned_revenue_amount or 0)
        st.caption(
            f"{category} · {activity.current_status or 'Created'} · "
            f"{H.fmt_money(amount)}"
        )

        btn_cols = st.columns(4)
        if btn_cols[0].button(
            "Change status",
            key=f"prj_work_stat_{activity.id}_{index}",
            use_container_width=True,
        ):
            st.session_state[CHANGE_STATUS] = True
            st.session_state[CHANGE_STATUS_ID] = activity.id
            st.rerun()
        if btn_cols[1].button(
            "Edit amount",
            key=f"prj_work_amt_{activity.id}_{index}",
            use_container_width=True,
        ):
            st.session_state[EDIT_AMOUNT] = True
            st.session_state[EDIT_AMOUNT_ID] = activity.id
            st.rerun()
        if btn_cols[2].button(
            "Assign phase",
            key=f"prj_work_phase_{activity.id}_{index}",
            use_container_width=True,
        ):
            st.session_state[ASSIGN_PHASE] = True
            st.session_state[ASSIGN_PHASE_ID] = activity.id
            st.rerun()
        if btn_cols[3].button(
            "Remove",
            key=f"prj_work_rm_{activity.id}_{index}",
            use_container_width=True,
        ):
            st.session_state[REMOVE_ACTIVITY] = True
            st.session_state[REMOVE_ACTIVITY_ID] = activity.id
            st.rerun()


def render_work(services: dict, project) -> None:
    projects = services["projects"]
    weighted = 0.0
    try:
        weighted = projects.get_weighted_progress(project.id)
    except Exception:
        pass
    st.caption(f"Weighted progress **{weighted:.1f}%**")

    if project.activities:
        st.subheader("Dependency / timeline")
        by_id = {a.id: a for a in project.activities}
        dep_rows = []
        for activity in sorted(project.activities, key=lambda a: (a.sort_order, a.name)):
            pred_names = [
                by_id[pid].name
                for pid in (activity.predecessor_ids or [])
                if pid in by_id
            ]
            dep_rows.append(
                {
                    "Activity": activity.name,
                    "Predecessors": ", ".join(pred_names) if pred_names else "—",
                    "% Complete": round(float(activity.percent_complete or 0), 1),
                    "Planned start": activity.planned_start or "",
                    "Planned end": activity.planned_end or "",
                    "Status": activity.current_status or "Created",
                }
            )
        st.dataframe(pd.DataFrame(dep_rows), use_container_width=True, hide_index=True)

    top_cols = st.columns([1, 1])
    if top_cols[0].button("Add activities", type="primary", key="prj_work_add_catalog"):
        st.session_state[ADD_ACTIVITIES] = True
        st.rerun()

    st.subheader("Phases")
    if not project.phases:
        st.caption("No phases yet — activities can stay unassigned.")
    else:
        for phase in sorted(project.phases, key=lambda p: p.sort_order):
            row = st.columns([3, 1, 1, 1])
            row[0].write(f"**{phase.name}** (order {phase.sort_order})")
            if row[1].button("Edit", key=f"prj_work_phase_edit_{phase.id}"):
                st.session_state[EDIT_PHASE] = True
                st.session_state[EDIT_PHASE_ID] = phase.id
                st.rerun()
            if row[2].button("Remove", key=f"prj_work_phase_rm_{phase.id}"):
                st.session_state[REMOVE_PHASE] = True
                st.session_state[REMOVE_PHASE_ID] = phase.id
                st.rerun()

    if top_cols[1].button("Add phase", key="prj_work_add_phase_btn"):
        st.session_state[ADD_PHASE] = True
        st.rerun()

    st.divider()

    if not project.activities:
        if H.empty_state(
            "No activities on this project yet. Add activities from the catalog.",
            cta="Add activities",
            cta_key="prj_work_empty_add",
        ):
            st.session_state[ADD_ACTIVITIES] = True
            st.rerun()
    else:
        for phase_id, phase_name in _phase_sections(project):
            phase_activities = _activities_for_phase(project, phase_id)
            if not phase_activities and phase_id is not None:
                continue
            st.markdown(f"### {phase_name}")
            if not phase_activities:
                st.caption("No activities in this section.")
            else:
                for i, activity in enumerate(phase_activities):
                    _render_activity_card(services, project, activity, i)

            material_rows = _phase_material_rows(services, project, phase_id)
            with st.expander("Phase materials", expanded=False):
                if material_rows:
                    st.dataframe(
                        pd.DataFrame(material_rows),
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.caption("No BOQ materials linked to this phase.")

    if st.session_state.get(ADD_ACTIVITIES):
        _add_activities_dialog(services, project)
    if st.session_state.get(ADD_PHASE):
        _add_phase_dialog(services, project)
    if st.session_state.get(EDIT_PHASE) and st.session_state.get(EDIT_PHASE_ID):
        _edit_phase_dialog(services, project, st.session_state[EDIT_PHASE_ID])
    if st.session_state.get(REMOVE_PHASE) and st.session_state.get(REMOVE_PHASE_ID):
        _remove_phase_dialog(services, project, st.session_state[REMOVE_PHASE_ID])
    if st.session_state.get(CHANGE_STATUS) and st.session_state.get(CHANGE_STATUS_ID):
        _change_status_dialog(services, project, st.session_state[CHANGE_STATUS_ID])
    if st.session_state.get(EDIT_AMOUNT) and st.session_state.get(EDIT_AMOUNT_ID):
        _edit_amount_dialog(services, project, st.session_state[EDIT_AMOUNT_ID])
    if st.session_state.get(ASSIGN_PHASE) and st.session_state.get(ASSIGN_PHASE_ID):
        _assign_phase_dialog(services, project, st.session_state[ASSIGN_PHASE_ID])
    if st.session_state.get(REMOVE_ACTIVITY) and st.session_state.get(REMOVE_ACTIVITY_ID):
        _remove_activity_dialog(services, project, st.session_state[REMOVE_ACTIVITY_ID])
