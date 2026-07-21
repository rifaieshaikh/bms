"""Projects settings — manage project templates (add / edit / remove)."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.domain.shared.enums import PlaceOfSupplyMode, ProjectBillingMode
from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler
from vaybooks.bms.ui.styles import render_card_grid


T_ADD = "prj_template_add_dialog"
T_EDIT = "prj_template_edit_dialog"
T_EDIT_ID = "prj_template_edit_id"
T_REMOVE = "prj_template_remove_dialog"
T_REMOVE_ID = "prj_template_remove_id"


def _parse_lines(raw: str) -> list[str]:
    return [line.strip() for line in (raw or "").splitlines() if line.strip()]


def _template_form(prefix: str, template=None) -> dict:
    name = st.text_input(
        "Template name",
        value=template.name if template else "",
        key=f"{prefix}_name",
    )
    description = st.text_area(
        "Description",
        value=template.description if template else "",
        key=f"{prefix}_desc",
    )
    c1, c2 = st.columns(2)
    phases_enabled = c1.checkbox(
        "Phases enabled",
        value=template.phases_enabled if template else True,
        key=f"{prefix}_phases_on",
    )
    max_depth = c2.number_input(
        "Max activity depth",
        min_value=1,
        max_value=10,
        value=int(template.max_activity_depth if template else 3),
        key=f"{prefix}_depth",
    )
    billing_opts = [m.value for m in ProjectBillingMode]
    billing_mode = st.selectbox(
        "Billing mode",
        options=billing_opts,
        index=billing_opts.index(template.billing_mode.value)
        if template and template.billing_mode.value in billing_opts
        else 0,
        key=f"{prefix}_billing",
    )
    c3, c4 = st.columns(2)
    retention_pct = c3.number_input(
        "Retention %",
        min_value=0.0,
        max_value=100.0,
        value=float(template.retention_pct if template else 0.0),
        key=f"{prefix}_ret",
    )
    default_rate = c4.number_input(
        "Default hourly rate",
        min_value=0.0,
        value=float(template.default_hourly_rate if template else 0.0),
        step=50.0,
        key=f"{prefix}_rate",
    )
    pos_opts = [m.value for m in PlaceOfSupplyMode]
    place_of_supply = st.selectbox(
        "Place of supply mode",
        options=pos_opts,
        index=pos_opts.index(template.place_of_supply_mode.value)
        if template and template.place_of_supply_mode.value in pos_opts
        else pos_opts.index(PlaceOfSupplyMode.SITE_STATE.value),
        key=f"{prefix}_pos",
    )
    default_phases = "\n".join(p.name for p in (template.phases if template else []))
    st.caption("Default phase names — one per line.")
    phase_raw = st.text_area(
        "Phases",
        value=default_phases,
        placeholder="e.g.\nDesign\nExecution\nHandover",
        key=f"{prefix}_phases",
    )
    return {
        "name": name,
        "description": description,
        "phases_enabled": phases_enabled,
        "max_activity_depth": int(max_depth),
        "billing_mode": ProjectBillingMode(billing_mode),
        "retention_pct": float(retention_pct),
        "default_hourly_rate": float(default_rate),
        "place_of_supply_mode": PlaceOfSupplyMode(place_of_supply),
        "phase_names": _parse_lines(phase_raw),
    }


@st.dialog("Add Project Template", width="large", on_dismiss=make_dismiss_handler(T_ADD))
def _add_template_dialog(projects_svc) -> None:
    data = _template_form("prj_tmpl_add")
    cols = st.columns(2)
    if cols[0].button("Cancel", use_container_width=True):
        st.session_state.pop(T_ADD, None)
        st.rerun()
    if cols[1].button("Create template", type="primary", use_container_width=True):
        try:
            projects_svc.create_template(
                data["name"],
                description=data["description"],
                phases_enabled=data["phases_enabled"],
                max_activity_depth=data["max_activity_depth"],
                billing_mode=data["billing_mode"],
                retention_pct=data["retention_pct"],
                place_of_supply_mode=data["place_of_supply_mode"],
                default_hourly_rate=data["default_hourly_rate"],
                phase_names=data["phase_names"],
            )
            st.session_state.pop(T_ADD, None)
            st.rerun()
        except (ValidationError, Exception) as exc:
            st.error(str(exc))


@st.dialog("Edit Project Template", width="large", on_dismiss=make_dismiss_handler(T_EDIT, T_EDIT_ID))
def _edit_template_dialog(projects_svc, template_id: str) -> None:
    template = projects_svc.get_template(template_id)
    if not template:
        st.error("Template not found")
        return
    if template.is_system:
        st.info("System template — you can adjust structure; name stays unique.")
    data = _template_form("prj_tmpl_edit", template)
    cols = st.columns(2)
    if cols[0].button("Cancel", use_container_width=True):
        st.session_state.pop(T_EDIT, None)
        st.session_state.pop(T_EDIT_ID, None)
        st.rerun()
    if cols[1].button("Save changes", type="primary", use_container_width=True):
        try:
            projects_svc.update_template(
                template_id,
                name=data["name"],
                description=data["description"],
                phases_enabled=data["phases_enabled"],
                max_activity_depth=data["max_activity_depth"],
                billing_mode=data["billing_mode"],
                retention_pct=data["retention_pct"],
                place_of_supply_mode=data["place_of_supply_mode"],
                default_hourly_rate=data["default_hourly_rate"],
                phase_names=data["phase_names"],
            )
            st.session_state.pop(T_EDIT, None)
            st.session_state.pop(T_EDIT_ID, None)
            st.rerun()
        except (ValidationError, Exception) as exc:
            st.error(str(exc))


@st.dialog("Remove Project Template", on_dismiss=make_dismiss_handler(T_REMOVE, T_REMOVE_ID))
def _remove_template_dialog(projects_svc, template_id: str) -> None:
    template = projects_svc.get_template(template_id)
    if not template:
        st.error("Template not found")
        return
    if template.is_system:
        st.error("System templates cannot be deleted.")
        if st.button("Close", use_container_width=True):
            st.session_state.pop(T_REMOVE, None)
            st.session_state.pop(T_REMOVE_ID, None)
            st.rerun()
        return
    st.write(f"Remove template **{template.name}**? This cannot be undone.")
    cols = st.columns(2)
    if cols[0].button("Cancel", use_container_width=True):
        st.session_state.pop(T_REMOVE, None)
        st.session_state.pop(T_REMOVE_ID, None)
        st.rerun()
    if cols[1].button("Remove", type="primary", use_container_width=True):
        try:
            projects_svc.delete_template(template_id)
            st.session_state.pop(T_REMOVE, None)
            st.session_state.pop(T_REMOVE_ID, None)
            st.rerun()
        except (ValidationError, Exception) as exc:
            st.error(str(exc))


def render(services: dict) -> None:
    projects_svc = services.get("projects")
    if projects_svc is None:
        st.warning("Projects service is not configured.")
        return

    st.header("Project Settings")
    st.info(
        "Manage the Project Activities catalog under **Settings → Project Activities**. "
        "Add activities to projects from the catalog on each project's Work tab."
    )
    st.caption("Open **Settings → Project Activities** from the sidebar to configure the catalog.")

    st.subheader("Project templates")
    st.caption(
        "Templates supply default phases and billing settings when creating new projects. "
        "Activities are added from the catalog after project creation."
    )

    if st.button("Add template", type="primary", key="prj_tmpl_add_btn"):
        st.session_state[T_ADD] = True
        st.rerun()

    try:
        templates = projects_svc.list_templates()
    except Exception as exc:
        st.error(str(exc))
        return

    if not templates:
        st.info("No templates yet. Add one to use when creating projects.")
    else:

        def _render_card(template, _i):
            with st.container(border=True):
                top = st.columns([4, 1, 1])
                top[0].markdown(f"**{template.name}**")
                kind = "System" if template.is_system else "Custom"
                top[0].caption(
                    f"{kind} · {len(template.phases)} phases · "
                    f"{len(template.activities)} legacy activities · {template.billing_mode.value}"
                )
                if template.description:
                    st.write(template.description)
                if top[1].button(
                    "Edit",
                    key=f"prj_tmpl_edit_{template.id}",
                    use_container_width=True,
                ):
                    st.session_state[T_EDIT] = True
                    st.session_state[T_EDIT_ID] = template.id
                    st.rerun()
                if top[2].button(
                    "Remove",
                    key=f"prj_tmpl_rm_{template.id}",
                    use_container_width=True,
                    disabled=bool(template.is_system),
                ):
                    st.session_state[T_REMOVE] = True
                    st.session_state[T_REMOVE_ID] = template.id
                    st.rerun()

        render_card_grid(
            sorted(templates, key=lambda t: (not t.is_system, t.name.lower())),
            _render_card,
            suffix="prj_templates",
        )

    if st.session_state.get(T_ADD):
        _add_template_dialog(projects_svc)
    if st.session_state.get(T_EDIT) and st.session_state.get(T_EDIT_ID):
        _edit_template_dialog(projects_svc, st.session_state[T_EDIT_ID])
    if st.session_state.get(T_REMOVE) and st.session_state.get(T_REMOVE_ID):
        _remove_template_dialog(projects_svc, st.session_state[T_REMOVE_ID])
