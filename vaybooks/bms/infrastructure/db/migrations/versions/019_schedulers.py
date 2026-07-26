"""Scheduler collections, indexes, seeded job configs, and entitlements."""

from __future__ import annotations

from datetime import datetime

from pymongo.database import Database

from vaybooks.bms.domain.entitlements.catalog import (
    ALL_FEATURE_KEYS,
    MODULE_SCHEDULERS,
    ORG_ENTITLEMENT_ID,
    PLAN_DEFINITIONS,
    SYSTEM_ROLE_DEFINITIONS,
)
from vaybooks.bms.infrastructure.db.scheduler_indexes import (
    ensure_scheduler_indexes,
    ensure_scheduler_query_indexes,
)

# Frozen snapshot of the modules that existed before Schedulers; later catalog
# additions must not change how this migration behaves on old databases.
_MODULES_BEFORE_SCHEDULERS = frozenset(
    {
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
    }
)


def _seed_job_configs(db: Database, now: datetime) -> None:
    """Insert one config per registered job, leaving edited configs untouched."""
    from vaybooks.bms.application.schedulers.jobs import all_jobs
    from vaybooks.bms.application.schedulers.jobs._base import Deps
    from vaybooks.bms.application.schedulers.service import SchedulerAppService

    collection = db.scheduler_job_configs
    from vaybooks.bms.infrastructure.repositories.schedulers.mongo_scheduler_repositories import (
        job_config_to_doc,
    )

    # Jobs are constructed with empty dependencies: only their seed definitions
    # are needed here, never their identify/process behaviour.
    for _job, definition in all_jobs(Deps()):
        if collection.find_one({"_id": definition.job_id}):
            continue
        config = SchedulerAppService._config_from_definition(definition)
        config.updated_at = now
        config.updated_by = "migration"
        collection.insert_one(job_config_to_doc(config))


def up(db: Database) -> None:
    now = datetime.utcnow()

    ensure_scheduler_indexes(db)
    ensure_scheduler_query_indexes(db)
    _seed_job_configs(db, now)

    # Re-upsert every system role so pattern-derived sets pick up schedulers.*.
    for role_id, meta in SYSTEM_ROLE_DEFINITIONS.items():
        db.roles.replace_one(
            {"_id": role_id},
            {
                "_id": role_id,
                "name": meta["name"],
                "description": meta.get("description", ""),
                "is_system": True,
                "permission_keys": list(meta.get("permission_keys") or []),
                "created_at": now,
                "updated_at": now,
            },
            upsert=True,
        )

    for plan_id, meta in PLAN_DEFINITIONS.items():
        db.plans.replace_one(
            {"_id": plan_id},
            {
                "_id": plan_id,
                "name": meta["name"],
                "description": meta.get("description", ""),
                "feature_keys": list(meta.get("feature_keys") or []),
                "updated_at": now,
            },
            upsert=True,
        )

    for key in sorted(ALL_FEATURE_KEYS):
        if db.feature_flags.find_one({"_id": key}):
            continue
        db.feature_flags.insert_one(
            {
                "_id": key,
                "key": key,
                "enabled": True,
                "description": key,
                "updated_at": now,
            }
        )

    # Enable Schedulers only for orgs that never restricted their modules; a
    # deliberate module selection is left exactly as the admin configured it.
    org = db.org_entitlements.find_one({"_id": ORG_ENTITLEMENT_ID})
    if org is not None:
        enabled = list(org.get("enabled_modules") or [])
        if MODULE_SCHEDULERS not in enabled and _MODULES_BEFORE_SCHEDULERS.issubset(
            set(enabled)
        ):
            enabled.append(MODULE_SCHEDULERS)
            db.org_entitlements.update_one(
                {"_id": ORG_ENTITLEMENT_ID},
                {"$set": {"enabled_modules": enabled, "updated_at": now}},
            )

    db.org_entitlements.update_one(
        {"_id": ORG_ENTITLEMENT_ID},
        {"$inc": {"version": 1}, "$set": {"updated_at": now}},
    )
