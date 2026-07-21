"""Project enquiries list — cards + new enquiry dialog."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.domain.shared.enums import ProjectEnquiryStatus
from vaybooks.bms.domain.shared.india import INDIAN_STATES
from vaybooks.bms.ui import filtering as F
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.list_view import render_list
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler
from vaybooks.bms.ui.filtering import FilterField, ListSchema, SortOption
from vaybooks.bms.ui.pagination import CARD_PAGE_SIZE
from vaybooks.bms.ui.styles import panel, status_badge

ENQUIRIES = ListSchema(
    entity_key="project_enquiries",
    title="Enquiries",
    filter_fields=[
        FilterField("enquiry_number", "Enquiry number", F.EXACT),
        FilterField("customer_name", "Customer name", F.EXACT),
        FilterField(
            "statuses",
            "Status",
            F.MULTISELECT,
            record_attr="status",
            options=[(s.value, s.value) for s in ProjectEnquiryStatus],
        ),
    ],
    sort_options=[
        SortOption("created_at", "Created (newest)"),
        SortOption("enquiry_number", "Enquiry number"),
        SortOption("customer_name", "Customer name"),
    ],
    default_sort="created_at",
    page_size=CARD_PAGE_SIZE,
)

CREATE_DIALOG = "prj_enquiry_create_dialog"
WORKSPACE_ID = "project_enquiry_workspace_id"


def _load_enquiries(services, filters, sort):
    svc = services.get("project_enquiries")
    if svc is None:
        return []
    try:
        return svc.list_enquiries()
    except Exception:
        return []


def _render_cards(page_items, services) -> None:
    if not page_items:
        st.info("No enquiries yet.")
        return
    for enquiry in page_items:
        with panel(f"enq_card_{enquiry.id}"):
            with st.container(border=True):
                cols = st.columns([3, 2, 1])
                with cols[0]:
                    st.markdown(f"**{enquiry.enquiry_number}**")
                    st.caption(enquiry.customer_name)
                    if enquiry.requirement:
                        st.caption(enquiry.requirement[:120])
                with cols[1]:
                    st.markdown(
                        status_badge(enquiry.status.value),
                        unsafe_allow_html=True,
                    )
                    if enquiry.project_id:
                        st.caption("Linked project")
                with cols[2]:
                    if st.button("View", key=f"enq_view_{enquiry.id}"):
                        st.session_state[WORKSPACE_ID] = enquiry.id
                        navigation.go_to_list(
                            "project_enquiry_workspace", enquiry=enquiry.id
                        )


@st.dialog(
    "New Enquiry", width="large", on_dismiss=make_dismiss_handler(CREATE_DIALOG)
)
def _create_enquiry_dialog(services: dict) -> None:
    customers = services["customers"].list_all_customers()
    customer_labels = {c.customer_name: c.id for c in customers}
    customer_label = st.selectbox(
        "Customer",
        options=[""] + list(customer_labels.keys()),
        key="enq_new_customer",
    )
    site_address = st.text_area("Site address", key="enq_new_site")
    state_labels = [f"{s['code']} — {s['name']}" for s in INDIAN_STATES]
    code_by_label = {label: s["code"] for label, s in zip(state_labels, INDIAN_STATES)}
    site_state_label = st.selectbox(
        "Site state",
        options=[""] + state_labels,
        key="enq_new_state",
    )
    requirement = st.text_area("Requirement", key="enq_new_req")
    source = st.text_input("Source", key="enq_new_source")

    cols = st.columns(2)
    if cols[0].button("Cancel", use_container_width=True):
        st.session_state.pop(CREATE_DIALOG, None)
        st.rerun()
    if cols[1].button("Create", type="primary", use_container_width=True):
        if not customer_label:
            st.error("Customer is required")
            return
        try:
            enquiry = services["project_enquiries"].create_enquiry(
                customer_labels[customer_label],
                site_address=site_address or "",
                site_state_code=code_by_label.get(site_state_label, ""),
                requirement=requirement or "",
                source=source or "",
            )
            st.session_state.pop(CREATE_DIALOG, None)
            st.session_state[WORKSPACE_ID] = enquiry.id
            navigation.go_to_list(
                "project_enquiry_workspace", enquiry=enquiry.id
            )
        except Exception as exc:
            st.error(str(exc))


def render(services: dict) -> None:
    st.title("Enquiries")
    if st.button("New Enquiry", type="primary", key="enq_new_btn"):
        st.session_state[CREATE_DIALOG] = True
    if st.session_state.get(CREATE_DIALOG):
        _create_enquiry_dialog(services)
    render_list(
        ENQUIRIES,
        services,
        load_fn=_load_enquiries,
        render_page_fn=_render_cards,
    )
