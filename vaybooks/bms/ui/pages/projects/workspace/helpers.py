"""Shared helpers for Project Workspace UI."""

from __future__ import annotations

from typing import Callable, Optional

import streamlit as st

from vaybooks.bms.domain.shared.enums import ProjectActivityStatus
from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.ui.styles import status_badge


WORKSPACE_ID = "project_workspace_id"
WORKSPACE_TAB = "project_workspace_tab"
WORK_SELECTED_ACTIVITY = "prj_work_selected_activity"
BILLING_SUBTAB = "prj_billing_subtab"

TABS = [
    "Overview",
    "Work",
    "BOQ",
    "Budget",
    "Time",
    "Costs",
    "Billing",
    "Money",
    "Documents",
    "Profit",
    "Settings",
]

BILLING_SUBTABS = [
    "Quotations",
    "Work Orders",
    "Measurements",
    "RA Bills",
    "Tax Invoices",
    "Proforma",
    "Variations",
]


def set_tab(tab: str) -> None:
    st.session_state[WORKSPACE_TAB] = tab


def go_tab(tab: str) -> None:
    set_tab(tab)
    st.rerun()


def empty_state(message: str, *, cta: str | None = None, cta_key: str | None = None) -> bool:
    """Show empty message; return True if CTA clicked."""
    st.info(message)
    if cta and cta_key:
        return st.button(cta, type="primary", key=cta_key)
    return False


def run_action(fn: Callable, success: str = "Saved") -> None:
    try:
        fn()
        st.success(success)
        st.rerun()
    except ValidationError as exc:
        st.error(str(exc))
    except Exception as exc:
        st.error(str(exc))


def activity_depth_map(project) -> dict[str, int]:
    by_id = {a.id: a for a in project.activities}
    depths: dict[str, int] = {}

    def depth(aid: str) -> int:
        if aid in depths:
            return depths[aid]
        act = by_id.get(aid)
        if not act or not act.parent_activity_id:
            depths[aid] = 0
        else:
            depths[aid] = depth(act.parent_activity_id) + 1
        return depths[aid]

    for a in project.activities:
        depth(a.id)
    return depths


def leaf_activities(project) -> list:
    parent_ids = {a.parent_activity_id for a in project.activities if a.parent_activity_id}
    return [a for a in project.activities if a.id not in parent_ids]


def has_children(project, activity_id: str) -> bool:
    return any(a.parent_activity_id == activity_id for a in project.activities)


def activity_tree_options(
    project,
    *,
    leaves_only: bool = False,
    include_blank: bool = False,
    blank_label: str = "— None —",
) -> dict[str, Optional[str]]:
    """Ordered label -> activity_id map with indentation."""
    depths = activity_depth_map(project)
    activities = sorted(project.activities, key=lambda a: (depths.get(a.id, 0), a.sort_order, a.name))
    if leaves_only:
        leaves = {a.id for a in leaf_activities(project)}
        activities = [a for a in activities if a.id in leaves]
    options: dict[str, Optional[str]] = {}
    if include_blank:
        options[blank_label] = None
    for a in activities:
        indent = "  " * depths.get(a.id, 0)
        prefix = "└ " if depths.get(a.id, 0) > 0 else ""
        label = f"{indent}{prefix}{a.name}"
        # Ensure unique labels
        if label in options:
            label = f"{label} ({a.id[:6]})"
        options[label] = a.id
    return options


def activity_label(project, activity_id: str) -> str:
    for a in project.activities:
        if a.id == activity_id:
            return a.name
    return activity_id or "—"


def status_actions(current_status: str, actions: list[tuple[str, str, Callable]]) -> None:
    """actions: list of (label, allowed_when_status, callback). Only matching status shown."""
    visible = [(label, cb) for label, when, cb in actions if when == current_status]
    if not visible:
        return
    cols = st.columns(max(len(visible), 1))
    for i, (label, cb) in enumerate(visible):
        if cols[i].button(label, key=f"status_act_{current_status}_{label}_{i}"):
            run_action(cb, success=label)


def render_badge(status_value: str) -> None:
    st.markdown(status_badge(status_value), unsafe_allow_html=True)


def fmt_money(value) -> str:
    if value is None:
        return "—"
    return f"₹{float(value):,.0f}"


def fmt_hours(value) -> str:
    if value is None:
        return "—"
    return f"{float(value):,.1f}h"


def dynamic_line_editor(
    key_prefix: str,
    *,
    initial_lines: list[dict] | None = None,
    project=None,
    max_lines: int = 20,
) -> list[dict]:
    """Session-backed dynamic BOQ lines. Returns list of line dicts."""
    state_key = f"{key_prefix}_lines"
    if state_key not in st.session_state:
        st.session_state[state_key] = list(initial_lines or []) or [
            {"description": "", "quantity": 1.0, "rate": 0.0, "discount_pct": 0.0, "hsn_sac": "", "activity_id": None}
        ]

    lines: list[dict] = st.session_state[state_key]
    act_opts = activity_tree_options(project, include_blank=True) if project else {}

    for idx, line in enumerate(lines):
        st.markdown(f"**Line {idx + 1}**")
        c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
        line["description"] = c1.text_input(
            "Description",
            value=line.get("description") or "",
            key=f"{key_prefix}_desc_{idx}",
        )
        line["quantity"] = c2.number_input(
            "Qty",
            min_value=0.0,
            value=float(line.get("quantity") or 1.0),
            key=f"{key_prefix}_qty_{idx}",
        )
        line["rate"] = c3.number_input(
            "Rate",
            min_value=0.0,
            value=float(line.get("rate") or 0.0),
            key=f"{key_prefix}_rate_{idx}",
            step=100.0,
        )
        line["discount_pct"] = c4.number_input(
            "Disc %",
            min_value=0.0,
            max_value=100.0,
            value=float(line.get("discount_pct") or 0.0),
            key=f"{key_prefix}_disc_{idx}",
        )
        c5, c6, c7 = st.columns([2, 3, 1])
        line["hsn_sac"] = c5.text_input(
            "HSN/SAC",
            value=line.get("hsn_sac") or "",
            key=f"{key_prefix}_hsn_{idx}",
        )
        if act_opts:
            # reverse map current activity_id to label
            id_to_label = {v: k for k, v in act_opts.items()}
            current = id_to_label.get(line.get("activity_id"), list(act_opts.keys())[0])
            labels = list(act_opts.keys())
            try:
                cur_idx = labels.index(current)
            except ValueError:
                cur_idx = 0
            picked = c6.selectbox(
                "Activity",
                options=labels,
                index=cur_idx,
                key=f"{key_prefix}_act_{idx}",
            )
            line["activity_id"] = act_opts[picked]
        if c7.button("Remove", key=f"{key_prefix}_rm_{idx}"):
            lines.pop(idx)
            st.session_state[state_key] = lines
            st.rerun()

    btn_cols = st.columns(2)
    if btn_cols[0].button("Add line", key=f"{key_prefix}_add") and len(lines) < max_lines:
        lines.append(
            {
                "description": "",
                "quantity": 1.0,
                "rate": 0.0,
                "discount_pct": 0.0,
                "hsn_sac": "",
                "activity_id": None,
            }
        )
        st.session_state[state_key] = lines
        st.rerun()

    st.session_state[state_key] = lines
    return [
        {
            "description": (ln.get("description") or "").strip(),
            "quantity": float(ln.get("quantity") or 0),
            "rate": float(ln.get("rate") or 0),
            "discount_pct": float(ln.get("discount_pct") or 0),
            "hsn_sac": (ln.get("hsn_sac") or "").strip(),
            "activity_id": ln.get("activity_id"),
            # sales invoice path also accepts qty
            "qty": float(ln.get("quantity") or 0),
        }
        for ln in lines
        if (ln.get("description") or "").strip()
    ]


def reset_line_editor(key_prefix: str, lines: list[dict] | None = None) -> None:
    st.session_state[f"{key_prefix}_lines"] = list(lines or [])


def activity_status_options() -> list[str]:
    return [s.value for s in ProjectActivityStatus]
