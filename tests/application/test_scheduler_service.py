"""Scheduler pipeline, leases, triggers, idempotency, and scheduled reports."""

from datetime import datetime, timedelta

import pytest

from vaybooks.bms.application.schedulers.pipeline import chunks, run_job
from vaybooks.bms.application.schedulers.protocol import (
    JobContext,
    JobDefinition,
    JobResult,
)
from vaybooks.bms.application.schedulers.registry import JobRegistry
from vaybooks.bms.application.schedulers.reports_protocol import (
    RANGE_LAST_7_DAYS,
    ReportDefinition,
    ReportRunResult,
    resolve_relative_range,
    rows_to_csv,
)
from vaybooks.bms.application.schedulers.reports_registry import (
    ReportRegistry,
    ReportSkipped,
)
from vaybooks.bms.application.schedulers.service import SchedulerAppService
from vaybooks.bms.domain.schedulers.entities import (
    DOMAIN_CRM,
    DOMAIN_SALES,
    STATUS_COMPLETED,
    STATUS_COMPLETED_WITH_ERRORS,
    STATUS_DRY_RUN,
    STATUS_FAILED,
    STATUS_SKIPPED,
    TRIGGER_RUN_ALL,
    TRIGGER_RUN_NOW,
    TRIGGER_SCHEDULE,
    SchedulerJobConfig,
    SchedulerRunLog,
    report_lease_key,
)
from vaybooks.bms.domain.schedulers.time import utc_now

# ---------------------------------------------------------------------------
# In-memory doubles
# ---------------------------------------------------------------------------


class FakeConfigRepo:
    def __init__(self, configs=()):
        self._store = {c.job_id: c for c in configs}

    def save(self, config):
        self._store[config.job_id] = config
        return config

    def find_by_id(self, job_id):
        return self._store.get(job_id)

    def list_all(self):
        return list(self._store.values())

    def list_by_domain(self, domain):
        return [c for c in self._store.values() if c.domain == domain]

    def list_enabled(self):
        return [c for c in self._store.values() if c.enabled]


class FakeRunLogRepo:
    def __init__(self):
        self.saved = []

    def save(self, log):
        for index, existing in enumerate(self.saved):
            if existing.id == log.id:
                self.saved[index] = log
                return log
        self.saved.append(log)
        return log

    def list_for_job(self, job_id, limit=10):
        rows = [r for r in self.saved if r.job_id == job_id]
        return sorted(rows, key=lambda r: r.started_at, reverse=True)[:limit]

    def list_recent(self, limit=15, domain=""):
        rows = [r for r in self.saved if not domain or r.domain == domain]
        return sorted(rows, key=lambda r: r.started_at, reverse=True)[:limit]


class FakeLeaseRepo:
    """Mimics the atomic acquire semantics of the Mongo implementation."""

    def __init__(self):
        self.held = {}
        self.refreshes = 0

    def acquire(self, lease_key, holder_id, *, ttl_seconds, now=None):
        moment = now or utc_now()
        current = self.held.get(lease_key)
        if current and current[1] > moment:
            return False
        self.held[lease_key] = (holder_id, moment + timedelta(seconds=ttl_seconds))
        return True

    def refresh(self, lease_key, holder_id, *, ttl_seconds, now=None):
        moment = now or utc_now()
        current = self.held.get(lease_key)
        if not current or current[0] != holder_id:
            return False
        self.refreshes += 1
        self.held[lease_key] = (holder_id, moment + timedelta(seconds=ttl_seconds))
        return True

    def release(self, lease_key, holder_id):
        current = self.held.get(lease_key)
        if current and current[0] == holder_id:
            self.held.pop(lease_key, None)

    def is_held(self, lease_key, *, now=None):
        current = self.held.get(lease_key)
        return bool(current and current[1] > (now or utc_now()))


class FakeNotificationRepo:
    def __init__(self):
        self.saved = []

    def save(self, notification):
        self.saved.append(notification)
        return notification

    def find_by_dedupe_key(self, dedupe_key):
        return next((n for n in self.saved if n.dedupe_key == dedupe_key), None)

    def list_for_recipient(self, recipient_id, *, state="open", limit=50):
        return [
            n
            for n in self.saved
            if n.recipient_id == recipient_id and (not state or n.state == state)
        ][:limit]

    def mark_read(self, notification_id):
        for n in self.saved:
            if n.id == notification_id:
                n.state = "read"


class FakeReportConfigRepo:
    def __init__(self, configs=()):
        self._store = {(c.domain, c.report_id): c for c in configs}

    def save(self, config):
        self._store[(config.domain, config.report_id)] = config
        return config

    def find(self, domain, report_id):
        return self._store.get((domain, report_id))

    def list_by_domain(self, domain):
        return [c for c in self._store.values() if c.domain == domain]

    def list_enabled(self):
        return [c for c in self._store.values() if c.enabled]


class FakeReportRunLogRepo:
    def __init__(self):
        self.saved = []

    def save(self, log):
        for index, existing in enumerate(self.saved):
            if existing.id == log.id:
                self.saved[index] = log
                return log
        self.saved.append(log)
        return log

    def list_for_report(self, domain, report_id, limit=20):
        rows = [
            r for r in self.saved if r.domain == domain and r.report_id == report_id
        ]
        return sorted(rows, key=lambda r: r.started_at, reverse=True)[:limit]

    def count_successful_on_day(self, domain, report_id, *, start, end):
        return sum(
            1
            for r in self.saved
            if r.domain == domain
            and r.report_id == report_id
            and r.status in (STATUS_COMPLETED, STATUS_COMPLETED_WITH_ERRORS)
            and start <= r.started_at < end
        )


class FakeArtifactRepo:
    def __init__(self):
        self.saved = []
        self.pruned = []

    def save(self, artifact):
        self.saved.append(artifact)
        return artifact

    def find_by_id(self, artifact_id):
        return next((a for a in self.saved if a.id == artifact_id), None)

    def prune(self, domain, report_id, keep):
        self.pruned.append((domain, report_id, keep))


class RecordingJob:
    """Deterministic job that records the batches it was handed."""

    def __init__(self, ids, *, fail_on_batch=None, fail_identify=False):
        self.ids = list(ids)
        self.batches = []
        self._fail_on_batch = fail_on_batch
        self._fail_identify = fail_identify

    def identify(self, ctx):
        if self._fail_identify:
            raise RuntimeError("identify exploded")
        return list(self.ids)

    def process_batch(self, ctx, ids):
        self.batches.append(list(ids))
        if self._fail_on_batch == len(self.batches):
            raise RuntimeError("batch exploded")
        for record_id in ids:
            ctx.notify(
                recipient_id="user-1",
                domain=ctx.domain,
                job_id=ctx.job_id,
                kind="test",
                title=f"Review {record_id}",
                ref_type="test_record",
                ref_id=record_id,
            )
        return JobResult(processed=len(ids), created=len(ids))


def make_config(job_id="job-a", domain=DOMAIN_CRM, **overrides):
    config = SchedulerJobConfig(job_id=job_id, domain=domain, title=job_id)
    config.batch_pause_ms = 0
    for key, value in overrides.items():
        setattr(config, key, value)
    return config


def build_service(jobs=None, reports=None, configs=(), report_configs=()):
    registry = JobRegistry()
    for job, definition in jobs or []:
        registry.register(job, definition)
    service = SchedulerAppService(
        FakeConfigRepo(configs),
        FakeRunLogRepo(),
        FakeLeaseRepo(),
        FakeNotificationRepo(),
        registry=registry,
        report_registry=reports,
        report_config_repo=FakeReportConfigRepo(report_configs),
        report_run_log_repo=FakeReportRunLogRepo(),
        report_artifact_repo=FakeArtifactRepo(),
        background=False,  # run inline so assertions are deterministic
    )
    return service


# ---------------------------------------------------------------------------
# Batching pipeline
# ---------------------------------------------------------------------------


def test_chunks_splits_evenly_and_keeps_the_remainder():
    assert list(chunks(["a", "b", "c", "d", "e"], 2)) == [["a", "b"], ["c", "d"], ["e"]]
    assert list(chunks([], 10)) == []
    assert list(chunks(["a"], 0)) == [["a"]]


def test_run_job_processes_one_batch_at_a_time_and_pauses_between_them():
    job = RecordingJob([f"id-{i}" for i in range(7)])
    config = make_config(batch_size=3, batch_pause_ms=25)
    pauses = []
    log = SchedulerRunLog(job_id=config.job_id, domain=config.domain)

    run_job(
        job,
        JobContext(config=config, now=utc_now(), notify=lambda **kw: None),
        log,
        sleep=pauses.append,
    )

    assert job.batches == [
        ["id-0", "id-1", "id-2"],
        ["id-3", "id-4", "id-5"],
        ["id-6"],
    ]
    assert pauses == [0.025, 0.025, 0.025]
    assert log.status == STATUS_COMPLETED
    assert (log.identified_count, log.batch_count, log.created_count) == (7, 3, 7)


def test_run_job_caps_identified_ids_and_records_why():
    job = RecordingJob([f"id-{i}" for i in range(10)])
    config = make_config(batch_size=100, max_ids_per_run=4)
    log = SchedulerRunLog(job_id=config.job_id)

    run_job(job, JobContext(config=config, now=utc_now(), notify=lambda **kw: None), log)

    assert log.identified_count == 10
    assert job.batches == [["id-0", "id-1", "id-2", "id-3"]]
    assert "Capped at 4 of 10" in log.details[0]


def test_dry_run_never_calls_process_batch():
    job = RecordingJob(["a", "b", "c"])
    config = make_config(batch_size=2)
    log = SchedulerRunLog(job_id=config.job_id)

    run_job(
        job,
        JobContext(config=config, now=utc_now(), dry_run=True, notify=lambda **kw: None),
        log,
    )

    assert job.batches == []
    assert log.status == STATUS_DRY_RUN
    assert (log.identified_count, log.batch_count) == (3, 2)


def test_a_failing_batch_does_not_abort_the_remaining_batches():
    job = RecordingJob(["a", "b", "c", "d"])
    config = make_config(batch_size=1)
    log = SchedulerRunLog(job_id=config.job_id)

    run_job(job, JobContext(config=config, now=utc_now(), notify=lambda **kw: None), log)

    assert len(job.batches) == 4
    assert log.status == STATUS_COMPLETED


def test_identify_failure_marks_the_run_failed():
    job = RecordingJob([], fail_identify=True)
    config = make_config()
    log = SchedulerRunLog(job_id=config.job_id)

    run_job(job, JobContext(config=config, now=utc_now(), notify=lambda **kw: None), log)

    assert log.status == STATUS_FAILED
    assert "identify failed" in log.error_summary


def test_batch_errors_are_reported_without_failing_the_whole_run():
    job = RecordingJob(["a", "b", "c", "d"], fail_on_batch=2)
    config = make_config(batch_size=2)
    log = SchedulerRunLog(job_id=config.job_id)

    run_job(job, JobContext(config=config, now=utc_now(), notify=lambda **kw: None), log)

    assert log.status == STATUS_COMPLETED_WITH_ERRORS
    assert log.error_count == 1
    assert log.created_count == 2  # the first batch still landed


def test_heartbeat_refreshes_the_lease_once_per_batch():
    job = RecordingJob(["a", "b", "c"])
    config = make_config(batch_size=1)
    log = SchedulerRunLog(job_id=config.job_id)
    beats = []

    run_job(
        job,
        JobContext(config=config, now=utc_now(), notify=lambda **kw: None),
        log,
        heartbeat=lambda: beats.append(1),
    )

    assert len(beats) == 3


# ---------------------------------------------------------------------------
# Service triggers
# ---------------------------------------------------------------------------


def _definition(job_id, domain=DOMAIN_CRM):
    return JobDefinition(job_id=job_id, domain=domain, title=job_id.title())


def test_run_now_executes_a_disabled_job_but_the_wave_does_not():
    job = RecordingJob(["a"])
    config = make_config("job-a", enabled=False)
    service = build_service(
        jobs=[(job, _definition("job-a"))], configs=[config]
    )

    assert service.run_all().any_started is False
    outcome = service.run_now("job-a", actor_id="u1")

    assert outcome.any_started is True
    assert job.batches == [["a"]]


def test_run_domain_only_touches_that_domain():
    crm_job = RecordingJob(["a"])
    sales_job = RecordingJob(["b"])
    service = build_service(
        jobs=[
            (crm_job, _definition("crm-job", DOMAIN_CRM)),
            (sales_job, _definition("sales-job", DOMAIN_SALES)),
        ],
        configs=[
            make_config("crm-job", DOMAIN_CRM),
            make_config("sales-job", DOMAIN_SALES),
        ],
    )

    service.run_domain(DOMAIN_CRM)

    assert crm_job.batches == [["a"]]
    assert sales_job.batches == []


def test_run_all_runs_every_enabled_job_in_domain_order():
    order = []

    class OrderedJob(RecordingJob):
        def __init__(self, label):
            super().__init__([label])
            self.label = label

        def process_batch(self, ctx, ids):
            order.append(self.label)
            return super().process_batch(ctx, ids)

    sales_job = OrderedJob("sales")
    crm_job = OrderedJob("crm")
    service = build_service(
        jobs=[
            (sales_job, _definition("sales-job", DOMAIN_SALES)),
            (crm_job, _definition("crm-job", DOMAIN_CRM)),
        ],
        configs=[
            make_config("sales-job", DOMAIN_SALES),
            make_config("crm-job", DOMAIN_CRM),
        ],
    )

    service.run_all()

    assert order == ["crm", "sales"]  # DOMAIN_ORDER puts CRM first


def test_dry_run_writes_no_notifications():
    job = RecordingJob(["a", "b"])
    service = build_service(
        jobs=[(job, _definition("job-a"))], configs=[make_config("job-a")]
    )

    service.dry_run("job-a")

    assert job.batches == []
    assert service._notifications.saved == []
    assert service.list_runs("job-a")[0].status == STATUS_DRY_RUN


def test_a_held_lease_makes_a_second_run_skip():
    job = RecordingJob(["a"])
    service = build_service(
        jobs=[(job, _definition("job-a"))], configs=[make_config("job-a")]
    )
    service._leases.acquire("job-a", "someone-else", ttl_seconds=600)

    service.run_now("job-a")

    assert job.batches == []
    log = service.list_runs("job-a")[0]
    assert log.status == STATUS_SKIPPED and log.error_summary == "Already running"


def test_unregistered_job_is_skipped_rather_than_crashing():
    service = build_service(configs=[make_config("ghost-job")])
    service._configs.save(make_config("ghost-job"))

    outcome = service.run_now("ghost-job")

    assert outcome.any_started is True  # the wave started
    assert service.list_runs("ghost-job")[0].status == STATUS_SKIPPED


def test_a_successful_run_updates_config_state_and_next_run():
    job = RecordingJob(["a"])
    config = make_config("job-a")
    service = build_service(jobs=[(job, _definition("job-a"))], configs=[config])

    service.run_now("job-a")

    saved = service.get_config("job-a")
    assert saved.last_status == STATUS_COMPLETED
    assert saved.last_run_at is not None
    assert saved.next_run_at > utc_now()


def test_maybe_start_due_jobs_runs_only_what_is_due():
    due_job = RecordingJob(["a"])
    fresh_job = RecordingJob(["b"])
    due_config = make_config("due-job", last_run_at=utc_now() - timedelta(days=3))
    fresh_config = make_config("fresh-job", last_run_at=utc_now())
    service = build_service(
        jobs=[
            (due_job, _definition("due-job")),
            (fresh_job, _definition("fresh-job")),
        ],
        configs=[due_config, fresh_config],
    )

    service.maybe_start_due_jobs(actor_id="u1")

    assert due_job.batches == [["a"]]
    assert fresh_job.batches == []


def test_the_login_trigger_is_quiet_when_nothing_is_due():
    config = make_config("job-a", last_run_at=utc_now())
    service = build_service(
        jobs=[(RecordingJob(["a"]), _definition("job-a"))], configs=[config]
    )

    outcome = service.maybe_start_due_jobs()

    assert outcome.any_started is False
    assert outcome.message == "Nothing due"


# ---------------------------------------------------------------------------
# Notification idempotency
# ---------------------------------------------------------------------------


def test_repeat_runs_do_not_duplicate_notifications():
    job = RecordingJob(["inv-1", "inv-2"])
    service = build_service(
        jobs=[(job, _definition("job-a"))], configs=[make_config("job-a")]
    )

    service.run_now("job-a")
    service.run_now("job-a")

    assert len(service._notifications.saved) == 2
    assert {n.ref_id for n in service._notifications.saved} == {"inv-1", "inv-2"}


def test_notifications_need_a_recipient():
    service = build_service()
    assert service.create_notification(
        recipient_id="", domain=DOMAIN_CRM, job_id="j", kind="k", title="t"
    ) is None


# ---------------------------------------------------------------------------
# Scheduled reports
# ---------------------------------------------------------------------------


def _report_registry(rows=None, *, skip=False, boom=False):
    registry = ReportRegistry()

    def runner(ctx):
        if skip:
            raise ReportSkipped("Report service unavailable")
        if boom:
            raise RuntimeError("report exploded")
        return ReportRunResult(rows=list(rows or []))

    registry.register(
        ReportDefinition(
            domain=DOMAIN_CRM,
            report_id="lead_funnel",
            title="Lead Funnel",
            category="Pipeline",
        ),
        runner,
    )
    return registry


def _report_config(service, **overrides):
    config = service.get_report_config(DOMAIN_CRM, "lead_funnel")
    config.enabled = True
    for key, value in overrides.items():
        setattr(config, key, value)
    return service.save_report_config(config, actor_id="u1")


def test_rows_to_csv_uses_the_union_of_keys():
    csv_bytes = rows_to_csv([{"a": 1, "b": 2}, {"a": 3, "c": 4}])
    text = csv_bytes.decode("utf-8-sig")
    assert text.splitlines()[0] == "a,b,c"
    assert text.splitlines()[1] == "1,2,"


def test_running_a_report_stores_a_csv_artifact_and_notifies():
    service = build_service(reports=_report_registry([{"lead": "L1", "stage": "New"}]))
    _report_config(service)

    service.run_report_now(DOMAIN_CRM, "lead_funnel", actor_id="u1")

    log = service.list_report_runs(DOMAIN_CRM, "lead_funnel")[0]
    assert log.status == STATUS_COMPLETED and log.row_count == 1
    artifact = service.get_artifact(log.artifact_id)
    assert artifact is not None and b"lead" in artifact.data
    assert artifact.filename.endswith(".csv")
    assert [n.kind for n in service._notifications.saved] == ["scheduled_report"]


def test_report_rows_are_capped_and_flagged_as_truncated():
    rows = [{"n": i} for i in range(10)]
    service = build_service(reports=_report_registry(rows))
    _report_config(service, max_rows=4)

    service.run_report_now(DOMAIN_CRM, "lead_funnel")

    log = service.list_report_runs(DOMAIN_CRM, "lead_funnel")[0]
    assert log.row_count == 4 and log.truncated is True
    assert log.status == STATUS_COMPLETED_WITH_ERRORS


def test_report_dry_run_stores_no_artifact():
    service = build_service(reports=_report_registry([{"n": 1}]))
    _report_config(service)

    service.dry_run_report(DOMAIN_CRM, "lead_funnel")

    log = service.list_report_runs(DOMAIN_CRM, "lead_funnel")[0]
    assert log.status == STATUS_DRY_RUN
    assert service._report_artifacts.saved == []


def test_a_report_the_service_cannot_produce_is_skipped_not_failed():
    service = build_service(reports=_report_registry(skip=True))
    _report_config(service)

    service.run_report_now(DOMAIN_CRM, "lead_funnel")

    assert service.list_report_runs(DOMAIN_CRM, "lead_funnel")[0].status == STATUS_SKIPPED


def test_a_broken_report_is_logged_as_failed():
    service = build_service(reports=_report_registry(boom=True))
    _report_config(service)

    service.run_report_now(DOMAIN_CRM, "lead_funnel")

    log = service.list_report_runs(DOMAIN_CRM, "lead_funnel")[0]
    assert log.status == STATUS_FAILED and "report exploded" in log.error_summary


def test_a_due_scheduled_report_runs_on_login():
    service = build_service(reports=_report_registry([{"n": 1}]))
    _report_config(service, last_run_at=utc_now() - timedelta(days=3))

    service.maybe_start_due_jobs()
    service.maybe_start_due_jobs()

    logs = service.list_report_runs(DOMAIN_CRM, "lead_funnel")
    assert len([log for log in logs if log.status == STATUS_COMPLETED]) == 1


def test_the_day_guard_blocks_a_second_scheduled_report_run():
    service = build_service(reports=_report_registry([{"n": 1}]))
    config = _report_config(service, last_run_at=utc_now() - timedelta(days=3))

    service.maybe_start_due_jobs()
    # Force the schedule to look due again on the same calendar day.
    stored = service.get_report_config(DOMAIN_CRM, "lead_funnel")
    stored.last_run_at = utc_now() - timedelta(days=3)
    service._report_configs.save(stored)
    service.maybe_start_due_jobs()

    logs = service.list_report_runs(DOMAIN_CRM, "lead_funnel")
    assert len([log for log in logs if log.status == STATUS_COMPLETED]) == 1
    assert any(
        log.status == STATUS_SKIPPED and log.error_summary == "Already completed today"
        for log in logs
    )


def test_manual_report_runs_bypass_the_once_a_day_guard():
    service = build_service(reports=_report_registry([{"n": 1}]))
    _report_config(service)

    service.run_report_now(DOMAIN_CRM, "lead_funnel")
    service.run_report_now(DOMAIN_CRM, "lead_funnel")

    logs = service.list_report_runs(DOMAIN_CRM, "lead_funnel")
    assert len([log for log in logs if log.status == STATUS_COMPLETED]) == 2


def test_saving_a_report_config_defaults_the_recipient_to_the_editor():
    service = build_service(reports=_report_registry([]))
    config = _report_config(service)
    assert config.recipient_ids == ["u1"]


def test_report_run_records_the_resolved_date_window():
    service = build_service(reports=_report_registry([{"n": 1}]))
    _report_config(service, filters={"range_key": RANGE_LAST_7_DAYS})

    service.run_report_now(DOMAIN_CRM, "lead_funnel")

    start, end = resolve_relative_range(RANGE_LAST_7_DAYS)
    snapshot = service.list_report_runs(DOMAIN_CRM, "lead_funnel")[0].resolved_filters
    assert snapshot["start"] == start.isoformat()
    assert snapshot["end"] == end.isoformat()


def test_report_leases_use_a_namespaced_key():
    assert report_lease_key(DOMAIN_CRM, "lead_funnel") == "report:crm:lead_funnel"


def test_a_held_report_lease_skips_the_run():
    service = build_service(reports=_report_registry([{"n": 1}]))
    _report_config(service)
    service._leases.acquire(
        report_lease_key(DOMAIN_CRM, "lead_funnel"), "other", ttl_seconds=600
    )

    service.run_report_now(DOMAIN_CRM, "lead_funnel")

    assert service.list_report_runs(DOMAIN_CRM, "lead_funnel")[0].status == STATUS_SKIPPED
