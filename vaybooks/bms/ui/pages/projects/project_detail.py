"""Project detail route — redirects to the project workspace."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.ui import navigation

WORKSPACE_ID = "project_workspace_id"


def render(services: dict) -> None:
    project_id = navigation.current_detail_id("project_detail")
    if not project_id:
        st.warning("No project selected.")
        navigation.go_to_list("projects_list")
        return

    st.session_state[WORKSPACE_ID] = project_id
    navigation.go_to_list("project_workspace", project=project_id)
