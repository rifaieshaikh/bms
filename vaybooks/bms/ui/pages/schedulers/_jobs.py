"""Jobs section of a domain Schedulers page."""

from __future__ import annotations

from typing import Any, Dict, List

import streamlit as st

from vaybooks.bms.domain.schedulers.entities import SchedulerJobConfig
from vaybooks.bms.domain.schedulers.time import format_business
from vaybooks.bms.ui.pages.schedulers._common import (
    actor_id,
    render_domain_summary,
    render_recent_runs,
    schedule_controls,
    show_outcome,
)

# Rule fields the editor knows how to render, keyed by config attribute.
_RULE_LABELS: Dict[str, str] = {
    "threshold_days": "Threshold (days)",
    "warning_days": "Warn ahead (days)",
    "grace_days": "Grace (days)",
    "minimum_amount": "Minimum amount",
    "reminder_offsets_days": "Reminder offsets (days, comma separated)",
}


def render_jobs_section(
    services: dict,
    service,
    *,
    domain: str,
    may_run: bool,
    may_edit: bool,
) -> None:
    configs = render_domain_summary(service, domain)
    if not configs:
        st.info("No schedulers are registered for this module yet.")
        return

    action_left, action_right = st.columns([1, 3])
    with action_left:
        if st.button(
            "Run all in this domain",
            key=f"sched_{domain}_run_domain",
            disabled=not may_run,
            width="stretch",
            icon=":material/play_arrow:",
        ):
            show_outcome(service.run_domain(domain, actor_id=actor_id(services)))

    by_title = {f"{c.title or c.job_id}": c for c in configs}
    chosen_title = st.selectbox(
        "Scheduler",
        list(by_title.keys()),
        key=f"sched_{domain}_job_pick",
    )
    config = by_title[chosen_title]
    _render_job_editor(
        services, service, config, domain=domain, may_run=may_run, may_edit=may_edit
    )

    st.divider()
    st.subheader("Recent runs")
    render_recent_runs(service, domain)


def _render_job_editor(
    services: dict,
    service,
    config: SchedulerJobConfig,
    *,
    domain: str,
    may_run: bool,
    may_edit: bool,
) -> None:
    prefix = f"sched_{domain}_{config.job_id}"
    if config.description:
        st.caption(config.description)

    running = service.is_running(config.job_id)
    if running:
        st.info("This scheduler is running right now.")
    st.caption(
        f"Last run: {(config.last_status or 'never run').replace('_', ' ')} · "
        f"{format_business(config.last_run_at)} · Next eligible: "
        f"{format_business(service.next_due_at(config))}"
    )
    if config.last_error:
        st.warning(config.last_error)

    enabled = st.toggle(
        "Enabled", value=config.enabled, key=f"{prefix}_enabled", disabled=not may_edit
    )
    spec = schedule_controls(
        key_prefix=prefix,
        frequency=config.frequency,
        time_of_day=config.time_of_day,
        weekday=config.weekday,
        interval_days=config.interval_days,
        disabled=not may_edit,
    )

    definition = service.registry.definition(config.job_id)
    rule_fields = list(getattr(definition, "rule_fields", []) or [])
    rule_values = _render_rule_fields(prefix, config, rule_fields, disabled=not may_edit)

    with st.expander("Processing and delivery"):
        col_a, col_b, col_c = st.columns(3)
        batch_size = int(
            col_a.number_input(
                "Batch size",
                min_value=1,
                max_value=1000,
                value=int(config.batch_size),
                key=f"{prefix}_batch",
                disabled=not may_edit,
            )
        )
        batch_pause_ms = int(
            col_b.number_input(
                "Pause between batches (ms)",
                min_value=0,
                max_value=10000,
                step=50,
                value=int(config.batch_pause_ms),
                key=f"{prefix}_pause",
                disabled=not may_edit,
            )
        )
        max_ids = int(
            col_c.number_input(
                "Maximum records per run",
                min_value=1,
                max_value=200000,
                step=100,
                value=int(config.max_ids_per_run),
                key=f"{prefix}_maxids",
                disabled=not may_edit,
            )
        )
        col_d, col_e = st.columns(2)
        create_notification = col_d.checkbox(
            "Create in-app notification",
            value=config.create_notification,
            key=f"{prefix}_notify",
            disabled=not may_edit,
        )
        create_activity = col_e.checkbox(
            "Create review activity",
            value=config.create_activity,
            key=f"{prefix}_activity",
            disabled=not may_edit,
        )
        fallback_user_id = st.text_input(
            "Fallback assignee (user id)",
            value=config.fallback_user_id,
            key=f"{prefix}_fallback",
            disabled=not may_edit,
            help="Used when the record has no owner. Some jobs only notify this user.",
        )

    col_save, col_run, col_dry = st.columns(3)
    if col_save.button(
        "Save",
        key=f"{prefix}_save",
        type="primary",
        disabled=not may_edit,
        width="stretch",
    ):
        config.enabled = enabled
        config.apply_schedule(spec)
        config.batch_size = batch_size
        config.batch_pause_ms = batch_pause_ms
        config.max_ids_per_run = max_ids
        config.create_notification = create_notification
        config.create_activity = create_activity
        config.fallback_user_id = fallback_user_id.strip()
        _apply_rule_values(config, rule_values)
        service.save_config(config, actor_id=actor_id(services))
        st.success("Saved.")
        st.rerun()

    if col_run.button(
        "Run now",
        key=f"{prefix}_run",
        disabled=not may_run,
        width="stretch",
        icon=":material/play_arrow:",
    ):
        show_outcome(service.run_now(config.job_id, actor_id=actor_id(services)))

    if col_dry.button(
        "Dry run",
        key=f"{prefix}_dry",
        disabled=not may_run,
        width="stretch",
        icon=":material/visibility:",
        help="Counts what would be processed without writing anything.",
    ):
        show_outcome(service.dry_run(config.job_id, actor_id=actor_id(services)))

    runs = service.list_runs(config.job_id, limit=5)
    if runs:
        with st.expander("This scheduler's last runs"):
            st.dataframe(
                [
                    {
                        "Status": (r.status or "").replace("_", " "),
                        "Trigger": r.trigger,
                        "Started": format_business(r.started_at),
                        "Identified": r.identified_count,
                        "Created": r.created_count,
                        "Skipped": r.skipped_count,
                        "Errors": r.error_count,
                        "Batches": r.batch_count,
                    }
                    for r in runs
                ],
                width="stretch",
                hide_index=True,
            )


def _render_rule_fields(
    prefix: str,
    config: SchedulerJobConfig,
    rule_fields: List[str],
    *,
    disabled: bool,
) -> Dict[str, Any]:
    if not rule_fields:
        return {}
    st.markdown("**Rule settings**")
    values: Dict[str, Any] = {}
    columns = st.columns(min(3, len(rule_fields)))
    for index, name in enumerate(rule_fields):
        column = columns[index % len(columns)]
        with column:
            values[name] = _render_rule_field(prefix, config, name, disabled=disabled)
    return values


def _render_rule_field(
    prefix: str, config: SchedulerJobConfig, name: str, *, disabled: bool
) -> Any:
    key = f"{prefix}_rule_{name}"
    if name == "reminder_offsets_days":
        raw = st.text_input(
            _RULE_LABELS[name],
            value=", ".join(str(v) for v in (config.reminder_offsets_days or [])),
            key=key,
            disabled=disabled,
        )
        return raw
    if name == "minimum_amount":
        return st.number_input(
            _RULE_LABELS[name],
            min_value=0.0,
            value=float(config.minimum_amount or 0.0),
            step=1.0,
            key=key,
            disabled=disabled,
        )
    if name in _RULE_LABELS:
        return int(
            st.number_input(
                _RULE_LABELS[name],
                min_value=0,
                max_value=3650,
                value=int(getattr(config, name, 0) or 0),
                step=1,
                key=key,
                disabled=disabled,
            )
        )
    # Job-specific option; infer the widget from the stored default.
    current = config.option(name)
    label = name.replace("_", " ").capitalize()
    if isinstance(current, bool):
        return st.checkbox(label, value=current, key=key, disabled=disabled)
    if isinstance(current, (int, float)):
        return st.number_input(
            label, value=float(current), step=1.0, key=key, disabled=disabled
        )
    return st.text_input(label, value=str(current or ""), key=key, disabled=disabled)


def _apply_rule_values(config: SchedulerJobConfig, values: Dict[str, Any]) -> None:
    for name, value in values.items():
        if name == "reminder_offsets_days":
            config.reminder_offsets_days = [
                int(part.strip())
                for part in str(value or "").split(",")
                if part.strip().lstrip("-").isdigit()
            ]
        elif name == "minimum_amount":
            config.minimum_amount = float(value or 0.0)
        elif name in _RULE_LABELS:
            setattr(config, name, int(value or 0))
        else:
            current = config.option(name)
            if isinstance(current, bool):
                config.options[name] = bool(value)
            elif isinstance(current, int) and not isinstance(current, bool):
                config.options[name] = int(value)
            elif isinstance(current, float):
                config.options[name] = float(value)
            else:
                config.options[name] = value
