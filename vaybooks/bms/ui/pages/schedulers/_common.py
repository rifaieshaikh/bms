"""Shared rendering for Settings → Schedulers job pages (jobs only)."""

from __future__ import annotations

from datetime import time as dt_time
from typing import List

import streamlit as st

from vaybooks.bms.domain.schedulers.entities import (
    DOMAIN_LABELS,
    SchedulerJobConfig,
)
from vaybooks.bms.domain.schedulers.schedule import (
    FREQ_EVERY_N_DAYS,
    FREQ_WEEKLY,
    FREQUENCIES,
    FREQUENCY_LABELS,
    WEEKDAY_LABELS,
    ScheduleSpec,
    format_schedule,
    parse_time_of_day,
)
from vaybooks.bms.domain.schedulers.time import format_business

UNAVAILABLE_TEXT = "The scheduler service is not available yet."


def can(services: dict, permission: str) -> bool:
    try:
        from vaybooks.bms.ui.auth.session import can_permission

        return bool(can_permission(services, permission))
    except Exception:
        return True


def actor_id(services: dict) -> str:
    try:
        from vaybooks.bms.ui.auth.session import current_user_id

        return current_user_id()
    except Exception:
        return ""


def schedule_controls(
    *,
    key_prefix: str,
    frequency: str,
    time_of_day: str,
    weekday: int,
    interval_days: int,
    disabled: bool = False,
) -> ScheduleSpec:
    """Plain-language schedule editor; cron is never shown to the operator."""
    col_freq, col_time, col_extra = st.columns(3)
    with col_freq:
        chosen = st.selectbox(
            "How often",
            list(FREQUENCIES),
            index=list(FREQUENCIES).index(frequency) if frequency in FREQUENCIES else 0,
            format_func=lambda f: FREQUENCY_LABELS.get(f, f),
            key=f"{key_prefix}_freq",
            disabled=disabled,
        )
    with col_time:
        try:
            default_time = parse_time_of_day(time_of_day)
        except Exception:
            default_time = dt_time(6, 0)
        picked = st.time_input(
            "At",
            value=default_time,
            step=300,
            key=f"{key_prefix}_time",
            disabled=disabled,
        )
    chosen_weekday = int(weekday or 0)
    chosen_interval = max(1, int(interval_days or 1))
    with col_extra:
        if chosen == FREQ_WEEKLY:
            chosen_weekday = st.selectbox(
                "On",
                list(range(7)),
                index=chosen_weekday % 7,
                format_func=lambda i: WEEKDAY_LABELS[i],
                key=f"{key_prefix}_weekday",
                disabled=disabled,
            )
        elif chosen == FREQ_EVERY_N_DAYS:
            chosen_interval = int(
                st.number_input(
                    "Every (days)",
                    min_value=1,
                    max_value=365,
                    value=chosen_interval,
                    step=1,
                    key=f"{key_prefix}_interval",
                    disabled=disabled,
                )
            )
        else:
            st.caption(" ")

    spec = ScheduleSpec(
        frequency=chosen,
        time_of_day=f"{picked.hour:02d}:{picked.minute:02d}",
        weekday=chosen_weekday,
        interval_days=chosen_interval,
    )
    st.caption(f"Runs {format_schedule(spec).lower()} (India Standard Time)")
    return spec


def render_domain_summary(service, domain: str) -> List[SchedulerJobConfig]:
    configs = service.list_configs(domain)
    enabled = [c for c in configs if c.enabled]
    next_due = min(
        (c for c in enabled if service.next_due_at(c)),
        key=lambda c: service.next_due_at(c),
        default=None,
    )
    last = next(
        (c for c in sorted(configs, key=_last_run_key, reverse=True) if c.last_run_at),
        None,
    )
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Enabled jobs", f"{len(enabled)} / {len(configs)}")
    col_b.metric(
        "Next due",
        format_business(service.next_due_at(next_due)) if next_due else "—",
        help=next_due.title if next_due else None,
    )
    col_c.metric(
        "Last run",
        (last.last_status or "—").replace("_", " ") if last else "—",
        help=format_business(last.last_run_at) if last else None,
    )
    return configs


def _last_run_key(config: SchedulerJobConfig):
    from datetime import datetime

    return config.last_run_at or datetime.min


def render_recent_runs(service, domain: str, *, limit: int = 10) -> None:
    runs = service.recent_runs(limit=limit, domain=domain)
    if not runs:
        st.caption("No runs recorded yet.")
        return
    st.dataframe(
        [
            {
                "Job": r.job_id,
                "Status": (r.status or "").replace("_", " "),
                "Trigger": r.trigger,
                "Started": format_business(r.started_at),
                "Identified": r.identified_count,
                "Created": r.created_count,
                "Errors": r.error_count,
                "Detail": r.error_summary[:120],
            }
            for r in runs
        ],
        width="stretch",
        hide_index=True,
    )


def show_outcome(outcome) -> None:
    if outcome is None:
        return
    if getattr(outcome, "any_started", False):
        st.success(
            f"{outcome.message}: {', '.join(outcome.started[:5])}"
            + ("…" if len(outcome.started) > 5 else "")
        )
    else:
        st.info(getattr(outcome, "message", "Nothing to run"))


def render_page(services: dict, *, domain: str) -> None:
    """Settings → Schedulers page for one domain (jobs only)."""
    from vaybooks.bms.ui.pages.schedulers._jobs import render_jobs_section

    label = DOMAIN_LABELS.get(domain, domain.title())
    st.title(f"{label} Schedulers")

    service = services.get("schedulers")
    if service is None:
        st.info(UNAVAILABLE_TEXT)
        return

    may_run = can(services, "schedulers.run")
    may_edit = can(services, "schedulers.edit")

    header_left, header_right = st.columns([3, 1], vertical_alignment="center")
    header_left.caption(
        "Schedules run on the first sign-in after the due time, in the background."
    )
    with header_right:
        if st.button(
            "Run all schedulers",
            key=f"sched_{domain}_run_global",
            disabled=not may_run,
            width="stretch",
            icon=":material/play_circle:",
            help="Run every enabled job and scheduled report across all domains.",
        ):
            st.session_state[f"sched_{domain}_confirm_all"] = True
    if st.session_state.get(f"sched_{domain}_confirm_all"):
        st.warning("This runs every enabled scheduler in every domain.")
        confirm_a, confirm_b = st.columns(2)
        if confirm_a.button("Confirm", key=f"sched_{domain}_confirm_yes", type="primary"):
            st.session_state.pop(f"sched_{domain}_confirm_all", None)
            show_outcome(service.run_all(actor_id=actor_id(services)))
        if confirm_b.button("Cancel", key=f"sched_{domain}_confirm_no"):
            st.session_state.pop(f"sched_{domain}_confirm_all", None)

    render_jobs_section(
        services, service, domain=domain, may_run=may_run, may_edit=may_edit
    )
