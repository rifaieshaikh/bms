"""Multi-step project configuration wizard (Wave 2 commercial)."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.domain.shared.enums import (
    ProjectArchetype,
    ProjectBillingMode,
    ProjectScaleProfile,
)
from vaybooks.bms.domain.shared.india import INDIAN_STATES
from vaybooks.bms.ui.components.project_card import WORKSPACE_ID
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler
from vaybooks.bms.ui import navigation

CREATE_DIALOG = "project_create_dialog"
WIZARD_STEP = "prj_wizard_step"
WIZARD_DATA = "prj_wizard_data"

_MODULE_OPTIONS = [
    "BOQ",
    "Budget",
    "Time",
    "Costs",
    "Procurement",
    "Billing",
    "Quality",
    "DPR",
    "Documents",
]

_EXECUTION_MODELS = [
    "Self-perform",
    "Subcontract-led",
    "Hybrid delivery",
]

_STRUCTURE_DEPTHS = {
    "Shallow (phases only)": 1,
    "Standard (phase → activity)": 2,
    "Deep (phase → package → activity → task)": 4,
}


def _load_templates(services: dict) -> list:
    svc = services.get("projects")
    if svc is None:
        return []
    loader = getattr(svc, "list_templates", None)
    if callable(loader):
        try:
            return loader()
        except Exception:
            return []
    return []


def _open_workspace(project_id: str) -> None:
    st.session_state[WORKSPACE_ID] = project_id
    navigation.go_to_list("project_workspace", project=project_id)


def _wizard_data() -> dict:
    if WIZARD_DATA not in st.session_state:
        st.session_state[WIZARD_DATA] = {
            "archetype": ProjectArchetype.CUSTOM.value,
            "scale": ProjectScaleProfile.SMALL.value,
            "execution_model": _EXECUTION_MODELS[0],
            "billing_mode": ProjectBillingMode.FIXED.value,
            "structure_depth_label": list(_STRUCTURE_DEPTHS.keys())[1],
            "modules": ["BOQ", "Budget", "Billing"],
            "name": "",
            "customer_label": "",
            "site_address": "",
            "site_state_label": "",
            "contract_value": 0.0,
            "template_name": "",
        }
    return st.session_state[WIZARD_DATA]


def _set_step(step: int) -> None:
    st.session_state[WIZARD_STEP] = step


def _nav_row(step: int, *, can_next: bool = True) -> None:
    cols = st.columns(3)
    if cols[0].button("Cancel", key=f"wiz_cancel_{step}", use_container_width=True):
        st.session_state.pop(CREATE_DIALOG, None)
        st.session_state.pop(WIZARD_STEP, None)
        st.session_state.pop(WIZARD_DATA, None)
        st.rerun()
    if step > 0 and cols[1].button("Back", key=f"wiz_back_{step}", use_container_width=True):
        _set_step(step - 1)
        st.rerun()
    if can_next and cols[2].button(
        "Next", type="primary", key=f"wiz_next_{step}", use_container_width=True
    ):
        _set_step(step + 1)
        st.rerun()


def _step_archetype(data: dict) -> None:
    st.markdown("**Step 1 — Project archetype**")
    st.caption("Choose the commercial shape that drives defaults and modules.")
    cols = st.columns(2)
    options = [a.value for a in ProjectArchetype]
    for idx, label in enumerate(options):
        with cols[idx % 2]:
            selected = data["archetype"] == label
            if st.button(
                f"{'✓ ' if selected else ''}{label}",
                key=f"wiz_arch_{idx}",
                use_container_width=True,
                type="primary" if selected else "secondary",
            ):
                data["archetype"] = label
                st.rerun()
    _nav_row(0, can_next=bool(data.get("archetype")))


def _step_scale(data: dict) -> None:
    st.markdown("**Step 2 — Scale profile**")
    data["scale"] = st.radio(
        "Scale",
        options=[s.value for s in ProjectScaleProfile],
        index=[s.value for s in ProjectScaleProfile].index(data["scale"]),
        key="wiz_scale",
        horizontal=True,
    )
    _nav_row(1)


def _step_execution(data: dict) -> None:
    st.markdown("**Step 3 — Execution model**")
    data["execution_model"] = st.selectbox(
        "How will work be delivered?",
        options=_EXECUTION_MODELS,
        index=_EXECUTION_MODELS.index(data["execution_model"])
        if data["execution_model"] in _EXECUTION_MODELS
        else 0,
        key="wiz_exec",
    )
    _nav_row(2)


def _step_billing(data: dict) -> None:
    st.markdown("**Step 4 — Billing mode**")
    modes = [m.value for m in ProjectBillingMode]
    data["billing_mode"] = st.selectbox(
        "Billing mode",
        options=modes,
        index=modes.index(data["billing_mode"]) if data["billing_mode"] in modes else 0,
        key="wiz_billing",
    )
    st.caption(
        "Includes Milestone, Unit/BOQ, Cost Plus, and Hybrid alongside Fixed / T&M / RA."
    )
    _nav_row(3)


def _step_structure(data: dict) -> None:
    st.markdown("**Step 5 — Structure depth**")
    labels = list(_STRUCTURE_DEPTHS.keys())
    current = data.get("structure_depth_label") or labels[1]
    if current not in labels:
        current = labels[1]
    data["structure_depth_label"] = st.selectbox(
        "WBS / activity depth",
        options=labels,
        index=labels.index(current),
        key="wiz_depth",
    )
    _nav_row(4)


def _step_modules(data: dict) -> None:
    st.markdown("**Step 6 — Modules**")
    data["modules"] = st.multiselect(
        "Enable modules",
        options=_MODULE_OPTIONS,
        default=[m for m in data.get("modules") or [] if m in _MODULE_OPTIONS]
        or ["BOQ", "Budget", "Billing"],
        key="wiz_modules",
    )
    _nav_row(5)


def _step_preview(data: dict, services: dict) -> None:
    st.markdown("**Step 7 — Preview & details**")
    templates = _load_templates(services)
    template_options = {t.name: t.id for t in templates}
    customers = services["customers"].list_all_customers()
    customer_labels = {c.customer_name: c.id for c in customers}
    state_labels = [f"{s['code']} — {s['name']}" for s in INDIAN_STATES]

    data["name"] = st.text_input("Project name", value=data.get("name") or "", key="wiz_name")
    data["customer_label"] = st.selectbox(
        "Customer",
        options=[""] + list(customer_labels.keys()),
        index=(
            list(customer_labels.keys()).index(data["customer_label"]) + 1
            if data.get("customer_label") in customer_labels
            else 0
        ),
        key="wiz_customer",
    )
    data["site_address"] = st.text_area(
        "Site address", value=data.get("site_address") or "", key="wiz_site"
    )
    data["site_state_label"] = st.selectbox(
        "Site state",
        options=[""] + state_labels,
        index=(
            state_labels.index(data["site_state_label"]) + 1
            if data.get("site_state_label") in state_labels
            else 0
        ),
        key="wiz_state",
    )
    data["contract_value"] = st.number_input(
        "Contract value",
        min_value=0.0,
        value=float(data.get("contract_value") or 0.0),
        step=1000.0,
        key="wiz_contract",
    )
    if template_options:
        names = list(template_options.keys())
        data["template_name"] = st.selectbox(
            "Template (optional)",
            options=[""] + names,
            index=(
                names.index(data["template_name"]) + 1
                if data.get("template_name") in template_options
                else 0
            ),
            key="wiz_template",
        )
    else:
        data["template_name"] = ""

    st.info(
        f"**{data.get('archetype')}** · {data.get('scale')} · "
        f"{data.get('billing_mode')} · {data.get('execution_model')} · "
        f"depth {_STRUCTURE_DEPTHS.get(data.get('structure_depth_label'), 3)} · "
        f"modules: {', '.join(data.get('modules') or []) or '—'}"
    )
    _nav_row(6, can_next=bool((data.get("name") or "").strip() and data.get("customer_label")))


def _step_confirm(data: dict, services: dict) -> None:
    st.markdown("**Step 8 — Confirm**")
    st.write(
        {
            "Archetype": data.get("archetype"),
            "Scale": data.get("scale"),
            "Execution model": data.get("execution_model"),
            "Billing mode": data.get("billing_mode"),
            "Structure depth": data.get("structure_depth_label"),
            "Modules": data.get("modules"),
            "Name": data.get("name"),
            "Customer": data.get("customer_label"),
            "Template": data.get("template_name") or "(blank)",
            "Contract value": data.get("contract_value"),
        }
    )
    cols = st.columns(3)
    if cols[0].button("Cancel", key="wiz_cancel_final", use_container_width=True):
        st.session_state.pop(CREATE_DIALOG, None)
        st.session_state.pop(WIZARD_STEP, None)
        st.session_state.pop(WIZARD_DATA, None)
        st.rerun()
    if cols[1].button("Back", key="wiz_back_final", use_container_width=True):
        _set_step(6)
        st.rerun()
    if cols[2].button("Create project", type="primary", key="wiz_confirm", use_container_width=True):
        _create_from_wizard(data, services)


def _create_from_wizard(data: dict, services: dict) -> None:
    name = (data.get("name") or "").strip()
    if not name:
        st.error("Project name is required")
        return
    customers = services["customers"].list_all_customers()
    customer_labels = {c.customer_name: c.id for c in customers}
    customer_label = data.get("customer_label") or ""
    if customer_label not in customer_labels:
        st.error("Customer is required")
        return
    customer_id = customer_labels[customer_label]
    state_labels = [f"{s['code']} — {s['name']}" for s in INDIAN_STATES]
    code_by_label = {label: s["code"] for label, s in zip(state_labels, INDIAN_STATES)}
    site_state_code = code_by_label.get(data.get("site_state_label") or "", "")
    templates = _load_templates(services)
    template_options = {t.name: t.id for t in templates}
    template_id = template_options.get(data.get("template_name") or "")
    depth = _STRUCTURE_DEPTHS.get(data.get("structure_depth_label") or "", 3)
    billing_mode = ProjectBillingMode(data.get("billing_mode") or ProjectBillingMode.FIXED.value)
    archetype = data.get("archetype") or ProjectArchetype.CUSTOM.value
    scale = data.get("scale") or ProjectScaleProfile.SMALL.value
    modules = list(data.get("modules") or [])
    execution_model = data.get("execution_model") or _EXECUTION_MODELS[0]
    contract_value = float(data.get("contract_value") or 0.0)

    try:
        projects_svc = services["projects"]
        if template_id:
            project = projects_svc.create_project_from_template(
                template_id,
                name,
                customer_id,
                contract_value,
                site_address=data.get("site_address") or "",
                site_state_code=site_state_code,
            )
        else:
            project = projects_svc.create_project(
                name,
                customer_id,
                contract_value,
                site_address=data.get("site_address") or "",
                site_state_code=site_state_code,
            )
        projects_svc.update_project_settings(
            project.id,
            billing_mode=billing_mode,
            max_activity_depth=depth,
            archetype=archetype,
            scale_profile=scale,
        )
        quality = services.get("project_quality_config")
        if quality is not None:
            quality.publish_config_snapshot(
                project.id,
                archetype=archetype,
                scale=scale,
                modules=modules,
                workflow={"execution_model": execution_model},
                change_reason="Initial configuration from project wizard",
            )
        st.session_state.pop(CREATE_DIALOG, None)
        st.session_state.pop(WIZARD_STEP, None)
        st.session_state.pop(WIZARD_DATA, None)
        _open_workspace(project.id)
    except Exception as exc:
        st.error(str(exc))


@st.dialog(
    "New Project",
    width="large",
    on_dismiss=make_dismiss_handler(CREATE_DIALOG, WIZARD_STEP, WIZARD_DATA),
)
def render_project_wizard(services: dict) -> None:
    """Multi-step commercial configuration wizard replacing the simple create dialog."""
    step = int(st.session_state.get(WIZARD_STEP, 0) or 0)
    data = _wizard_data()
    st.progress(min((step + 1) / 8.0, 1.0), text=f"Step {step + 1} of 8")

    steps = [
        _step_archetype,
        _step_scale,
        _step_execution,
        _step_billing,
        _step_structure,
        _step_modules,
        lambda d: _step_preview(d, services),
        lambda d: _step_confirm(d, services),
    ]
    if step < 0 or step >= len(steps):
        step = 0
        _set_step(0)
    steps[step](data)
