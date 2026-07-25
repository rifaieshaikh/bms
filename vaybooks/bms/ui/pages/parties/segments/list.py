"""Parties → Segments: CRUD for shared customer/vendor segments."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.domain.parties.segments.entities import (
    APPLIES_TO_CUSTOMER,
    APPLIES_TO_VENDOR,
)
from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.ui.components.common.list_view import render_list
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler
from vaybooks.bms.ui.filtering import FilterField, ListSchema, SortOption
from vaybooks.bms.ui import filtering as F
from vaybooks.bms.ui.pagination import CARD_PAGE_SIZE
from vaybooks.bms.ui.styles import render_card_grid, status_badge

S_ADD = "segment_add_dialog"
S_EDIT = "segment_edit_dialog"
S_DELETE = "segment_delete_dialog"

APPLIES_LABELS = {
    APPLIES_TO_CUSTOMER: "Customers",
    APPLIES_TO_VENDOR: "Vendors",
}


def _applies_to_from_labels(selected: list[str]) -> list[str]:
    return [key for key, label in APPLIES_LABELS.items() if label in selected]


def _applies_caption(applies_to: list[str]) -> str:
    labels = [APPLIES_LABELS[a] for a in (applies_to or []) if a in APPLIES_LABELS]
    return ", ".join(labels) if labels else "—"


def _match_segment_active(segment, _value) -> bool:
    return bool(getattr(segment, "is_active", False))


def _match_applies_to(segment, value) -> bool:
    return value in (getattr(segment, "applies_to", None) or [])


SEGMENTS = ListSchema(
    entity_key="party_segments",
    title="Segments",
    filter_fields=[
        FilterField("name", "Name", F.REGEX),
        FilterField(
            "applies_filter",
            "Applies to",
            F.SELECT,
            options=[
                (APPLIES_TO_CUSTOMER, "Customers"),
                (APPLIES_TO_VENDOR, "Vendors"),
            ],
            match=_match_applies_to,
        ),
        FilterField(
            "active_only",
            "Active only",
            F.CHECKBOX,
            match=_match_segment_active,
        ),
    ],
    sort_options=[
        SortOption("name", "Name"),
        SortOption("created_at", "Created"),
    ],
    default_sort="name",
    default_desc=False,
    page_size=CARD_PAGE_SIZE,
)


@st.dialog("Add Segment", on_dismiss=make_dismiss_handler(S_ADD))
def _add_segment_dialog(segments_svc):
    name = st.text_input("Name *", key="add_segment_name")
    applies = st.multiselect(
        "Applies to *",
        list(APPLIES_LABELS.values()),
        default=list(APPLIES_LABELS.values()),
        key="add_segment_applies",
    )
    is_active = st.checkbox("Active", value=True, key="add_segment_active")
    if st.button("Create Segment", type="primary", width="stretch"):
        if not name.strip():
            st.error("Segment name is required")
            return
        if not applies:
            st.error("Select at least one party type")
            return
        try:
            segments_svc.create_segment(
                name,
                applies_to=_applies_to_from_labels(applies),
                is_active=is_active,
            )
            st.session_state.pop(S_ADD, None)
            st.success(f"Created segment: {name.strip()}")
            st.rerun()
        except ValidationError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(str(exc))


@st.dialog("Edit Segment", on_dismiss=make_dismiss_handler(S_EDIT))
def _edit_segment_dialog(segments_svc, segment_id: str):
    segment = segments_svc.get_segment(segment_id)
    if not segment:
        st.error("Segment not found")
        return

    name = st.text_input("Name *", value=segment.name, key="edit_segment_name")
    current_applies = [
        APPLIES_LABELS[a]
        for a in (segment.applies_to or [])
        if a in APPLIES_LABELS
    ]
    applies = st.multiselect(
        "Applies to *",
        list(APPLIES_LABELS.values()),
        default=current_applies,
        key="edit_segment_applies",
    )
    is_active = st.checkbox(
        "Active", value=segment.is_active, key="edit_segment_active"
    )
    cols = st.columns(2)
    if cols[0].button("Save Changes", type="primary", width="stretch"):
        if not name.strip():
            st.error("Segment name is required")
            return
        if not applies:
            st.error("Select at least one party type")
            return
        try:
            segments_svc.update_segment(
                segment_id,
                name=name,
                applies_to=_applies_to_from_labels(applies),
                is_active=is_active,
            )
            st.session_state.pop(S_EDIT, None)
            st.success("Segment updated")
            st.rerun()
        except ValidationError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(str(exc))
    if cols[1].button("Delete", width="stretch"):
        st.session_state.pop(S_EDIT, None)
        st.session_state[S_DELETE] = segment_id
        st.rerun()


@st.dialog("Delete Segment", on_dismiss=make_dismiss_handler(S_DELETE))
def _delete_segment_dialog(segments_svc, segment_id: str):
    segment = segments_svc.get_segment(segment_id)
    label = segment.name if segment else "this segment"
    st.warning(f"Delete **{label}**? Customers and vendors keep their other segments.")
    cols = st.columns(2)
    if cols[0].button("Delete", type="primary", width="stretch"):
        try:
            segments_svc.delete_segment(segment_id)
            st.session_state.pop(S_DELETE, None)
            st.success("Segment deleted")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if cols[1].button("Cancel", width="stretch"):
        st.session_state.pop(S_DELETE, None)
        st.rerun()


def _segment_card(segment, index: int):
    with st.container(border=True):
        status = "Active" if segment.is_active else "Inactive"
        color = "green" if segment.is_active else "gray"
        st.markdown(f"**{segment.name}**")
        st.markdown(status_badge(status, color), unsafe_allow_html=True)
        st.caption(f"Applies to: {_applies_caption(segment.applies_to)}")
        cols = st.columns(2)
        if cols[0].button(
            "Edit",
            key=f"edit_segment_btn_{index}_{segment.id}",
            width="stretch",
        ):
            st.session_state[S_EDIT] = segment.id
        if cols[1].button(
            "Delete",
            key=f"del_segment_btn_{index}_{segment.id}",
            width="stretch",
        ):
            st.session_state[S_DELETE] = segment.id


def _load_segments(services, filters, sort):
    segments_svc = services.get("party_segments")
    if not segments_svc:
        return []
    try:
        return segments_svc.list_segments(active_only=False)
    except Exception:
        return []


def _render_cards(page_segments, services):
    render_card_grid(
        page_segments,
        lambda segment, i: _segment_card(segment, i),
        suffix="segments",
    )


def render(services: dict):
    segments_svc = services.get("party_segments")
    if segments_svc is None:
        st.error("Party segments service is not available.")
        return

    st.caption(
        "Shared labels for Customers and Vendors. Assign multiple segments on each party."
    )
    bar = render_list(
        SEGMENTS,
        services=services,
        load_fn=_load_segments,
        card_renderer=_render_cards,
        primary_label="Add Segment",
        primary_key="segments_add_btn",
        count_label="segments",
        empty_text="No segments yet. Create one to start grouping customers and vendors.",
        page_key_nav="segments_list",
    )
    if bar["primary_clicked"]:
        st.session_state[S_ADD] = True

    if st.session_state.get(S_ADD):
        _add_segment_dialog(segments_svc)
    if st.session_state.get(S_EDIT):
        _edit_segment_dialog(segments_svc, st.session_state[S_EDIT])
    if st.session_state.get(S_DELETE):
        _delete_segment_dialog(segments_svc, st.session_state[S_DELETE])
