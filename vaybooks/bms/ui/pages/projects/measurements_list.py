"""Cross-project measurements list with project picker."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.projects.project_card import WORKSPACE_ID
from vaybooks.bms.ui.styles import metric_grid


def _project_options(services: dict) -> dict[str, str]:
    try:
        projects = services["projects"].list_projects()
    except Exception:
        return {}
    return {
        f"{p.project_number} — {p.name}": p.id
        for p in projects
    }


def _load_measurements(services: dict, project_id: str | None):
    meas_svc = services.get("project_measurement")
    if meas_svc is None:
        return []
    rows = []
    if project_id:
        project_ids = [project_id]
    else:
        try:
            project_ids = [p.id for p in services["projects"].list_projects()]
        except Exception:
            project_ids = []
    projects_by_id = {}
    try:
        for p in services["projects"].list_projects():
            projects_by_id[p.id] = p
    except Exception:
        pass
    for pid in project_ids:
        try:
            measurements = meas_svc.list_by_project(pid)
        except Exception:
            continue
        project = projects_by_id.get(pid)
        for m in measurements:
            rows.append(
                {
                    "project_id": pid,
                    "project": (
                        f"{project.project_number} — {project.name}"
                        if project
                        else pid[:8]
                    ),
                    "date": m.measurement_date,
                    "quantity": m.quantity,
                    "cumulative": m.cumulative_quantity,
                    "status": m.status.value if hasattr(m.status, "value") else m.status,
                    "ra_bill_id": (m.ra_bill_id or "")[:12] or "—",
                    "eligible": not bool((m.ra_bill_id or "").strip())
                    and str(getattr(m.status, "value", m.status))
                    in (
                        "Submitted",
                        "Engineer Verified",
                        "Customer Certified",
                    ),
                    "id": m.id,
                }
            )
    return rows


def render(services: dict) -> None:
    st.title("Measurements")
    st.caption("Certified and in-progress measurements across projects.")

    opts = _project_options(services)
    labels = ["All projects"] + list(opts.keys())
    selected = st.selectbox("Project", options=labels, key="prj_meas_list_project")
    project_id = None if selected == "All projects" else opts.get(selected)

    rows = _load_measurements(services, project_id)
    eligible = sum(1 for r in rows if r.get("eligible"))
    billed = sum(1 for r in rows if r.get("ra_bill_id") not in ("", "—"))
    metric_grid(
        [
            ("Measurements", str(len(rows))),
            ("Eligible for RA", str(eligible)),
            ("Linked to RA", str(billed)),
        ],
        suffix="prj_meas_list",
    )

    if not rows:
        st.info("No measurements found.")
        return

    display = pd.DataFrame(
        [
            {
                "Project": r["project"],
                "Date": r["date"],
                "Qty": r["quantity"],
                "Cumulative": r["cumulative"],
                "Status": r["status"],
                "RA": r["ra_bill_id"],
                "Eligible": "Yes" if r["eligible"] else "No",
            }
            for r in rows
        ]
    )
    st.dataframe(display, use_container_width=True, hide_index=True)

    if project_id:
        if st.button("Open project workspace", key="prj_meas_open_ws"):
            st.session_state[WORKSPACE_ID] = project_id
            navigation.go_to_list("project_workspace", project=project_id)
