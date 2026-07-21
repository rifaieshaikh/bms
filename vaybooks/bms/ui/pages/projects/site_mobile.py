"""Mobile site shell — offline-friendly capture sections (AC-015)."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.pages.projects.workspace import helpers as H

_SECTIONS = (
    "Today",
    "Progress",
    "Material",
    "Measurement",
    "Expense",
    "Photos",
    "Approval",
)


def _resolve_project_id() -> str | None:
    params = st.query_params
    raw = params.get("project") or params.get("project_id")
    if isinstance(raw, list):
        raw = raw[0] if raw else None
    if raw:
        st.session_state[H.WORKSPACE_ID] = str(raw)
    return st.session_state.get(H.WORKSPACE_ID)


def render(services: dict) -> None:
    st.title("Site mobile")
    project_id = _resolve_project_id()
    projects_svc = services.get("projects")
    offline = services.get("project_offline")
    if not project_id:
        st.info("Open with `?project=<project_id>` or pick a project from the workspace.")
        return
    project = None
    if projects_svc:
        try:
            project = projects_svc.get_project(project_id)
        except Exception:
            project = None
    if project is None:
        st.error("Project not found.")
        return

    st.caption(f"{project.project_number} · {project.name}")
    section = st.selectbox("Section", options=list(_SECTIONS), key="site_mob_section")
    note = st.text_area("Draft notes / payload", key="site_mob_payload")
    device_id = st.text_input("Device id", value="site-phone", key="site_mob_device")

    cols = st.columns(2)
    if cols[0].button("Save offline draft", type="primary", use_container_width=True):
        if offline is None:
            st.error("Offline draft service is not configured.")
        else:
            try:
                draft = offline.save_draft(
                    project.id,
                    section,
                    {"notes": note, "section": section},
                    device_id=device_id,
                )
                st.success(f"Draft saved ({draft.id[:8]}…) — pending sync")
            except Exception as exc:
                st.error(str(exc))

    st.subheader("Draft queue")
    if offline is None:
        st.caption("Offline service unavailable.")
        return
    drafts = offline.list_drafts(project.id)
    if not drafts:
        H.empty_state("No drafts yet.")
        return
    for draft in drafts:
        state = "synced" if draft.synced else "pending"
        row = st.columns([3, 1])
        row[0].write(
            f"**{draft.section}** · {state} · device={draft.device_id or '—'}"
        )
        if not draft.synced and row[1].button(
            "Sync", key=f"site_mob_sync_{draft.id}", use_container_width=True
        ):
            try:
                offline.sync_draft(draft.id)
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    if st.button("Back to workspace", key="site_mob_back"):
        navigation.open("project_workspace", project=project.id)
