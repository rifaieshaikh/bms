"""Access — Plans: card list with create/edit/delete and apply."""

from __future__ import annotations

from collections import defaultdict

import streamlit as st

from vaybooks.bms.domain.entitlements.catalog import (
    ALL_MODULES,
    MODULE_LABELS,
    expand_modules,
    module_key,
    permission_module,
)
from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.ui.auth.guard import require_page_access
from vaybooks.bms.ui.components.common.list_view import render_list
from vaybooks.bms.ui.dialog_utils import (
    clear_all_dialog_flags,
    clear_dialog_flags,
    make_dismiss_handler,
)
from vaybooks.bms.ui.filtering import FilterField, ListSchema, SortOption
from vaybooks.bms.ui import filtering as F
from vaybooks.bms.ui.pagination import CARD_PAGE_SIZE
from vaybooks.bms.ui.styles import render_card_grid, status_badge

EDIT_FLAG = "access_plan_edit_flag"
DELETE_FLAG = "access_plan_delete_flag"
VIEW_FLAG = "access_plan_view_flag"
APPLY_FLAG = "access_plan_apply_flag"

_LOCKOUT_KEYS = ("settings.plans.view", "settings.plans.manage")


def _lacks_plans_access(plan) -> bool:
    keys = set(plan.feature_keys or [])
    return not keys.intersection(_LOCKOUT_KEYS)


def _module_selection_to_keys(modules: list, extra_keys: list) -> list:
    keys = set(expand_modules(modules))
    keys.update(extra_keys or [])
    return sorted(keys)


def _keys_to_module_selection(feature_keys: list) -> tuple[list, list]:
    keys = set(feature_keys or [])
    modules = []
    for m in ALL_MODULES:
        if module_key(m) in keys and expand_modules([m]) <= keys:
            modules.append(m)
    covered = set(expand_modules(modules))
    extras = sorted(keys - covered)
    return modules, extras


def _feature_summary(plan) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for key in plan.feature_keys or []:
        counts[permission_module(key)] += 1
    return dict(sorted(counts.items()))


def _match_kind(plan, value) -> bool:
    want_system = value == "system"
    return bool(getattr(plan, "is_system", False)) is want_system


PLANS = ListSchema(
    entity_key="access_plans",
    title="Plans",
    filter_fields=[
        FilterField("name", "Name", F.REGEX),
        FilterField(
            "kind",
            "Type",
            F.SELECT,
            options=[("system", "Built-in"), ("custom", "Custom")],
            match=_match_kind,
        ),
    ],
    sort_options=[
        SortOption("name", "Name"),
        SortOption("updated_at", "Updated"),
    ],
    default_sort="name",
    default_desc=False,
    page_size=CARD_PAGE_SIZE,
)


def _plan_form_fields(*, name="", description="", modules=None, extras=None):
    name = st.text_input("Name", value=name)
    description = st.text_input("Description", value=description)
    modules = st.multiselect(
        "Modules (all permissions under each selected module)",
        options=list(ALL_MODULES),
        default=modules or [],
        format_func=lambda m: MODULE_LABELS.get(m, m),
    )
    with st.expander("Fine-tune: extra individual permissions", expanded=bool(extras)):
        from vaybooks.bms.domain.entitlements.catalog import PERMISSIONS

        extras = st.multiselect(
            "Extra permissions (beyond selected modules)",
            options=list(PERMISSIONS),
            default=extras or [],
        )
    return name, description, modules, extras


@st.dialog("Create Plan", width="large")
def _create_plan_dialog(services: dict) -> None:
    plans_svc = services["plans"]
    plans = plans_svc.list_plans()
    clone_from = st.selectbox(
        "Start from (optional)",
        options=[""] + [p.id for p in plans],
        format_func=lambda pid: (
            "(blank)" if not pid else next(p.name for p in plans if p.id == pid)
        ),
    )
    clone_modules, clone_extras = [], []
    if clone_from:
        source = next(p for p in plans if p.id == clone_from)
        clone_modules, clone_extras = _keys_to_module_selection(source.feature_keys)
    with st.form("access_plan_create_form"):
        name, description, modules, extras = _plan_form_fields(
            modules=clone_modules, extras=clone_extras
        )
        if st.form_submit_button("Create plan", type="primary"):
            try:
                plans_svc.create_plan(
                    name=name,
                    description=description,
                    feature_keys=_module_selection_to_keys(modules, extras),
                )
                st.rerun()
            except ValidationError as exc:
                st.error(str(exc))


@st.dialog("Edit Plan", width="large", on_dismiss=make_dismiss_handler(EDIT_FLAG))
def _edit_plan_dialog(services: dict, plan) -> None:
    cur_modules, cur_extras = _keys_to_module_selection(plan.feature_keys)
    with st.form("access_plan_edit_form"):
        name, description, modules, extras = _plan_form_fields(
            name=plan.name,
            description=plan.description,
            modules=cur_modules,
            extras=cur_extras,
        )
        if st.form_submit_button("Save plan", type="primary"):
            try:
                services["plans"].update_plan(
                    plan.id,
                    name=name,
                    description=description,
                    feature_keys=_module_selection_to_keys(modules, extras),
                )
                clear_dialog_flags(EDIT_FLAG)
                st.rerun()
            except ValidationError as exc:
                st.error(str(exc))


@st.dialog("Delete Plan", on_dismiss=make_dismiss_handler(DELETE_FLAG))
def _delete_plan_dialog(services: dict, plan) -> None:
    st.write(f"Delete plan **{plan.name}**? This cannot be undone.")
    col_yes, col_no = st.columns(2)
    if col_yes.button("Delete", type="primary", use_container_width=True):
        try:
            services["plans"].delete_plan(plan.id)
            clear_dialog_flags(DELETE_FLAG)
            st.rerun()
        except ValidationError as exc:
            st.error(str(exc))
    if col_no.button("Cancel", use_container_width=True):
        clear_dialog_flags(DELETE_FLAG)
        st.rerun()


@st.dialog("Plan details", on_dismiss=make_dismiss_handler(VIEW_FLAG))
def _view_plan_dialog(plan) -> None:
    kind = "Built-in" if plan.is_system else "Custom"
    st.markdown(f"**{plan.name}**")
    st.caption(f"{kind} · {len(plan.feature_keys or [])} features")
    if plan.description:
        st.write(plan.description)
    if _lacks_plans_access(plan):
        st.warning(
            "This plan does not include Plans access (settings.plans.view). "
            "If applied, plans cannot be changed back from the UI."
        )
    summary = _feature_summary(plan)
    if not summary:
        st.info("No features on this plan.")
        return
    for module, count in summary.items():
        with st.expander(f"{module} ({count})", expanded=False):
            keys = sorted(
                k for k in (plan.feature_keys or []) if permission_module(k) == module
            )
            st.code("\n".join(keys), language=None)


@st.dialog("Apply plan", on_dismiss=make_dismiss_handler(APPLY_FLAG))
def _apply_plan_dialog(services: dict, plan) -> None:
    st.write(f"Switch the organisation to **{plan.name}**?")
    if _lacks_plans_access(plan):
        st.warning(
            "This plan does not include Plans access. You may not be able to "
            "change plans again from the UI after applying it."
        )
    col_yes, col_no = st.columns(2)
    if col_yes.button("Apply", type="primary", use_container_width=True):
        try:
            services["plans"].set_plan(plan.id)
            clear_dialog_flags(APPLY_FLAG)
            st.rerun()
        except ValidationError as exc:
            st.error(str(exc))
    if col_no.button("Cancel", use_container_width=True):
        clear_dialog_flags(APPLY_FLAG)
        st.rerun()


def _plan_card(plan, active_plan_id: str, index: int) -> None:
    is_active = plan.id == active_plan_id
    with st.container(border=True):
        st.markdown(f"**{plan.name}**")
        badges = []
        if is_active:
            badges.append(status_badge("Active", "green", compact=True))
        kind = "Built-in" if plan.is_system else "Custom"
        badges.append(
            status_badge(kind, "blue" if plan.is_system else "violet", compact=True)
        )
        st.markdown(" ".join(badges), unsafe_allow_html=True)
        st.caption(plan.description or "—")
        st.caption(f"{len(plan.feature_keys or [])} features")

        if is_active:
            if st.button(
                "View",
                key=f"access_plan_view_{index}_{plan.id}",
                use_container_width=True,
            ):
                clear_all_dialog_flags()
                st.session_state[VIEW_FLAG] = plan.id
                st.rerun()
        else:
            b1, b2 = st.columns(2)
            if b1.button(
                "Apply",
                key=f"access_plan_apply_{index}_{plan.id}",
                use_container_width=True,
            ):
                clear_all_dialog_flags()
                st.session_state[APPLY_FLAG] = plan.id
                st.rerun()
            if b2.button(
                "View",
                key=f"access_plan_view_{index}_{plan.id}",
                use_container_width=True,
            ):
                clear_all_dialog_flags()
                st.session_state[VIEW_FLAG] = plan.id
                st.rerun()
            if not plan.is_system:
                e1, e2 = st.columns(2)
                if e1.button(
                    "Edit",
                    key=f"access_plan_edit_{index}_{plan.id}",
                    use_container_width=True,
                ):
                    clear_all_dialog_flags()
                    st.session_state[EDIT_FLAG] = plan.id
                    st.rerun()
                if e2.button(
                    "Delete",
                    key=f"access_plan_del_{index}_{plan.id}",
                    use_container_width=True,
                ):
                    clear_all_dialog_flags()
                    st.session_state[DELETE_FLAG] = plan.id
                    st.rerun()


def _load_plans(services, filters, sort):
    try:
        return services["plans"].list_plans()
    except Exception:
        return []


def _render_cards(page_plans, services):
    active_id = services["plans"].get_org_entitlement().plan_id
    render_card_grid(
        page_plans,
        lambda plan, i: _plan_card(plan, active_id, i),
        suffix="access_plans",
        card_min_width=240,
    )


def render(services: dict):
    if not require_page_access(services, "plans-settings"):
        return

    plans_svc = services["plans"]
    ent = plans_svc.get_org_entitlement()
    current = plans_svc.get_plan(ent.plan_id)
    st.caption(
        f"Current plan: **{current.name if current else ent.plan_id}**"
        + (f" — {current.description}" if current and current.description else "")
    )

    bar = render_list(
        PLANS,
        services=services,
        load_fn=_load_plans,
        card_renderer=_render_cards,
        primary_label="Create Plan",
        primary_key="access_plans_add_btn",
        count_label="plans",
        empty_text="No plans found.",
        page_key_nav="plans_settings",
    )
    if bar.get("primary_clicked"):
        clear_all_dialog_flags()
        _create_plan_dialog(services)

    for flag, dialog in (
        (VIEW_FLAG, lambda p: _view_plan_dialog(p)),
        (APPLY_FLAG, lambda p: _apply_plan_dialog(services, p)),
        (EDIT_FLAG, lambda p: _edit_plan_dialog(services, p)),
        (DELETE_FLAG, lambda p: _delete_plan_dialog(services, p)),
    ):
        pending_id = st.session_state.get(flag)
        if not pending_id:
            continue
        plan = plans_svc.get_plan(pending_id)
        if plan is None:
            clear_dialog_flags(flag)
            break
        if flag in (EDIT_FLAG, DELETE_FLAG) and plan.is_system:
            clear_dialog_flags(flag)
            break
        dialog(plan)
        break
