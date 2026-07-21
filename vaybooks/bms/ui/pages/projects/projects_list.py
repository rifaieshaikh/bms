"""Projects list — filter/sort, cards, and multi-step create wizard."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.domain.shared.enums import ProjectStatus
from vaybooks.bms.ui import filtering as F
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.list_view import render_list
from vaybooks.bms.ui.components.project_card import WORKSPACE_ID, project_cards
from vaybooks.bms.ui.dialog_utils import register_armed_dialog
from vaybooks.bms.ui.filtering import FilterField, ListSchema, SortOption
from vaybooks.bms.ui.pagination import CARD_PAGE_SIZE
from vaybooks.bms.ui.pages.projects.wizard import CREATE_DIALOG, render_project_wizard

PROJECTS = ListSchema(
    entity_key="projects",
    title="Projects",
    filter_fields=[
        FilterField("project_number", "Project number", F.EXACT),
        FilterField("name", "Project name", F.EXACT),
        FilterField("customer_id", "Customer", F.ENTITY_SELECT, options_loader="customers"),
        FilterField("customer_name", "Customer name", F.EXACT),
        FilterField("statuses", "Status", F.MULTISELECT, record_attr="status",
                     options=[(s.value, s.value) for s in ProjectStatus]),
        FilterField("site_state_code", "Site state", F.EXACT),
    ],
    sort_options=[
        SortOption("created_at", "Created"),
        SortOption("project_number", "Project number"),
        SortOption("name", "Project name"),
        SortOption("customer_name", "Customer name"),
        SortOption("contract_value", "Contract value"),
    ],
    default_sort="created_at",
    page_size=CARD_PAGE_SIZE,
)


def _load_projects(services, filters, sort):
    try:
        return services["projects"].search_projects("")
    except Exception:
        try:
            return services["projects"].list_projects()
        except Exception:
            return []


def _render_cards(page_projects, services) -> None:
    project_cards(page_projects)


def _open_workspace(project_id: str) -> None:
    st.session_state[WORKSPACE_ID] = project_id
    navigation.go_to_list("project_workspace", project=project_id)


def render(services: dict) -> None:
    register_armed_dialog(CREATE_DIALOG)

    bar = render_list(
        PROJECTS,
        services=services,
        load_fn=_load_projects,
        card_renderer=_render_cards,
        primary_label="New Project",
        primary_key="projects_new_btn",
        count_label="projects",
        empty_text="No projects found.",
        page_key_nav="projects_list",
    )

    if bar["primary_clicked"]:
        st.session_state[CREATE_DIALOG] = True
        st.rerun()

    if st.session_state.get(CREATE_DIALOG):
        render_project_wizard(services)

    project_id = bar.get("view_nth") or bar.get("edit_nth")
    if project_id:
        _open_workspace(project_id)
