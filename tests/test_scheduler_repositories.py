"""Scheduler document mapping and the migration that provisions the module."""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pytest

from vaybooks.bms.domain.schedulers.entities import (
    DOMAIN_CRM,
    SchedulerJobConfig,
    SchedulerNotification,
    SchedulerReportConfig,
    SchedulerReportRunLog,
    SchedulerRunLog,
)
from vaybooks.bms.domain.schedulers.schedule import FREQ_WEEKLY, ScheduleSpec
from vaybooks.bms.domain.schedulers.time import utc_now
from vaybooks.bms.infrastructure.repositories.schedulers.mongo_scheduler_repositories import (
    job_config_from_doc,
    job_config_to_doc,
    notification_from_doc,
    notification_to_doc,
    report_config_from_doc,
    report_config_to_doc,
    report_run_log_from_doc,
    report_run_log_to_doc,
    run_log_from_doc,
    run_log_to_doc,
)

# ---------------------------------------------------------------------------
# A very small Mongo stand-in: enough for the operations migration 019 performs
# ---------------------------------------------------------------------------


def _matches(doc: Dict[str, Any], query: Dict[str, Any]) -> bool:
    return all(doc.get(key) == value for key, value in query.items())


class FakeCollection:
    def __init__(self, name: str):
        self.name = name
        self.docs: List[Dict[str, Any]] = []
        self.indexes: List[tuple] = []

    def create_index(self, keys, **kwargs):
        self.indexes.append((keys, kwargs))

    def find_one(self, query=None, projection=None):
        for doc in self.docs:
            if _matches(doc, query or {}):
                return dict(doc)
        return None

    def find(self, query=None, projection=None):
        return [dict(d) for d in self.docs if _matches(d, query or {})]

    def insert_one(self, doc):
        self.docs.append(dict(doc))

    def replace_one(self, query, doc, upsert=False):
        for index, existing in enumerate(self.docs):
            if _matches(existing, query):
                self.docs[index] = dict(doc)
                return
        if upsert:
            self.docs.append(dict(doc))

    def update_one(self, query, update, upsert=False):
        target = None
        for doc in self.docs:
            if _matches(doc, query):
                target = doc
                break
        if target is None:
            if not upsert:
                return
            target = dict(query)
            self.docs.append(target)
        for key, value in (update.get("$set") or {}).items():
            target[key] = value
        for key, value in (update.get("$inc") or {}).items():
            target[key] = (target.get(key) or 0) + value


class FakeDatabase:
    def __init__(self):
        self._collections: Dict[str, FakeCollection] = {}

    def __getattr__(self, name):
        return self[name]

    def __getitem__(self, name):
        if name not in self._collections:
            self._collections[name] = FakeCollection(name)
        return self._collections[name]


# ---------------------------------------------------------------------------
# Document mapping round trips
# ---------------------------------------------------------------------------


def test_job_config_round_trips_through_a_document():
    config = SchedulerJobConfig(job_id="crm.demo", domain=DOMAIN_CRM, title="Demo")
    config.apply_schedule(ScheduleSpec(FREQ_WEEKLY, "07:15", weekday=2))
    config.threshold_days = 9
    config.reminder_offsets_days = [0, 3, 7]
    config.minimum_amount = 1500.5
    config.options = {"priorities": ["High"]}
    config.last_run_at = utc_now()
    config.fallback_user_id = "ops-1"

    restored = job_config_from_doc(job_config_to_doc(config))

    assert restored.job_id == "crm.demo"
    assert restored.frequency == FREQ_WEEKLY and restored.weekday == 2
    assert restored.time_of_day == "07:15"
    assert restored.cron_expression == "15 7 * * 3"
    assert restored.reminder_offsets_days == [0, 3, 7]
    assert restored.minimum_amount == pytest.approx(1500.5)
    assert restored.options == {"priorities": ["High"]}
    assert restored.last_run_at == config.last_run_at
    assert restored.fallback_user_id == "ops-1"


def test_a_document_missing_optional_fields_falls_back_to_defaults():
    restored = job_config_from_doc({"_id": "crm.demo", "domain": DOMAIN_CRM})

    assert restored.job_id == "crm.demo"
    assert restored.frequency == "daily" and restored.time_of_day == "06:00"
    assert restored.batch_size > 0 and restored.max_ids_per_run > 0
    assert restored.enabled is True


def test_run_log_round_trips_including_counters():
    log = SchedulerRunLog(job_id="crm.demo", domain=DOMAIN_CRM)
    log.identified_count = 12
    log.created_count = 7
    log.error_count = 1
    log.batch_count = 3
    log.details = ["capped"]
    log.finished_at = log.started_at + timedelta(seconds=4)

    restored = run_log_from_doc(run_log_to_doc(log))

    assert restored.id == log.id
    assert (restored.identified_count, restored.created_count) == (12, 7)
    assert restored.error_count == 1 and restored.batch_count == 3
    assert restored.details == ["capped"]
    assert restored.duration_seconds == pytest.approx(4.0)


def test_notification_round_trips_with_its_dedupe_key():
    notification = SchedulerNotification(
        recipient_id="u1",
        domain=DOMAIN_CRM,
        kind="crm.demo",
        title="Chase this",
        ref_type="invoice",
        ref_id="inv-1",
        dedupe_key=SchedulerNotification.build_dedupe_key(
            "u1", "crm.demo", "invoice", "inv-1"
        ),
        metadata={"total": 100},
    )

    restored = notification_from_doc(notification_to_doc(notification))

    assert restored.dedupe_key == "u1|crm.demo|invoice|inv-1|open"
    assert restored.metadata == {"total": 100}
    assert restored.state == "open"


def test_the_dedupe_key_separates_recipients_jobs_and_references():
    build = SchedulerNotification.build_dedupe_key
    base = build("u1", "job", "invoice", "inv-1")
    assert base != build("u2", "job", "invoice", "inv-1")
    assert base != build("u1", "other", "invoice", "inv-1")
    assert base != build("u1", "job", "invoice", "inv-2")


def test_report_config_and_run_log_round_trip():
    config = SchedulerReportConfig(
        domain=DOMAIN_CRM,
        report_id="lead_funnel",
        report_title="Lead Funnel",
        enabled=True,
        filters={"range_key": "last_7_days", "assigned_user_id": "u1"},
        recipient_ids=["u1", "u2"],
        max_rows=1234,
    )
    restored = report_config_from_doc(report_config_to_doc(config))
    assert restored.filters["assigned_user_id"] == "u1"
    assert restored.recipient_ids == ["u1", "u2"]
    assert restored.max_rows == 1234

    log = SchedulerReportRunLog(
        domain=DOMAIN_CRM,
        report_id="lead_funnel",
        row_count=42,
        truncated=True,
        artifact_id="a-1",
        resolved_filters={"start": "2026-07-01"},
    )
    restored_log = report_run_log_from_doc(report_run_log_to_doc(log))
    assert restored_log.row_count == 42 and restored_log.truncated is True
    assert restored_log.artifact_id == "a-1"
    assert restored_log.resolved_filters == {"start": "2026-07-01"}


# ---------------------------------------------------------------------------
# Indexes and migration 019
# ---------------------------------------------------------------------------


def _run_migration(db):
    import importlib

    module = importlib.import_module(
        "vaybooks.bms.infrastructure.db.migrations.versions.019_schedulers"
    )
    module.up(db)
    return module


def test_scheduler_indexes_cover_the_hot_lookups():
    from vaybooks.bms.infrastructure.db.scheduler_indexes import ensure_scheduler_indexes

    db = FakeDatabase()
    ensure_scheduler_indexes(db)

    names = {kwargs.get("name") for _keys, kwargs in db.scheduler_job_configs.indexes}
    assert "scheduler_job_id" in names
    lease_names = {kwargs.get("name") for _k, kwargs in db.scheduler_job_leases.indexes}
    assert "scheduler_lease_key" in lease_names
    dedupe = next(
        kwargs
        for _keys, kwargs in db.scheduler_notifications.indexes
        if kwargs.get("name") == "scheduler_notifications_dedupe_partial"
    )
    # Partial, so the many rows without a dedupe key never collide.
    assert dedupe["unique"] is True and "partialFilterExpression" in dedupe


def test_the_migration_seeds_one_config_per_registered_job():
    from vaybooks.bms.application.schedulers.jobs import all_jobs
    from vaybooks.bms.application.schedulers.jobs._base import Deps

    db = FakeDatabase()
    _run_migration(db)

    expected = {definition.job_id for _job, definition in all_jobs(Deps())}
    seeded = {doc["job_id"] for doc in db.scheduler_job_configs.docs}
    assert seeded == expected
    assert all(doc["cron_expression"] for doc in db.scheduler_job_configs.docs)
    assert all(doc["updated_by"] == "migration" for doc in db.scheduler_job_configs.docs)


def test_rerunning_the_migration_keeps_edited_configs():
    db = FakeDatabase()
    _run_migration(db)
    edited = db.scheduler_job_configs.docs[0]
    edited["enabled"] = False
    edited["time_of_day"] = "21:30"
    job_id = edited["job_id"]
    before = len(db.scheduler_job_configs.docs)

    _run_migration(db)

    after = [d for d in db.scheduler_job_configs.docs if d["job_id"] == job_id][0]
    assert len(db.scheduler_job_configs.docs) == before
    assert after["enabled"] is False and after["time_of_day"] == "21:30"


def test_the_migration_registers_the_schedulers_permissions():
    db = FakeDatabase()
    _run_migration(db)

    flags = {doc["_id"] for doc in db.feature_flags.docs}
    assert {"schedulers.view", "schedulers.run", "schedulers.edit"} <= flags
    owner = next(d for d in db.roles.docs if d["_id"] == "role_owner")
    assert "schedulers.run" in owner["permission_keys"]
    growth = next(d for d in db.plans.docs if d["_id"] == "growth")
    assert "schedulers.view" in growth["feature_keys"]


def test_an_org_on_every_module_gains_schedulers():
    db = FakeDatabase()
    db.org_entitlements.insert_one(
        {
            "_id": "default",
            "enabled_modules": [
                "core",
                "parties",
                "crm",
                "boutique",
                "projects",
                "sales",
                "purchases",
                "inventory",
                "finance",
                "migration",
                "settings",
                "system",
            ],
            "version": 4,
        }
    )

    _run_migration(db)

    org = db.org_entitlements.find_one({"_id": "default"})
    assert "schedulers" in org["enabled_modules"]
    assert org["version"] == 5


def test_an_org_with_a_deliberate_module_subset_is_left_alone():
    db = FakeDatabase()
    db.org_entitlements.insert_one(
        {
            "_id": "default",
            "enabled_modules": ["core", "parties", "sales"],
            "version": 1,
        }
    )

    _run_migration(db)

    org = db.org_entitlements.find_one({"_id": "default"})
    assert "schedulers" not in org["enabled_modules"]
