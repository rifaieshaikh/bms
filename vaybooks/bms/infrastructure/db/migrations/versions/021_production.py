"""Production accounting module, entitlements, indexes, and scheduler jobs."""

from datetime import datetime

from pymongo.database import Database

from vaybooks.bms.domain.entitlements.catalog import (
    ALL_FEATURE_KEYS,
    MODULE_PRODUCTION,
    ORG_ENTITLEMENT_ID,
    PLAN_DEFINITIONS,
    SYSTEM_ROLE_DEFINITIONS,
)


def up(db: Database) -> None:
    from vaybooks.bms.application.schedulers.jobs import production_jobs
    from vaybooks.bms.application.schedulers.jobs._base import Deps
    from vaybooks.bms.application.schedulers.service import SchedulerAppService
    from vaybooks.bms.infrastructure.db.indexes import ensure_indexes
    from vaybooks.bms.infrastructure.repositories.schedulers.mongo_scheduler_repositories import (
        job_config_to_doc,
    )

    now = datetime.utcnow()
    ensure_indexes(db)

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
        db.feature_flags.update_one(
            {"_id": key},
            {
                "$setOnInsert": {
                    "key": key,
                    "enabled": True,
                    "description": key,
                    "updated_at": now,
                }
            },
            upsert=True,
        )

    configs = db.scheduler_job_configs
    for _job, definition in production_jobs(Deps()):
        if configs.find_one({"_id": definition.job_id}):
            continue
        config = SchedulerAppService._config_from_definition(definition)
        config.updated_at = now
        config.updated_by = "migration"
        configs.insert_one(job_config_to_doc(config))

    org = db.org_entitlements.find_one({"_id": ORG_ENTITLEMENT_ID})
    if org is not None:
        enabled = list(org.get("enabled_modules") or [])
        if MODULE_PRODUCTION not in enabled and "inventory" in enabled:
            enabled.append(MODULE_PRODUCTION)
            db.org_entitlements.update_one(
                {"_id": ORG_ENTITLEMENT_ID},
                {"$set": {"enabled_modules": enabled, "updated_at": now}},
            )
    db.org_entitlements.update_one(
        {"_id": ORG_ENTITLEMENT_ID},
        {"$inc": {"version": 1}, "$set": {"updated_at": now}},
    )
