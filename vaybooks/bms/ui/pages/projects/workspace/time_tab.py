"""Time tab — log time and register."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from vaybooks.bms.domain.projects.services import ProjectDomainService
from vaybooks.bms.ui.pages.projects.workspace import helpers as H

_DOMAIN = ProjectDomainService()


def _load_workers(services: dict) -> dict[str, dict]:
    try:
        workers = services["workers"].list_workers(active_only=True)
    except Exception:
        workers = []
    return {
        w.id: {"id": w.id, "name": w.worker_name, "rate": float(w.default_hourly_rate or 0)}
        for w in workers
    }


def _resolve_rate(project, activity_id: str, worker: dict | None, rate_override: float) -> float:
    activity = next((a for a in project.activities if a.id == activity_id), None)
    return _DOMAIN.resolve_hourly_rate(
        entry_override=rate_override if rate_override > 0 else None,
        activity=activity,
        worker_rate=float(worker["rate"]) if worker else 0.0,
        project=project,
    )


def render_time(services: dict, project) -> None:
    time_svc = services.get("project_time")
    if time_svc is None:
        st.warning("Time service is not configured.")
        return

    leaves = H.leaf_activities(project)
    act_opts = H.activity_tree_options(project, leaves_only=True)
    workers_by_id = _load_workers(services)

    st.subheader("Log time")
    if not act_opts:
        H.empty_state("Add leaf activities before logging time.")
    elif not workers_by_id:
        H.empty_state("Add workers before logging time.")
    else:
        work_date = st.date_input("Date", value=date.today(), key="prj_time_date")
        act_labels = list(act_opts.keys())
        activity_label = st.selectbox("Activity", options=act_labels, key="prj_time_activity")
        activity_id = act_opts[activity_label]
        notes = st.text_input("Notes", key="prj_time_notes")

        mode = st.radio(
            "Workers",
            options=["Select workers", "Number of rows"],
            horizontal=True,
            key="prj_time_worker_mode",
        )

        worker_rows: list[dict] = []
        preview_cost = 0.0
        preview_minutes = 0

        if mode == "Select workers":
            id_to_name = {w["id"]: w["name"] for w in workers_by_id.values()}
            selected_ids = st.multiselect(
                "Workers",
                options=list(workers_by_id.keys()),
                format_func=lambda wid: id_to_name[wid],
                key="prj_time_multiselect",
            )
            for wid in selected_ids:
                worker = workers_by_id[wid]
                st.markdown(f"**{worker['name']}**")
                c1, c2, c3 = st.columns([2, 2, 1])
                duration = c1.number_input(
                    "Duration (minutes)",
                    min_value=1,
                    value=60,
                    step=15,
                    key=f"prj_time_dur_{wid}",
                )
                rate_override = c2.number_input(
                    "Rate override (0 = cascade)",
                    min_value=0.0,
                    value=0.0,
                    step=50.0,
                    key=f"prj_time_rate_{wid}",
                )
                zero_cost = c3.checkbox("Zero cost", key=f"prj_time_zero_{wid}")
                rate = _resolve_rate(project, activity_id, worker, rate_override)
                row_cost = 0.0 if zero_cost else _DOMAIN.compute_labour_cost(int(duration), rate)
                preview_cost += row_cost
                preview_minutes += int(duration)
                worker_rows.append(
                    {
                        "worker_id": wid,
                        "duration_minutes": int(duration),
                        "hourly_rate": rate_override if rate_override > 0 else None,
                        "zero_cost_override": zero_cost,
                    }
                )
        else:
            row_count = st.number_input(
                "How many rows",
                min_value=1,
                max_value=20,
                value=1,
                step=1,
                key="prj_time_row_count",
            )
            id_to_name = {w["id"]: w["name"] for w in workers_by_id.values()}
            worker_ids = list(workers_by_id.keys())
            for idx in range(int(row_count)):
                st.markdown(f"**Row {idx + 1}**")
                c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
                wid = c1.selectbox(
                    "Worker",
                    options=worker_ids,
                    format_func=lambda x, m=id_to_name: m[x],
                    key=f"prj_time_row_worker_{idx}",
                )
                duration = c2.number_input(
                    "Duration (minutes)",
                    min_value=1,
                    value=60,
                    step=15,
                    key=f"prj_time_row_dur_{idx}",
                )
                rate_override = c3.number_input(
                    "Rate override (0 = cascade)",
                    min_value=0.0,
                    value=0.0,
                    step=50.0,
                    key=f"prj_time_row_rate_{idx}",
                )
                zero_cost = c4.checkbox("Zero cost", key=f"prj_time_row_zero_{idx}")
                worker = workers_by_id[wid]
                rate = _resolve_rate(project, activity_id, worker, rate_override)
                row_cost = 0.0 if zero_cost else _DOMAIN.compute_labour_cost(int(duration), rate)
                preview_cost += row_cost
                preview_minutes += int(duration)
                worker_rows.append(
                    {
                        "worker_id": wid,
                        "duration_minutes": int(duration),
                        "hourly_rate": rate_override if rate_override > 0 else None,
                        "zero_cost_override": zero_cost,
                    }
                )

        st.caption(
            f"Preview: {preview_minutes} min · est. cost {H.fmt_money(preview_cost)}"
        )
        if st.button("Save time entries", type="primary", key="prj_time_save"):
            if not worker_rows:
                st.error("Select at least one worker row")
            else:
                H.run_action(
                    lambda: time_svc.create_time_entries(
                        project.id,
                        activity_id,
                        worker_rows,
                        work_date,
                        notes=notes,
                    ),
                    "Time logged",
                )

    st.divider()
    st.subheader("Register")
    try:
        entries = time_svc.list_by_project(project.id)
    except Exception as exc:
        st.error(str(exc))
        return

    if not entries:
        H.empty_state("No time entries yet.")
        return

    total_minutes = sum(e.duration_minutes for e in entries)
    total_cost = sum(e.labour_cost for e in entries)
    rows = []
    for entry in sorted(entries, key=lambda e: e.work_date, reverse=True):
        rows.append(
            {
                "Date": entry.work_date,
                "Worker": entry.worker_name,
                "Activity": H.activity_label(project, entry.activity_id),
                "Minutes": entry.duration_minutes,
                "Rate": entry.hourly_rate,
                "Cost": entry.labour_cost,
                "Notes": entry.notes or "—",
                "_id": entry.id,
            }
        )

    st.dataframe(
        pd.DataFrame(rows).drop(columns=["_id"]),
        use_container_width=True,
        hide_index=True,
    )
    st.caption(
        f"Totals: {total_minutes:,} min ({H.fmt_hours(total_minutes / 60.0)}) · "
        f"cost {H.fmt_money(total_cost)}"
    )

    for row in rows:
        cols = st.columns([5, 1])
        cols[0].caption(
            f"{row['Date']} · {row['Worker']} · {row['Minutes']} min · {H.fmt_money(row['Cost'])}"
        )
        if cols[1].button("Delete", key=f"prj_time_del_{row['_id']}"):
            H.run_action(
                lambda eid=row["_id"]: time_svc.delete_time_entry(eid),
                "Time entry deleted",
            )
