"""Project list cards — same pattern as customization order cards."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.shared import CardAction, card, empty_state
from vaybooks.bms.ui.styles import render_card_grid

WORKSPACE_ID = "project_workspace_id"


def project_card(project, key_prefix: str) -> None:
    def _on_view() -> None:
        st.session_state[WORKSPACE_ID] = project.id
        navigation.go_to_list("project_workspace", project=project.id)

    with st.container(border=True):
        card(
            project.project_number,
            badges=[(project.status.value, None)],
            caption_lines=[
                project.name,
                project.customer_name,
                f"Contract ₹{float(project.contract_value or 0):,.0f}",
                f"Site: {project.site_state_code}" if project.site_state_code else "",
            ],
            actions=[
                CardAction(
                    "View",
                    key=f"{key_prefix}_view",
                    kind="secondary",
                    on_click=_on_view,
                )
            ],
        )


def project_cards(projects: list, key_prefix: str = "prj") -> None:
    if not projects:
        empty_state("No projects found.")
        return
    render_card_grid(
        projects,
        lambda project, _i: project_card(project, f"{key_prefix}_{project.id}"),
        suffix=key_prefix,
    )
