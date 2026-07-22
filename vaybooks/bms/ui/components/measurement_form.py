"""Spec-driven measurement capture form."""

from __future__ import annotations

from datetime import date
from typing import Optional

import streamlit as st

from vaybooks.bms.domain.boutique.measurements.entities import MeasurementRecord
from vaybooks.bms.domain.shared.enums import (
    FitPreference,
    MeasurementFieldType,
    MeasurementSection,
    PersonType,
)


def _render_field_input(field, current, unit: str, key_prefix: str) -> Optional[dict]:
    label = field.label + (" *" if field.required else "")
    if not field.is_core:
        label = f"{label} (extra)"
    widget_key = f"{key_prefix}_f_{field.id}_{field.key}"
    if field.value_type == MeasurementFieldType.SELECT and field.options:
        options = [""] + list(field.options)
        current_val = current.value if current else ""
        idx = options.index(current_val) if current_val in options else 0
        value = st.selectbox(
            label,
            options,
            index=idx,
            key=widget_key,
            help=field.help_text or None,
        )
    else:
        value = st.text_input(
            label,
            value=current.value if current else "",
            key=widget_key,
            help=field.help_text or (f"Unit: {field.unit}" if field.unit else None),
        )
    if not value:
        return None
    return {
        "field_key": field.key,
        "value": value,
        "unit": field.unit if field.unit != "none" else unit,
        "notes": current.notes if current else "",
    }


def measurement_form(
    services: dict,
    *,
    customer_id: str,
    order_id: Optional[str] = None,
    existing: Optional[MeasurementRecord] = None,
    key_prefix: str = "meas",
) -> Optional[MeasurementRecord]:
    """Render a measurement create/edit form. Returns saved record or None."""
    measurement_service = services["measurements"]
    person_options = [p.value for p in PersonType]
    default_person = (
        existing.person_type.value if existing else PersonType.WOMEN.value
    )
    person_type = st.selectbox(
        "Person type",
        person_options,
        index=person_options.index(default_person),
        key=f"{key_prefix}_person",
        disabled=existing is not None,
    )
    specs = measurement_service.list_specs_for_person(person_type, active_only=True)
    sections = measurement_service.list_sections(active_only=True)
    if not specs:
        st.warning(
            "No measurement fields are configured for this person type. "
            "Open Settings → Measurement Specs, or restart the app so specs can seed."
        )

    cols = st.columns(2)
    wearer_name = cols[0].text_input(
        "Wearer name",
        value=existing.wearer_name if existing else "",
        key=f"{key_prefix}_wearer",
    )
    wearer_age = cols[1].text_input(
        "Age",
        value=existing.wearer_age if existing else "",
        key=f"{key_prefix}_age",
    )
    cols2 = st.columns(3)
    wearer_height = cols2[0].text_input(
        "Height (record)",
        value=existing.wearer_height if existing else "",
        key=f"{key_prefix}_height",
    )
    wearer_weight = cols2[1].text_input(
        "Weight (record)",
        value=existing.wearer_weight if existing else "",
        key=f"{key_prefix}_weight",
    )
    fit_options = [f.value for f in FitPreference]
    fit_default = (
        existing.fit_preference.value if existing else FitPreference.REGULAR.value
    )
    fit_preference = cols2[2].selectbox(
        "Fit",
        fit_options,
        index=fit_options.index(fit_default),
        key=f"{key_prefix}_fit",
    )
    unit = st.selectbox(
        "Default unit",
        ["inch", "cm"],
        index=0 if not existing or existing.unit == "inch" else 1,
        key=f"{key_prefix}_unit",
    )
    measured_by = st.text_input(
        "Measured by",
        value=existing.measured_by if existing else "",
        key=f"{key_prefix}_by",
    )
    measured_at = st.date_input(
        "Measured on",
        value=existing.measured_at if existing else date.today(),
        key=f"{key_prefix}_at",
    )

    existing_values = existing.value_map() if existing else {}
    values: list[dict] = []
    core_count = sum(1 for s in specs if s.is_core)
    extra_count = sum(1 for s in specs if not s.is_core)
    st.caption(
        f"{len(specs)} fields for {person_type} "
        f"({core_count} core · {extra_count} additional)"
    )

    known_keys = {section.key for section in sections}
    # Preserve fields whose section was removed/deactivated under Other.
    section_rows = [(section.key, section.label) for section in sections]
    if any(spec.section not in known_keys for spec in specs):
        section_rows.append(("__other__", "Other"))

    for section_key, section_label in section_rows:
        section_fields = [
            s
            for s in specs
            if (
                s.section == section_key
                if section_key != "__other__"
                else s.section not in known_keys
            )
        ]
        if not section_fields:
            continue
        st.markdown(f"#### {section_label}")
        # Two-column grid so the full catalog is visible without endless scroll.
        for i in range(0, len(section_fields), 2):
            row = section_fields[i : i + 2]
            cols = st.columns(2)
            for col, field in zip(cols, row):
                with col:
                    current = existing_values.get(field.key)
                    row_value = _render_field_input(
                        field, current, unit, key_prefix
                    )
                    if row_value:
                        values.append(row_value)

    notes = st.text_area(
        "Notes",
        value=existing.notes if existing else "",
        key=f"{key_prefix}_notes",
    )
    print_notes = st.text_input(
        "Print remarks",
        value=existing.print_notes if existing else "",
        key=f"{key_prefix}_print_notes",
    )

    save_label = "Update measurement" if existing else "Save measurement"
    if st.button(save_label, type="primary", key=f"{key_prefix}_save"):
        try:
            if existing:
                return measurement_service.update_record(
                    existing.id,
                    values=values,
                    wearer_name=wearer_name,
                    wearer_age=wearer_age,
                    wearer_height=wearer_height,
                    wearer_weight=wearer_weight,
                    unit=unit,
                    fit_preference=fit_preference,
                    notes=notes,
                    print_notes=print_notes,
                    measured_at=measured_at,
                    measured_by=measured_by,
                    order_id=order_id or existing.order_id,
                )
            return measurement_service.create_record(
                customer_id=customer_id,
                person_type=person_type,
                values=values,
                order_id=order_id,
                wearer_name=wearer_name,
                wearer_age=wearer_age,
                wearer_height=wearer_height,
                wearer_weight=wearer_weight,
                unit=unit,
                fit_preference=fit_preference,
                notes=notes,
                print_notes=print_notes,
                measured_at=measured_at,
                measured_by=measured_by,
            )
        except Exception as exc:
            st.error(str(exc))
    return None
