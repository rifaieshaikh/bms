"""Store activities: seed catalog, worker activity refs, entitlements.

- Seeds the store activity catalog (baseline retail activities).
- Converts ``workers.activity_ids`` into source-qualified ``activity_refs``
  (all pre-existing ids belong to the customization catalog).
- Re-upserts system roles / plans and seeds feature flags so the new
  ``settings.store_activities.*`` and ``parties.store_tasks.*`` permissions
  become available.
"""

from __future__ import annotations

from datetime import datetime

from pymongo.database import Database

from vaybooks.bms.domain.entitlements.catalog import (
    ALL_FEATURE_KEYS,
    ORG_ENTITLEMENT_ID,
    PLAN_DEFINITIONS,
    SYSTEM_ROLE_DEFINITIONS,
)


def _seed_store_activities(db: Database) -> None:
    from vaybooks.bms.domain.shared.enums import ActivityCategory
    from vaybooks.bms.domain.store.activities.entities import StoreActivityConfig
    from vaybooks.bms.infrastructure.repositories.store.mongo_store_activity_repository import (
        MongoStoreActivityRepository,
    )

    repo = MongoStoreActivityRepository(db)
    if repo.list_all(active_only=False):
        return

    seeds = [
        ("Billing", ActivityCategory.IN_HOUSE_SERVICE, 150.0),
        ("Packing", ActivityCategory.IN_HOUSE_SERVICE, 120.0),
        ("Floor Assistance", ActivityCategory.IN_HOUSE_SERVICE, 120.0),
        ("Inventory Count", ActivityCategory.IN_HOUSE_SERVICE, 150.0),
    ]
    for name, category, hourly in seeds:
        config = StoreActivityConfig(
            activity_name=name,
            activity_type=None,
            default_hourly_expense=hourly,
        )
        config.apply_category(category)
        repo.save(config)


def _convert_worker_activity_refs(db: Database) -> None:
    for doc in db.workers.find({"activity_refs": {"$exists": False}}):
        refs = [
            {"activity_id": activity_id, "source": "customization"}
            for activity_id in (doc.get("activity_ids") or [])
            if activity_id
        ]
        db.workers.update_one(
            {"_id": doc["_id"]}, {"$set": {"activity_refs": refs}}
        )


def up(db: Database) -> None:
    now = datetime.utcnow()

    _seed_store_activities(db)
    _convert_worker_activity_refs(db)

    # Re-upsert system roles so pattern-derived sets pick up the new
    # store_activities / store_tasks permissions.
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

    db.org_entitlements.update_one(
        {"_id": ORG_ENTITLEMENT_ID},
        {"$inc": {"version": 1}, "$set": {"updated_at": now}},
    )
