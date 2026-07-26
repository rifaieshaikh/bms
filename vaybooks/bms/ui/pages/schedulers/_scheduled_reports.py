"""Domain Scheduled reports page: result, recent runs, Configure dialog."""

from __future__ import annotations

import csv
import io
from typing import Any, Dict, List

import streamlit as st

from vaybooks.bms.application.schedulers.reports_protocol import (
    RANGE_LAST_N_DAYS,
    RELATIVE_RANGE_LABELS,
    RELATIVE_RANGES,
    resolve_relative_range,
)
from vaybooks.bms.domain.schedulers.entities import (
    DEFAULT_REPORT_MAX_ROWS,
    DOMAIN_LABELS,
    STATUS_COMPLETED,
    STATUS_COMPLETED_WITH_ERRORS,
    STATUS_DRY_RUN,
    SchedulerReportConfig,
)
from vaybooks.bms.domain.schedulers.time import format_business
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler
from vaybooks.bms.ui.pages.schedulers._common import (
    UNAVAILABLE_TEXT,
    actor_id,
    can,
    schedule_controls,
    show_outcome,
)

# Filter keys offered per domain beyond the shared relative date range.
_EXTRA_FILTERS: Dict[str, List[tuple[str, str]]] = {
    "crm": [
        ("assigned_user_id", "Assigned user id"),
        ("customer_id", "Customer id"),
        ("area", "Area"),
        ("branch", "Branch"),
    ],
    "sales": [("customer_id", "Customer id")],
    "purchases": [("vendor_id", "Vendor id")],
    "inventory": [
        ("category_id", "Category id"),
        ("location_id", "Location id"),
        ("search", "Product or SKU contains"),
    ],
    "boutique": [("customer_id", "Customer id")],
    "projects": [("project_id", "Project id")],
}

_SUCCESS_STATUSES = (STATUS_COMPLETED, STATUS_COMPLETED_WITH_ERRORS, STATUS_DRY_RUN)


# Session flag: when set, value is "domain|report_id" and the configure dialog opens.
CONFIGURE_FLAG = "sched_rpt_configure_open"


def _selected_run_key(domain: str, report_id: str) -> str:
    return f"sched_rpt_selected_run_{domain}_{report_id}"


def render_scheduled_reports_page(services: dict, *, domain: str) -> None:
    label = DOMAIN_LABELS.get(domain, domain.title())
    st.title(f"{label} Scheduled reports")

    service = services.get("schedulers")
    if service is None:
        st.info(UNAVAILABLE_TEXT)
        return

    may_run = can(services, "schedulers.run")
    may_edit = can(services, "schedulers.edit")

    definitions = service.list_domain_reports(domain)
    if not definitions:
        st.info("No reports are available to schedule for this module yet.")
        return

    st.caption(
        "Scheduled runs produce a CSV you can review here. Use Configure to set "
        "the schedule and filters."
    )

    action_left, _ = st.columns([1, 3])
    with action_left:
        if st.button(
            "Run all scheduled reports",
            key=f"sched_{domain}_run_reports",
            disabled=not may_run,
            width="stretch",
            icon=":material/play_arrow:",
        ):
            show_outcome(
                service.run_domain_reports(domain, actor_id=actor_id(services))
            )

    labels = {_label(d): d for d in definitions}
    chosen = st.selectbox(
        "Report", list(labels.keys()), key=f"sched_{domain}_report_pick"
    )
    definition = labels[chosen]
    config = service.get_report_config(domain, definition.report_id)
    if config is None:
        st.info("This report cannot be scheduled.")
        return

    _render_toolbar(
        services,
        service,
        config,
        definition,
        domain=domain,
        may_run=may_run,
        may_edit=may_edit,
    )

    open_target = st.session_state.get(CONFIGURE_FLAG) or ""
    if open_target == f"{domain}|{config.report_id}":
        _configure_dialog(
            services,
            service,
            config,
            definition,
            domain=domain,
            may_edit=may_edit,
        )

    tab_report, tab_status = st.tabs(["Report", "Execution status"])
    with tab_report:
        _render_result_tab(services, service, config, domain=domain)
    with tab_status:
        _render_recent_runs_tab(services, service, config, domain=domain)


def _label(definition) -> str:
    if definition.category:
        return f"{definition.title} ({definition.category})"
    return definition.title


def _render_toolbar(
    services: dict,
    service,
    config: SchedulerReportConfig,
    definition,
    *,
    domain: str,
    may_run: bool,
    may_edit: bool,
) -> None:
    schedule_text = config.schedule_summary
    status = (config.last_status or "never run").replace("_", " ")
    st.caption(
        f"{'Enabled' if config.enabled else 'Disabled'} · {schedule_text} · "
        f"Last run: {status} · {format_business(config.last_run_at)} · "
        f"Next due: {format_business(service.next_due_at(config))}"
    )
    if config.last_error:
        st.warning(config.last_error)
    if service.is_report_running(domain, config.report_id):
        st.info("This report is running right now.")

    col_cfg, col_run, col_dry = st.columns(3)
    if col_cfg.button(
        "Configure",
        key=f"sched_{domain}_rpt_{config.report_id}_configure",
        disabled=not may_edit,
        width="stretch",
        icon=":material/settings:",
    ):
        st.session_state[CONFIGURE_FLAG] = f"{domain}|{config.report_id}"
        st.rerun()

    if col_run.button(
        "Run now",
        key=f"sched_{domain}_rpt_{config.report_id}_run",
        disabled=not may_run,
        width="stretch",
        icon=":material/play_arrow:",
    ):
        show_outcome(
            service.run_report_now(
                domain, config.report_id, actor_id=actor_id(services)
            )
        )

    if col_dry.button(
        "Dry run",
        key=f"sched_{domain}_rpt_{config.report_id}_dry",
        disabled=not may_run,
        width="stretch",
        icon=":material/visibility:",
        help="Estimates the row count without storing a file.",
    ):
        show_outcome(
            service.dry_run_report(
                domain, config.report_id, actor_id=actor_id(services)
            )
        )


@st.dialog(
    "Configure scheduled report",
    width="large",
    on_dismiss=make_dismiss_handler(CONFIGURE_FLAG),
)
def _configure_dialog(
    services: dict,
    service,
    config: SchedulerReportConfig,
    definition,
    *,
    domain: str,
    may_edit: bool,
) -> None:
    prefix = f"sched_{domain}_rpt_dlg_{config.report_id}"
    filters = dict(config.filters or {})

    st.markdown(f"**{definition.title}**")
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

    st.markdown("**Filters**")
    range_key = str(filters.get("range_key") or "last_30_days")
    range_days = int(filters.get("range_days") or 7)
    col_range, col_days = st.columns(2)
    with col_range:
        chosen_range = st.selectbox(
            "Date range",
            list(RELATIVE_RANGES),
            index=(
                list(RELATIVE_RANGES).index(range_key)
                if range_key in RELATIVE_RANGES
                else 3
            ),
            format_func=lambda r: RELATIVE_RANGE_LABELS.get(r, r),
            key=f"{prefix}_range",
            disabled=not may_edit or not definition.supports_date_range,
        )
    with col_days:
        if chosen_range == RANGE_LAST_N_DAYS:
            range_days = int(
                st.number_input(
                    "N days",
                    min_value=1,
                    max_value=730,
                    value=range_days,
                    key=f"{prefix}_range_days",
                    disabled=not may_edit,
                )
            )
        else:
            st.caption(" ")
    if definition.supports_date_range:
        start, end = resolve_relative_range(chosen_range, days=range_days)
        st.caption(
            f"Resolved at run time; today that would be {start.isoformat()} to "
            f"{end.isoformat()}."
        )
    else:
        st.caption("This report ignores the date range.")

    extra_values: Dict[str, Any] = {}
    extras = _EXTRA_FILTERS.get(domain, [])
    if extras:
        columns = st.columns(min(3, len(extras)))
        for index, (name, label) in enumerate(extras):
            with columns[index % len(columns)]:
                extra_values[name] = st.text_input(
                    label,
                    value=str(filters.get(name, "") or ""),
                    key=f"{prefix}_f_{name}",
                    disabled=not may_edit,
                )

    st.markdown("**Delivery**")
    col_rec, col_rows = st.columns(2)
    recipients_raw = col_rec.text_input(
        "Recipients (user ids, comma separated)",
        value=", ".join(config.recipient_ids or []),
        key=f"{prefix}_recipients",
        disabled=not may_edit,
        help="Defaults to whoever saves this configuration.",
    )
    max_rows = int(
        col_rows.number_input(
            "Maximum rows",
            min_value=100,
            max_value=500000,
            step=1000,
            value=int(config.max_rows or DEFAULT_REPORT_MAX_ROWS),
            key=f"{prefix}_maxrows",
            disabled=not may_edit,
        )
    )
    create_notification = st.checkbox(
        "Notify recipients when a run completes",
        value=config.create_notification,
        key=f"{prefix}_notify",
        disabled=not may_edit,
    )

    col_save, col_cancel = st.columns(2)
    if col_save.button(
        "Save",
        key=f"{prefix}_save",
        type="primary",
        disabled=not may_edit,
        width="stretch",
    ):
        config.enabled = enabled
        config.report_title = definition.title
        config.apply_schedule(spec)
        new_filters = {"range_key": chosen_range, "range_days": range_days}
        new_filters.update({k: v for k, v in extra_values.items() if str(v).strip()})
        config.filters = new_filters
        config.recipient_ids = [
            part.strip() for part in recipients_raw.split(",") if part.strip()
        ]
        config.max_rows = max_rows
        config.create_notification = create_notification
        service.save_report_config(config, actor_id=actor_id(services))
        st.session_state.pop(CONFIGURE_FLAG, None)
        st.success("Saved.")
        st.rerun()

    if col_cancel.button("Cancel", key=f"{prefix}_cancel", width="stretch"):
        st.session_state.pop(CONFIGURE_FLAG, None)
        st.rerun()


def _render_result_tab(
    services: dict, service, config: SchedulerReportConfig, *, domain: str
) -> None:
    runs = service.list_report_runs(domain, config.report_id, limit=25)
    result_runs = [r for r in runs if r.status in _SUCCESS_STATUSES and r.artifact_id]
    if not result_runs and not any(r.status in _SUCCESS_STATUSES for r in runs):
        st.info(
            "No report result yet. Run now or wait for the schedule, then the "
            "output will appear here."
        )
        return

    selected_key = _selected_run_key(domain, config.report_id)
    selected_id = st.session_state.get(selected_key) or (
        result_runs[0].id if result_runs else (runs[0].id if runs else "")
    )
    by_id = {r.id: r for r in runs}
    run = by_id.get(selected_id) or (result_runs[0] if result_runs else runs[0])
    st.session_state[selected_key] = run.id

    st.caption(
        f"Showing run from {format_business(run.started_at)} · "
        f"{(run.status or '').replace('_', ' ')} · {run.row_count} rows"
        + (" (truncated)" if run.truncated else "")
    )
    if run.error_summary and run.status != STATUS_COMPLETED:
        st.warning(run.error_summary)

    if not run.artifact_id:
        st.info(
            "This run did not store a CSV (for example a dry run). "
            "Pick a completed run from Execution status, or run again."
        )
        return

    artifact = service.get_artifact(run.artifact_id, actor_id=actor_id(services))
    if artifact is None:
        st.warning("The CSV for this run is no longer available.")
        return

    rows = _csv_to_rows(artifact.data)
    if rows:
        st.dataframe(rows, width="stretch", hide_index=True)
    else:
        st.caption("The CSV has no data rows.")

    st.download_button(
        "Download CSV",
        data=artifact.data,
        file_name=artifact.filename or f"{config.report_id}.csv",
        mime="text/csv",
        key=f"sched_{domain}_rpt_{config.report_id}_dl_result",
        icon=":material/download:",
    )


def _render_recent_runs_tab(
    services: dict, service, config: SchedulerReportConfig, *, domain: str
) -> None:
    runs = service.list_report_runs(domain, config.report_id, limit=25)
    if not runs:
        st.info("This report has not run yet.")
        return

    st.subheader("Recent runs")
    st.dataframe(
        [
            {
                "Started": format_business(r.started_at),
                "Status": (r.status or "").replace("_", " "),
                "Trigger": r.trigger,
                "Actor": r.actor_id or "system",
                "Rows": r.row_count,
                "Truncated": "Yes" if r.truncated else "",
                "Detail": (r.error_summary or "")[:120],
            }
            for r in runs
        ],
        width="stretch",
        hide_index=True,
    )

    options = {
        f"{format_business(r.started_at)} · {(r.status or '').replace('_', ' ')} "
        f"({r.row_count} rows)": r.id
        for r in runs
    }
    pick = st.selectbox(
        "Open run on Report tab",
        list(options.keys()),
        key=f"sched_{domain}_rpt_{config.report_id}_pick_run",
    )
    if st.button(
        "Show on Report tab",
        key=f"sched_{domain}_rpt_{config.report_id}_show_run",
        icon=":material/visibility:",
    ):
        st.session_state[_selected_run_key(domain, config.report_id)] = options[pick]
        st.rerun()

    selected_id = options[pick]
    run = next(r for r in runs if r.id == selected_id)
    if run.artifact_id:
        artifact = service.get_artifact(run.artifact_id, actor_id=actor_id(services))
        if artifact is not None:
            st.download_button(
                "Download this run's CSV",
                data=artifact.data,
                file_name=artifact.filename or f"{config.report_id}.csv",
                mime="text/csv",
                key=f"sched_{domain}_rpt_{config.report_id}_dl_run",
                icon=":material/download:",
            )


def _csv_to_rows(data: bytes) -> List[Dict[str, Any]]:
    if not data:
        return []
    text = data.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]
