"""Measurement Specs admin — CRUD fields per person type."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.domain.shared.enums import (
    MeasurementFieldType,
    PersonType,
)

PENDING_EDIT_SPEC = "pending_edit_measurement_spec"
PENDING_EDIT_SECTION = "pending_edit_measurement_section"


def _person_options() -> list[str]:
    return [p.value for p in PersonType]


def _section_options(measurement_service) -> list[str]:
    return [section.key for section in measurement_service.list_sections()]


def _section_label_map(measurement_service) -> dict[str, str]:
    return {
        section.key: section.label
        for section in measurement_service.list_sections()
    }


def _type_options() -> list[str]:
    return [t.value for t in MeasurementFieldType]


@st.dialog("Add Measurement Field")
def _add_spec_dialog(measurement_service):
    key = st.text_input("Key (stable id)", placeholder="e.g. bust")
    label = st.text_input("Label", placeholder="e.g. Bust")
    person_types = st.multiselect(
        "Person types", options=_person_options(), default=[PersonType.WOMEN.value]
    )
    section_labels = _section_label_map(measurement_service)
    section = st.selectbox(
        "Section",
        list(section_labels),
        format_func=lambda key: section_labels.get(key, key),
    )
    value_type = st.selectbox("Value type", _type_options())
    unit = st.text_input("Unit", value="inch")
    required = st.checkbox("Required", value=False)
    is_active = st.checkbox("Active", value=True)
    sort_order = st.number_input("Sort order", min_value=0, value=100, step=10)
    help_text = st.text_input("Help text", value="")
    options_raw = st.text_area("Select options (one per line)", value="")
    if st.button("Save field", type="primary"):
        if not key or not label or not person_types:
            st.error("Key, label, and at least one person type are required")
            return
        try:
            measurement_service.create_spec(
                key=key,
                label=label,
                person_types=person_types,
                section=section,
                value_type=value_type,
                unit=unit,
                required=required,
                sort_order=int(sort_order),
                is_core=False,
                is_active=is_active,
                help_text=help_text,
                options=[ln.strip() for ln in options_raw.splitlines() if ln.strip()],
            )
            st.success("Field created")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


@st.dialog("Edit Measurement Field")
def _edit_spec_dialog(measurement_service, field_id: str):
    field = measurement_service.get_spec(field_id)
    if not field:
        st.error("Field not found")
        return
    label = st.text_input("Label", value=field.label)
    person_types = st.multiselect(
        "Person types",
        options=_person_options(),
        default=[p.value for p in field.person_types],
    )
    section_labels = _section_label_map(measurement_service)
    section_options = list(section_labels)
    if field.section not in section_options:
        section_options.append(field.section)
    section = st.selectbox(
        "Section",
        section_options,
        index=section_options.index(field.section),
        format_func=lambda key: section_labels.get(key, key),
    )
    value_type = st.selectbox(
        "Value type",
        _type_options(),
        index=_type_options().index(field.value_type.value),
    )
    unit = st.text_input("Unit", value=field.unit)
    required = st.checkbox("Required", value=field.required)
    is_active = st.checkbox("Active", value=field.is_active)
    sort_order = st.number_input(
        "Sort order", min_value=0, value=int(field.sort_order), step=10
    )
    help_text = st.text_input("Help text", value=field.help_text)
    options_raw = st.text_area(
        "Select options (one per line)",
        value="\n".join(field.options),
    )
    st.caption(f"Key: `{field.key}` · Core: {'yes' if field.is_core else 'no'}")
    cols = st.columns(2)
    if cols[0].button("Save changes", type="primary"):
        try:
            measurement_service.update_spec(
                field_id,
                label=label,
                person_types=person_types,
                section=section,
                value_type=value_type,
                unit=unit,
                required=required,
                is_active=is_active,
                sort_order=int(sort_order),
                help_text=help_text,
                options=[ln.strip() for ln in options_raw.splitlines() if ln.strip()],
            )
            st.success("Updated")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if cols[1].button("Delete field"):
        try:
            measurement_service.delete_spec(field_id)
            st.success("Deleted")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


@st.dialog("Add Measurement Section")
def _add_section_dialog(measurement_service):
    key = st.text_input("Key", placeholder="e.g. posture")
    label = st.text_input("Label", placeholder="e.g. Posture")
    sort_order = st.number_input("Sort order", min_value=0, value=600, step=10)
    if st.button("Save section", type="primary"):
        try:
            measurement_service.create_section(
                key=key,
                label=label,
                sort_order=int(sort_order),
            )
            st.success("Section created")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


@st.dialog("Edit Measurement Section")
def _edit_section_dialog(measurement_service, section_id: str):
    section = next(
        (
            row
            for row in measurement_service.list_sections()
            if row.id == section_id
        ),
        None,
    )
    if not section:
        st.error("Section not found")
        return
    label = st.text_input("Label", value=section.label)
    sort_order = st.number_input(
        "Sort order", min_value=0, value=section.sort_order, step=10
    )
    is_active = st.checkbox("Active", value=section.is_active)
    st.caption(f"Stable key: `{section.key}`")
    cols = st.columns(2)
    if cols[0].button("Save changes", type="primary"):
        try:
            measurement_service.update_section(
                section.id,
                label=label,
                sort_order=int(sort_order),
                is_active=is_active,
            )
            st.success("Section updated")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if cols[1].button("Delete section"):
        try:
            measurement_service.delete_section(section.id)
            st.success("Section deleted")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def render(services: dict):
    measurement_service = services["measurements"]
    st.title("Measurement Specs")
    st.caption(
        "Configure body and garment-length fields per person type. "
        "Core fields ship seeded; activate Extended fields or add custom ones."
    )

    fields_tab, sections_tab = st.tabs(["Fields", "Sections"])

    with fields_tab:
        person_filter = st.selectbox(
            "Filter by person type",
            options=["All"] + _person_options(),
            key="meas_spec_person_filter",
        )
        show_inactive = st.checkbox("Show inactive", value=True)

        specs = measurement_service.list_specs(active_only=not show_inactive)
        if person_filter != "All":
            specs = [
                s
                for s in specs
                if any(p.value == person_filter for p in s.person_types)
            ]

        if st.button("Add field", type="primary"):
            _add_spec_dialog(measurement_service)

        section_labels = _section_label_map(measurement_service)
        if not specs:
            st.info("No measurement fields configured.")
        for field in specs:
            with st.container(border=True):
                cols = st.columns([3, 2, 1, 1, 1])
                cols[0].markdown(f"**{field.label}** (`{field.key}`)")
                cols[1].write(", ".join(p.value for p in field.person_types))
                cols[2].write(section_labels.get(field.section, field.section))
                cols[3].write("Active" if field.is_active else "Inactive")
                if cols[4].button("Edit", key=f"edit_spec_{field.id}"):
                    st.session_state[PENDING_EDIT_SPEC] = field.id

    with sections_tab:
        st.caption(
            "Sections control how measurement fields are grouped and ordered "
            "on capture forms."
        )
        if st.button("Add section", type="primary"):
            _add_section_dialog(measurement_service)
        for section in measurement_service.list_sections():
            with st.container(border=True):
                cols = st.columns([3, 2, 1, 1])
                cols[0].markdown(f"**{section.label}** (`{section.key}`)")
                cols[1].write(f"Order: {section.sort_order}")
                cols[2].write("Active" if section.is_active else "Inactive")
                if cols[3].button("Edit", key=f"edit_section_{section.id}"):
                    st.session_state[PENDING_EDIT_SECTION] = section.id

    pending = st.session_state.pop(PENDING_EDIT_SPEC, None)
    pending_section = st.session_state.pop(PENDING_EDIT_SECTION, None)
    if pending:
        _edit_spec_dialog(measurement_service, pending)
    elif pending_section:
        _edit_section_dialog(measurement_service, pending_section)
