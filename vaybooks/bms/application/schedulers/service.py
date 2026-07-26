"""Scheduler application service: due checks, manual triggers, and reports."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from vaybooks.bms.application.schedulers.pipeline import run_job
from vaybooks.bms.application.schedulers.protocol import JobContext, JobDefinition
from vaybooks.bms.application.schedulers.registry import JobRegistry
from vaybooks.bms.application.schedulers.reports_protocol import (
    RANGE_LAST_30_DAYS,
    ReportContext,
    ReportRunResult,
    resolve_relative_range,
    rows_to_csv,
)
from vaybooks.bms.application.schedulers.reports_registry import (
    ReportRegistry,
    ReportSkipped,
)
from vaybooks.bms.application.schedulers.runner import (
    LEASE_TTL_SECONDS,
    ProcessLocks,
    start_background,
)
from vaybooks.bms.domain.schedulers.entities import (
    DOMAIN_ORDER,
    REPORT_ARTIFACT_RETENTION,
    STATUS_COMPLETED,
    STATUS_COMPLETED_WITH_ERRORS,
    STATUS_DRY_RUN,
    STATUS_FAILED,
    STATUS_RUNNING,
    STATUS_SKIPPED,
    TRIGGER_DRY_RUN,
    TRIGGER_RUN_ALL,
    TRIGGER_RUN_DOMAIN,
    TRIGGER_RUN_NOW,
    TRIGGER_SCHEDULE,
    SchedulerJobConfig,
    SchedulerNotification,
    SchedulerReportArtifact,
    SchedulerReportConfig,
    SchedulerReportRunLog,
    SchedulerRunLog,
    report_lease_key,
)
from vaybooks.bms.domain.schedulers.schedule import (
    ScheduleSpec,
    is_job_due,
    next_run_at,
    schedule_to_cron,
    validate_schedule,
)
from vaybooks.bms.domain.schedulers.time import (
    business_day_bounds,
    business_today,
    utc_now,
)

logger = logging.getLogger("vaybooks.bms.schedulers")

WAVE_LOCK_KEY = "__wave__"


class TriggerOutcome:
    """Small result object the UI renders after a manual trigger."""

    def __init__(self, started: List[str], skipped: List[str], message: str = ""):
        self.started = started
        self.skipped = skipped
        self.message = message

    @property
    def any_started(self) -> bool:
        return bool(self.started)


class SchedulerAppService:
    def __init__(
        self,
        config_repo,
        run_log_repo,
        lease_repo,
        notification_repo,
        *,
        registry: Optional[JobRegistry] = None,
        report_registry: Optional[ReportRegistry] = None,
        report_config_repo=None,
        report_run_log_repo=None,
        report_artifact_repo=None,
        audit=None,
        background: bool = True,
    ):
        self._configs = config_repo
        self._runs = run_log_repo
        self._leases = lease_repo
        self._notifications = notification_repo
        self._registry = registry or JobRegistry()
        self._reports = report_registry
        self._report_configs = report_config_repo
        self._report_runs = report_run_log_repo
        self._report_artifacts = report_artifact_repo
        self._audit = audit
        self._background = background
        self._locks = ProcessLocks()

    # --- registry / catalog --------------------------------------------------

    @property
    def registry(self) -> JobRegistry:
        return self._registry

    def job_definitions(self, domain: str = "") -> List[JobDefinition]:
        if domain:
            return self._registry.definitions_for_domain(domain)
        return self._registry.definitions()

    def list_domain_reports(self, domain: str):
        if self._reports is None:
            return []
        return self._reports.definitions_for_domain(domain)

    # --- job configuration ---------------------------------------------------

    def get_config(self, job_id: str) -> Optional[SchedulerJobConfig]:
        config = self._configs.find_by_id(job_id)
        if config is not None:
            return config
        definition = self._registry.definition(job_id)
        return self._config_from_definition(definition) if definition else None

    def list_configs(self, domain: str = "") -> List[SchedulerJobConfig]:
        """Registry order, falling back to seed defaults for unsaved jobs."""
        stored = {c.job_id: c for c in self._configs.list_all()}
        out: List[SchedulerJobConfig] = []
        for definition in self.job_definitions(domain):
            config = stored.get(definition.job_id)
            out.append(config or self._config_from_definition(definition))
        return out

    @staticmethod
    def _config_from_definition(definition: JobDefinition) -> SchedulerJobConfig:
        config = SchedulerJobConfig(
            job_id=definition.job_id,
            domain=definition.domain,
            title=definition.title,
            description=definition.description,
            enabled=definition.enabled,
            frequency=definition.frequency,
            time_of_day=definition.time_of_day,
            weekday=definition.weekday,
            interval_days=definition.interval_days,
            threshold_days=definition.threshold_days,
            warning_days=definition.warning_days,
            grace_days=definition.grace_days,
            reminder_offsets_days=list(definition.reminder_offsets_days or []),
            minimum_amount=definition.minimum_amount,
            create_activity=definition.create_activity,
            create_notification=definition.create_notification,
            options=dict(definition.options or {}),
        )
        config.apply_schedule(config.schedule)
        config.next_run_at = next_run_at(config.schedule)
        return config

    def save_config(
        self, config: SchedulerJobConfig, *, actor_id: str = ""
    ) -> SchedulerJobConfig:
        validate_schedule(config.schedule)
        config.cron_expression = schedule_to_cron(config.schedule)
        config.next_run_at = next_run_at(
            config.schedule, last_run_at=config.last_run_at
        )
        config.updated_by = actor_id or config.updated_by
        saved = self._configs.save(config)
        self._record_audit("scheduler_config_saved", actor_id, job_id=config.job_id)
        return saved

    # --- report configuration ------------------------------------------------

    def get_report_config(
        self, domain: str, report_id: str
    ) -> Optional[SchedulerReportConfig]:
        if self._report_configs is None:
            return None
        existing = self._report_configs.find(domain, report_id)
        if existing is not None:
            return existing
        definition = (
            self._reports.definition(domain, report_id) if self._reports else None
        )
        if definition is None:
            return None
        # Configs are created lazily on first Save; this is an unsaved default.
        config = SchedulerReportConfig(
            domain=domain,
            report_id=report_id,
            report_title=definition.title,
            enabled=False,
            filters={"range_key": RANGE_LAST_30_DAYS, "range_days": 30},
        )
        config.apply_schedule(config.schedule)
        return config

    def save_report_config(
        self, config: SchedulerReportConfig, *, actor_id: str = ""
    ) -> SchedulerReportConfig:
        if self._report_configs is None:
            raise RuntimeError("Scheduled reports are not configured")
        validate_schedule(config.schedule)
        config.cron_expression = schedule_to_cron(config.schedule)
        config.next_run_at = next_run_at(
            config.schedule, last_run_at=config.last_run_at
        )
        config.updated_by = actor_id or config.updated_by
        if not config.recipient_ids and actor_id:
            config.recipient_ids = [actor_id]
        saved = self._report_configs.save(config)
        self._record_audit(
            "scheduler_report_config_saved",
            actor_id,
            job_id=f"{config.domain}:{config.report_id}",
        )
        return saved

    def list_report_configs(self, domain: str) -> List[SchedulerReportConfig]:
        if self._report_configs is None:
            return []
        return self._report_configs.list_by_domain(domain)

    def list_report_runs(
        self, domain: str, report_id: str, limit: int = 20
    ) -> List[SchedulerReportRunLog]:
        if self._report_runs is None:
            return []
        return self._report_runs.list_for_report(domain, report_id, limit=limit)

    def get_artifact(self, artifact_id: str, *, actor_id: str = ""):
        if self._report_artifacts is None or not artifact_id:
            return None
        return self._report_artifacts.find_by_id(artifact_id)

    # --- status --------------------------------------------------------------

    def list_runs(self, job_id: str, limit: int = 10) -> List[SchedulerRunLog]:
        return self._runs.list_for_job(job_id, limit=limit)

    def recent_runs(self, limit: int = 15, domain: str = "") -> List[SchedulerRunLog]:
        return self._runs.list_recent(limit=limit, domain=domain)

    def is_running(self, job_id: str) -> bool:
        if self._locks.is_active(job_id):
            return True
        return self._leases.is_held(job_id, now=utc_now())

    def is_report_running(self, domain: str, report_id: str) -> bool:
        key = report_lease_key(domain, report_id)
        if self._locks.is_active(key):
            return True
        return self._leases.is_held(key, now=utc_now())

    def next_due_at(self, config: SchedulerJobConfig) -> Optional[datetime]:
        return next_run_at(config.schedule, last_run_at=config.last_run_at)

    # --- login trigger -------------------------------------------------------

    def maybe_start_due_jobs(self, *, actor_id: str = "") -> TriggerOutcome:
        """Evaluate schedules on authenticated login and start a due wave.

        Returns immediately; all work happens on a daemon thread.
        """
        try:
            due_jobs = [c for c in self.list_configs() if self._is_due(c)]
            due_reports = [c for c in self._due_report_configs()]
        except Exception:
            logger.exception("Scheduler due evaluation failed")
            return TriggerOutcome([], [], "Scheduler unavailable")

        if not due_jobs and not due_reports:
            return TriggerOutcome([], [], "Nothing due")
        if not self._locks.try_acquire(WAVE_LOCK_KEY):
            return TriggerOutcome([], [], "A scheduler wave is already running")

        job_ids = [c.job_id for c in due_jobs]
        report_keys = [f"{c.domain}:{c.report_id}" for c in due_reports]

        def _work() -> None:
            try:
                self._run_wave(
                    due_jobs, due_reports, trigger=TRIGGER_SCHEDULE, actor_id=actor_id
                )
            finally:
                self._locks.release(WAVE_LOCK_KEY)

        self._spawn(_work, name="scheduler-wave")
        return TriggerOutcome(job_ids + report_keys, [], "Scheduler wave started")

    def _is_due(self, config: SchedulerJobConfig) -> bool:
        if not config.enabled:
            return False
        try:
            return is_job_due(config.schedule, last_run_at=config.last_run_at)
        except Exception:
            logger.exception("Invalid schedule on job %s", config.job_id)
            return False

    def _due_report_configs(self) -> List[SchedulerReportConfig]:
        if self._report_configs is None or self._reports is None:
            return []
        due: List[SchedulerReportConfig] = []
        for config in self._report_configs.list_enabled():
            try:
                if is_job_due(config.schedule, last_run_at=config.last_run_at):
                    due.append(config)
            except Exception:
                logger.exception(
                    "Invalid schedule on report %s/%s", config.domain, config.report_id
                )
        rank = {domain: index for index, domain in enumerate(DOMAIN_ORDER)}
        due.sort(key=lambda c: (rank.get(c.domain, len(rank)), c.report_id))
        return due

    # --- manual triggers -----------------------------------------------------

    def run_now(self, job_id: str, *, actor_id: str = "") -> TriggerOutcome:
        config = self.get_config(job_id)
        if config is None:
            return TriggerOutcome([], [job_id], "Unknown job")
        return self._start_jobs([config], TRIGGER_RUN_NOW, actor_id, force=True)

    def dry_run(self, job_id: str, *, actor_id: str = "") -> TriggerOutcome:
        config = self.get_config(job_id)
        if config is None:
            return TriggerOutcome([], [job_id], "Unknown job")
        return self._start_jobs(
            [config], TRIGGER_DRY_RUN, actor_id, force=True, dry_run=True
        )

    def run_domain(
        self, domain: str, *, actor_id: str = "", include_reports: bool = True
    ) -> TriggerOutcome:
        configs = [c for c in self.list_configs(domain) if c.enabled]
        reports = (
            [c for c in self.list_report_configs(domain) if c.enabled]
            if include_reports
            else []
        )
        if not configs and not reports:
            return TriggerOutcome([], [], f"No enabled {domain} schedulers")
        return self._start_wave(configs, reports, TRIGGER_RUN_DOMAIN, actor_id)

    def run_all(self, *, actor_id: str = "") -> TriggerOutcome:
        configs = [c for c in self.list_configs() if c.enabled]
        reports: List[SchedulerReportConfig] = []
        if self._report_configs is not None:
            rank = {domain: index for index, domain in enumerate(DOMAIN_ORDER)}
            reports = sorted(
                self._report_configs.list_enabled(),
                key=lambda c: (rank.get(c.domain, len(rank)), c.report_id),
            )
        if not configs and not reports:
            return TriggerOutcome([], [], "No enabled schedulers")
        return self._start_wave(configs, reports, TRIGGER_RUN_ALL, actor_id)

    def run_report_now(
        self, domain: str, report_id: str, *, actor_id: str = ""
    ) -> TriggerOutcome:
        config = self.get_report_config(domain, report_id)
        if config is None:
            return TriggerOutcome([], [report_id], "Unknown report")
        return self._start_wave([], [config], TRIGGER_RUN_NOW, actor_id, force=True)

    def dry_run_report(
        self, domain: str, report_id: str, *, actor_id: str = ""
    ) -> TriggerOutcome:
        config = self.get_report_config(domain, report_id)
        if config is None:
            return TriggerOutcome([], [report_id], "Unknown report")
        return self._start_wave(
            [], [config], TRIGGER_DRY_RUN, actor_id, force=True, dry_run=True
        )

    def run_domain_reports(self, domain: str, *, actor_id: str = "") -> TriggerOutcome:
        reports = [c for c in self.list_report_configs(domain) if c.enabled]
        if not reports:
            return TriggerOutcome([], [], f"No enabled {domain} scheduled reports")
        return self._start_wave([], reports, TRIGGER_RUN_DOMAIN, actor_id)

    def _start_jobs(
        self,
        configs: List[SchedulerJobConfig],
        trigger: str,
        actor_id: str,
        *,
        force: bool = False,
        dry_run: bool = False,
    ) -> TriggerOutcome:
        return self._start_wave(
            configs, [], trigger, actor_id, force=force, dry_run=dry_run
        )

    def _start_wave(
        self,
        configs: List[SchedulerJobConfig],
        reports: List[SchedulerReportConfig],
        trigger: str,
        actor_id: str,
        *,
        force: bool = False,
        dry_run: bool = False,
    ) -> TriggerOutcome:
        runnable_jobs = [c for c in configs if force or c.enabled]
        skipped = [c.job_id for c in configs if c not in runnable_jobs]
        started = [c.job_id for c in runnable_jobs] + [
            f"{r.domain}:{r.report_id}" for r in reports
        ]
        if not started:
            return TriggerOutcome([], skipped, "Nothing to run")

        self._record_audit(
            f"scheduler_{trigger}", actor_id, job_id=",".join(started)[:500]
        )

        def _work() -> None:
            self._run_wave(
                runnable_jobs,
                reports,
                trigger=trigger,
                actor_id=actor_id,
                dry_run=dry_run,
            )

        self._spawn(_work, name=f"scheduler-{trigger}")
        return TriggerOutcome(started, skipped, "Started in the background")

    def _spawn(self, work: Callable[[], None], *, name: str) -> None:
        if self._background:
            start_background(work, name=name)
        else:
            work()

    # --- execution -----------------------------------------------------------

    def _run_wave(
        self,
        configs: List[SchedulerJobConfig],
        reports: List[SchedulerReportConfig],
        *,
        trigger: str,
        actor_id: str,
        dry_run: bool = False,
    ) -> None:
        rank = {domain: index for index, domain in enumerate(DOMAIN_ORDER)}
        ordered_job_ids = self._registry.ordered_job_ids()

        def job_sort(config: SchedulerJobConfig):
            try:
                position = ordered_job_ids.index(config.job_id)
            except ValueError:
                position = len(ordered_job_ids)
            return rank.get(config.domain, len(rank)), position

        for config in sorted(configs, key=job_sort):
            try:
                self._execute_job(
                    config, trigger=trigger, actor_id=actor_id, dry_run=dry_run
                )
            except Exception:
                logger.exception("Scheduler job %s failed", config.job_id)
        for report in reports:
            try:
                self._execute_report(
                    report, trigger=trigger, actor_id=actor_id, dry_run=dry_run
                )
            except Exception:
                logger.exception(
                    "Scheduled report %s/%s failed", report.domain, report.report_id
                )

    def _execute_job(
        self,
        config: SchedulerJobConfig,
        *,
        trigger: str,
        actor_id: str,
        dry_run: bool = False,
    ) -> Optional[SchedulerRunLog]:
        job = self._registry.get(config.job_id)
        if job is None:
            return self._log_skip(
                config, trigger, actor_id, "No implementation registered"
            )
        holder = f"{trigger}:{actor_id or 'system'}:{id(self)}"
        if not self._locks.try_acquire(config.job_id):
            return self._log_skip(config, trigger, actor_id, "Already running")
        now = utc_now()
        if not self._leases.acquire(
            config.job_id, holder, ttl_seconds=LEASE_TTL_SECONDS, now=now
        ):
            self._locks.release(config.job_id)
            return self._log_skip(config, trigger, actor_id, "Already running")

        log = SchedulerRunLog(
            job_id=config.job_id,
            domain=config.domain,
            trigger=trigger,
            actor_id=actor_id,
            status=STATUS_RUNNING,
            started_at=now,
            batch_size=config.batch_size,
        )
        self._runs.save(log)
        ctx = JobContext(
            config=config,
            now=now,
            actor_id=actor_id,
            dry_run=dry_run,
            notify=self.create_notification,
        )
        try:
            run_job(
                job,
                ctx,
                log,
                heartbeat=lambda: self._leases.refresh(
                    config.job_id, holder, ttl_seconds=LEASE_TTL_SECONDS, now=utc_now()
                ),
            )
        except Exception as exc:
            log.status = STATUS_FAILED
            log.error_summary = str(exc)[:2000]
            log.finished_at = utc_now()
        finally:
            self._runs.save(log)
            self._leases.release(config.job_id, holder)
            self._locks.release(config.job_id)

        if not dry_run and log.status in (STATUS_COMPLETED, STATUS_COMPLETED_WITH_ERRORS):
            config.last_run_at = log.finished_at or utc_now()
        config.last_status = log.status
        config.last_error = log.error_summary
        config.next_run_at = next_run_at(
            config.schedule, last_run_at=config.last_run_at
        )
        try:
            self._configs.save(config)
        except Exception:
            logger.exception("Failed to persist state for job %s", config.job_id)
        return log

    def _log_skip(
        self, config: SchedulerJobConfig, trigger: str, actor_id: str, reason: str
    ) -> SchedulerRunLog:
        now = utc_now()
        log = SchedulerRunLog(
            job_id=config.job_id,
            domain=config.domain,
            trigger=trigger,
            actor_id=actor_id,
            status=STATUS_SKIPPED,
            started_at=now,
            finished_at=now,
            error_summary=reason,
        )
        self._runs.save(log)
        return log

    # --- report execution ----------------------------------------------------

    def _execute_report(
        self,
        config: SchedulerReportConfig,
        *,
        trigger: str,
        actor_id: str,
        dry_run: bool = False,
    ) -> Optional[SchedulerReportRunLog]:
        if self._reports is None or self._report_runs is None:
            return None
        key = report_lease_key(config.domain, config.report_id)
        if not self._locks.try_acquire(key):
            return self._log_report_skip(config, trigger, actor_id, "Already running")
        holder = f"{trigger}:{actor_id or 'system'}:{id(self)}"
        now = utc_now()
        if not self._leases.acquire(
            key, holder, ttl_seconds=LEASE_TTL_SECONDS, now=now
        ):
            self._locks.release(key)
            return self._log_report_skip(config, trigger, actor_id, "Already running")

        try:
            if trigger == TRIGGER_SCHEDULE and self._already_ran_today(config):
                return self._log_report_skip(
                    config, trigger, actor_id, "Already completed today"
                )
            return self._run_report(
                config, trigger=trigger, actor_id=actor_id, dry_run=dry_run, now=now
            )
        finally:
            self._leases.release(key, holder)
            self._locks.release(key)

    def _already_ran_today(self, config: SchedulerReportConfig) -> bool:
        start, end = business_day_bounds(business_today())
        try:
            return (
                self._report_runs.count_successful_on_day(
                    config.domain, config.report_id, start=start, end=end
                )
                > 0
            )
        except Exception:
            return False

    def _run_report(
        self,
        config: SchedulerReportConfig,
        *,
        trigger: str,
        actor_id: str,
        dry_run: bool,
        now: datetime,
    ) -> SchedulerReportRunLog:
        definition = self._reports.definition(config.domain, config.report_id)
        title = config.report_title or (definition.title if definition else config.report_id)
        filters = dict(config.filters or {})
        range_key = str(filters.get("range_key") or RANGE_LAST_30_DAYS)
        range_days = int(filters.get("range_days") or 7)
        start, end = resolve_relative_range(range_key, days=range_days)

        ctx = ReportContext(
            domain=config.domain,
            report_id=config.report_id,
            report_title=title,
            start=start,
            end=end,
            filters=filters,
            max_rows=config.max_rows,
            actor_id=actor_id,
            dry_run=dry_run,
        )
        log = SchedulerReportRunLog(
            domain=config.domain,
            report_id=config.report_id,
            config_id=config.config_id,
            report_title=title,
            trigger=trigger,
            actor_id=actor_id,
            status=STATUS_RUNNING,
            started_at=now,
            resolved_filters=ctx.resolved_snapshot(),
        )
        self._report_runs.save(log)

        try:
            result: ReportRunResult = self._reports.run(ctx)
        except ReportSkipped as exc:
            log.status = STATUS_SKIPPED
            log.error_summary = str(exc)[:2000]
            log.finished_at = utc_now()
            self._report_runs.save(log)
            self._persist_report_state(config, log)
            return log
        except Exception as exc:
            logger.exception(
                "Scheduled report %s/%s failed", config.domain, config.report_id
            )
            log.status = STATUS_FAILED
            log.error_summary = str(exc)[:2000]
            log.finished_at = utc_now()
            self._report_runs.save(log)
            self._persist_report_state(config, log)
            return log

        rows = list(result.rows or [])
        truncated = result.truncated
        cap = max(1, int(config.max_rows))
        if len(rows) > cap:
            rows = rows[:cap]
            truncated = True

        log.row_count = len(rows)
        log.truncated = truncated

        if dry_run:
            log.status = STATUS_DRY_RUN
            log.finished_at = utc_now()
            self._report_runs.save(log)
            return log

        artifact_id = ""
        if self._report_artifacts is not None:
            artifact = SchedulerReportArtifact(
                domain=config.domain,
                report_id=config.report_id,
                run_id=log.id,
                filename=_artifact_filename(config.report_id, start, end),
                data=rows_to_csv(rows),
            )
            artifact.byte_size = len(artifact.data)
            self._report_artifacts.save(artifact)
            artifact_id = artifact.id
            try:
                self._report_artifacts.prune(
                    config.domain, config.report_id, REPORT_ARTIFACT_RETENTION
                )
            except Exception:
                logger.debug("Artifact prune failed for %s", config.report_id)

        log.artifact_id = artifact_id
        log.status = STATUS_COMPLETED_WITH_ERRORS if truncated else STATUS_COMPLETED
        if truncated:
            log.error_summary = f"Truncated to {cap} rows"
        log.finished_at = utc_now()
        self._report_runs.save(log)

        if config.create_notification:
            self._notify_report_recipients(config, log, title)
        self._persist_report_state(config, log, artifact_id=artifact_id)
        return log

    def _persist_report_state(
        self,
        config: SchedulerReportConfig,
        log: SchedulerReportRunLog,
        *,
        artifact_id: str = "",
    ) -> None:
        if self._report_configs is None:
            return
        if log.status in (STATUS_COMPLETED, STATUS_COMPLETED_WITH_ERRORS):
            config.last_run_at = log.finished_at or utc_now()
        config.last_status = log.status
        config.last_error = log.error_summary
        if artifact_id:
            config.last_artifact_id = artifact_id
        config.next_run_at = next_run_at(
            config.schedule, last_run_at=config.last_run_at
        )
        try:
            self._report_configs.save(config)
        except Exception:
            logger.exception(
                "Failed to persist state for report %s/%s",
                config.domain,
                config.report_id,
            )

    def _notify_report_recipients(
        self, config: SchedulerReportConfig, log: SchedulerReportRunLog, title: str
    ) -> None:
        recipients = [r for r in (config.recipient_ids or []) if r]
        if not recipients and config.fallback_user_id:
            recipients = [config.fallback_user_id]
        for recipient in recipients:
            self.create_notification(
                recipient_id=recipient,
                domain=config.domain,
                job_id=f"report:{config.report_id}",
                kind="scheduled_report",
                title=f"{title} is ready",
                message=f"{log.row_count} rows generated.",
                ref_type="scheduler_report_run",
                ref_id=log.id,
                metadata={
                    "domain": config.domain,
                    "report_id": config.report_id,
                    "run_id": log.id,
                    "artifact_id": log.artifact_id,
                },
            )

    def _log_report_skip(
        self,
        config: SchedulerReportConfig,
        trigger: str,
        actor_id: str,
        reason: str,
    ) -> SchedulerReportRunLog:
        now = utc_now()
        log = SchedulerReportRunLog(
            domain=config.domain,
            report_id=config.report_id,
            config_id=config.config_id,
            report_title=config.report_title,
            trigger=trigger,
            actor_id=actor_id,
            status=STATUS_SKIPPED,
            started_at=now,
            finished_at=now,
            error_summary=reason,
        )
        if self._report_runs is not None:
            self._report_runs.save(log)
        return log

    # --- notifications -------------------------------------------------------

    def create_notification(
        self,
        *,
        recipient_id: str,
        domain: str,
        job_id: str,
        kind: str,
        title: str,
        message: str = "",
        ref_type: str = "",
        ref_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[SchedulerNotification]:
        """Deduplicated notification write; returns None when already present."""
        if not recipient_id:
            return None
        dedupe_key = SchedulerNotification.build_dedupe_key(
            recipient_id, job_id, ref_type, ref_id
        )
        existing = self._notifications.find_by_dedupe_key(dedupe_key)
        if existing is not None:
            return None
        notification = SchedulerNotification(
            recipient_id=recipient_id,
            domain=domain,
            kind=kind,
            title=title,
            message=message,
            ref_type=ref_type,
            ref_id=ref_id,
            dedupe_key=dedupe_key,
            job_id=job_id,
            metadata=dict(metadata or {}),
        )
        try:
            return self._notifications.save(notification)
        except Exception:
            logger.exception("Failed to save scheduler notification")
            return None

    def list_notifications(
        self, recipient_id: str, *, state: str = "open", limit: int = 50
    ) -> List[SchedulerNotification]:
        if not recipient_id:
            return []
        return self._notifications.list_for_recipient(
            recipient_id, state=state, limit=limit
        )

    def mark_notification_read(self, notification_id: str) -> None:
        self._notifications.mark_read(notification_id)

    # --- audit ---------------------------------------------------------------

    def _record_audit(self, action: str, actor_id: str, **fields: Any) -> None:
        if self._audit is None:
            return
        try:
            self._audit.record(
                action,
                actor_id=actor_id,
                target_type="scheduler_job",
                target_id=str(fields.get("job_id", ""))[:200],
                detail={k: v for k, v in fields.items() if k != "job_id"},
            )
        except Exception:
            logger.debug("Scheduler audit write failed for %s", action)


def _artifact_filename(report_id: str, start: Optional[date], end: Optional[date]) -> str:
    stamp = end.isoformat() if end else business_today().isoformat()
    return f"{report_id}_{stamp}.csv"


__all__ = ["SchedulerAppService", "TriggerOutcome", "ScheduleSpec", "timedelta"]
