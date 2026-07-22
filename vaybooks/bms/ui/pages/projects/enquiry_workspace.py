"""Enquiry workspace — assessments and link to draft project."""

from __future__ import annotations

from datetime import date

import streamlit as st

from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.projects.project_card import WORKSPACE_ID as PROJECT_WS_ID
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler
from vaybooks.bms.ui.pages.projects.enquiries_list import WORKSPACE_ID
from vaybooks.bms.ui.styles import panel, status_badge

ASSESS_DIALOG = "prj_enquiry_assess_dialog"


def _resolve_enquiry_id() -> str | None:
    param_id = navigation.consume_list_param("project_enquiry_workspace", "enquiry")
    if param_id:
        st.session_state[WORKSPACE_ID] = param_id
    return st.session_state.get(WORKSPACE_ID)


@st.dialog(
    "Add site assessment",
    width="large",
    on_dismiss=make_dismiss_handler(ASSESS_DIALOG),
)
def _assessment_dialog(services: dict, enquiry_id: str) -> None:
    visit_date = st.date_input("Visit date", value=date.today(), key="enq_assess_date")
    conditions = st.text_area("Conditions", key="enq_assess_cond")
    measurements_notes = st.text_area("Measurements", key="enq_assess_meas")
    access_notes = st.text_input("Access", key="enq_assess_access")
    utilities_notes = st.text_input("Utilities", key="enq_assess_util")
    risks = st.text_area("Risks", key="enq_assess_risks")
    assumptions = st.text_area("Assumptions", key="enq_assess_assumptions")
    recommended_scope = st.text_area("Recommended scope", key="enq_assess_scope")
    cols = st.columns(2)
    if cols[0].button("Cancel", use_container_width=True):
        st.session_state.pop(ASSESS_DIALOG, None)
        st.rerun()
    if cols[1].button("Save", type="primary", use_container_width=True):
        try:
            services["project_enquiries"].add_assessment(
                enquiry_id,
                visit_date=visit_date,
                conditions=conditions or "",
                measurements_notes=measurements_notes or "",
                access_notes=access_notes or "",
                utilities_notes=utilities_notes or "",
                risks=risks or "",
                assumptions=assumptions or "",
                recommended_scope=recommended_scope or "",
                submit=True,
            )
            st.session_state.pop(ASSESS_DIALOG, None)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def render(services: dict) -> None:
    enquiry_id = _resolve_enquiry_id()
    svc = services.get("project_enquiries")
    if not enquiry_id or svc is None:
        st.warning("No enquiry selected.")
        if st.button("← Back to enquiries", key="enq_ws_back_empty"):
            navigation.go_to_list("project_enquiries_list")
        return

    try:
        enquiry = svc.get_enquiry(enquiry_id)
    except Exception:
        enquiry = None
    if not enquiry:
        st.error("Enquiry not found.")
        if st.button("← Back to enquiries", key="enq_ws_missing"):
            navigation.go_to_list("project_enquiries_list")
        return

    if st.button("← Back to enquiries", key="enq_ws_back"):
        navigation.go_back_to_list("project_enquiries", "project_enquiries_list")
        return

    st.title(enquiry.enquiry_number)
    with panel(f"enq_head_{enquiry.id}"):
        with st.container(border=True):
            st.markdown(status_badge(enquiry.status.value), unsafe_allow_html=True)
            st.markdown(f"**{enquiry.customer_name}**")
            if enquiry.site_address:
                st.caption(f"Site: {enquiry.site_address}")
            if enquiry.requirement:
                st.caption(enquiry.requirement)

    tab_ov, tab_assess, tab_link = st.tabs(
        ["Overview", "Assessments", "Project link"]
    )

    with tab_ov:
        st.write(f"**Source:** {enquiry.source or '—'}")
        st.write(f"**Internal notes:** {enquiry.internal_notes or '—'}")
        st.write(f"**Customer notes:** {enquiry.customer_notes or '—'}")
        if enquiry.status.value == "Draft":
            if st.button("Submit enquiry", key="enq_submit"):
                try:
                    svc.update_status(enquiry.id, "Submitted")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    with tab_assess:
        if st.button("Add assessment", key="enq_add_assess"):
            st.session_state[ASSESS_DIALOG] = True
        if st.session_state.get(ASSESS_DIALOG):
            _assessment_dialog(services, enquiry.id)
        assessments = svc.list_assessments(enquiry.id)
        if not assessments:
            st.info("No site assessments yet.")
        for assessment in assessments:
            with st.container(border=True):
                st.markdown(f"**Visit {assessment.visit_date}**")
                if assessment.conditions:
                    st.caption(assessment.conditions)
                if assessment.recommended_scope:
                    st.write(assessment.recommended_scope)

    with tab_link:
        if enquiry.project_id:
            st.success(f"Linked project: {enquiry.project_id[:12]}…")
            if st.button("Open project workspace", type="primary", key="enq_open_prj"):
                st.session_state[PROJECT_WS_ID] = enquiry.project_id
                navigation.go_to_list(
                    "project_workspace", project=enquiry.project_id
                )
        else:
            st.caption("Start estimation to create a Draft project for BOQ and quotation.")
            if st.button("Start estimation", type="primary", key="enq_start_est"):
                try:
                    project = svc.start_estimation(enquiry.id)
                    st.success(f"Draft project {project.project_number} created")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
