"""Project list cards — same pattern as customization order cards."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.styles import render_card_grid, status_badge

WORKSPACE_ID = "project_workspace_id"


def project_card(project, key_prefix: str) -> None:
    with st.container(border=True):
        st.markdown(f"**{project.project_number}**")
        st.caption(project.name)
        st.markdown(status_badge(project.status.value), unsafe_allow_html=True)
        st.write(project.customer_name)
        st.caption(f"Contract ₹{float(project.contract_value or 0):,.0f}")
        if project.site_state_code:
            st.caption(f"Site: {project.site_state_code}")
        if st.button("View", key=f"{key_prefix}_view", use_container_width=True):
            st.session_state[WORKSPACE_ID] = project.id
            navigation.go_to_list("project_workspace", project=project.id)


def project_cards(projects: list, key_prefix: str = "prj") -> None:
    if not projects:
        st.info("No projects found.")
        return
    render_card_grid(
        projects,
        lambda project, _i: project_card(project, f"{key_prefix}_{project.id}"),
        suffix=key_prefix,
    )
