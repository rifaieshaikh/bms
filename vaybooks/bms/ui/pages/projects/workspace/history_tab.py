"""History / audit tab for project workspace (Wave 1)."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.ui.pages.projects.workspace import helpers as H


def render_history(services: dict, project) -> None:
    audit = services.get("project_audit")
    if audit is None:
        st.info("Audit service is not configured.")
        return
    try:
        entries = audit.list_by_project(project.id)
    except Exception as exc:
        st.error(str(exc))
        return
    if not entries:
        H.empty_state("No history yet. Controlled changes will appear here.")
        return
    rows = [
        {
            "When": e.created_at,
            "Actor": e.actor_name or e.actor_id or "—",
            "Entity": e.entity_type,
            "Action": e.action,
            "Reason": e.reason or "—",
            "Before": str(e.before or "")[:80],
            "After": str(e.after or "")[:80],
        }
        for e in entries
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)
