"""Cross-project RA bills list with project picker."""

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
    return {f"{p.project_number} — {p.name}": p.id for p in projects}


def _load_ra_bills(services: dict, project_id: str | None):
    billing_svc = services.get("project_billing")
    if billing_svc is None:
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
            bills = billing_svc.list_ra_bills(pid)
        except Exception:
            continue
        project = projects_by_id.get(pid)
        for ra in bills:
            status = ra.status.value if hasattr(ra.status, "value") else ra.status
            rows.append(
                {
                    "project_id": pid,
                    "project": (
                        f"{project.project_number} — {project.name}"
                        if project
                        else pid[:8]
                    ),
                    "ra_number": ra.ra_number,
                    "ra_date": ra.ra_date,
                    "status": status,
                    "gross_claimed": getattr(ra, "gross_claimed", 0),
                    "gross_certified": getattr(ra, "gross_certified", 0),
                    "invoice": (ra.invoice_voucher_id or "")[:12] or "—",
                    "id": ra.id,
                }
            )
    return rows


def render(services: dict) -> None:
    st.title("RA Bills")
    st.caption("Running-account bills across projects.")

    opts = _project_options(services)
    labels = ["All projects"] + list(opts.keys())
    selected = st.selectbox("Project", options=labels, key="prj_ra_list_project")
    project_id = None if selected == "All projects" else opts.get(selected)

    rows = _load_ra_bills(services, project_id)
    draft = sum(1 for r in rows if r["status"] in ("Draft", "Submitted"))
    invoiced = sum(1 for r in rows if r["status"] == "Invoiced")
    metric_grid(
        [
            ("RA bills", str(len(rows))),
            ("Draft / submitted", str(draft)),
            ("Invoiced", str(invoiced)),
        ],
        suffix="prj_ra_list",
    )

    if not rows:
        st.info("No RA bills found.")
        return

    display = pd.DataFrame(
        [
            {
                "Project": r["project"],
                "RA #": r["ra_number"],
                "Date": r["ra_date"],
                "Status": r["status"],
                "Claimed": r["gross_claimed"],
                "Certified": r["gross_certified"],
                "Invoice": r["invoice"],
            }
            for r in rows
        ]
    )
    st.dataframe(display, use_container_width=True, hide_index=True)

    if project_id:
        if st.button("Open project workspace", key="prj_ra_open_ws"):
            st.session_state[WORKSPACE_ID] = project_id
            navigation.go_to_list("project_workspace", project=project_id)
