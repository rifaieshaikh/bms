"""Re-sync plans and roles so settings.discounts is entitlement-visible.

Migration 032 updated roles but left plan.feature_keys stale (still missing
settings.discounts.*). effective_keys = plan ∩ modules ∩ flags ∩ role, so the
Discounts settings page stayed hidden.
"""

from datetime import datetime

from pymongo.database import Database

from vaybooks.bms.domain.entitlements.catalog import (
    ORG_ENTITLEMENT_ID,
    PLAN_DEFINITIONS,
    SYSTEM_ROLE_DEFINITIONS,
)

_DISCOUNT_KEYS = (
    "settings.discounts.view",
    "settings.discounts.edit",
)


def up(db: Database) -> None:
    now = datetime.utcnow()

    for role_id, meta in SYSTEM_ROLE_DEFINITIONS.items():
        existing = db.roles.find_one({"_id": role_id})
        db.roles.replace_one(
            {"_id": role_id},
            {
                "_id": role_id,
                "name": meta["name"],
                "description": meta.get("description", ""),
                "is_system": True,
                "permission_keys": list(meta.get("permission_keys") or []),
                "created_at": (existing or {}).get("created_at", now),
                "updated_at": now,
            },
            upsert=True,
        )

    for plan_id, meta in PLAN_DEFINITIONS.items():
        existing = db.plans.find_one({"_id": plan_id})
        db.plans.replace_one(
            {"_id": plan_id},
            {
                "_id": plan_id,
                "name": meta["name"],
                "description": meta.get("description", ""),
                "feature_keys": list(meta.get("feature_keys") or []),
                "created_at": (existing or {}).get("created_at", now),
                "updated_at": now,
            },
            upsert=True,
        )

    # Belt-and-suspenders: ensure discount keys exist on every plan document.
    db.plans.update_many(
        {},
        {
            "$addToSet": {"feature_keys": {"$each": list(_DISCOUNT_KEYS)}},
            "$set": {"updated_at": now},
        },
    )

    for key in _DISCOUNT_KEYS:
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

    # Strip legacy sales.discounts keys from any roles still carrying them.
    db.roles.update_many(
        {},
        {
            "$pull": {
                "permission_keys": {
                    "$in": [
                        "sales.discounts.view",
                        "sales.discounts.edit",
                        "sales.discounts.create",
                    ]
                }
            },
            "$set": {"updated_at": now},
        },
    )

    # Ensure owner / settings-admin style roles that may be custom still get keys
    # when they already have other settings.* permissions.
    for role in db.roles.find(
        {
            "$or": [
                {"permission_keys": "settings.business.view"},
                {"permission_keys": "settings.services.view"},
                {"permission_keys": {"$regex": "^settings\\."}},
            ]
        }
    ):
        keys = set(role.get("permission_keys") or [])
        if keys.intersection(_DISCOUNT_KEYS) == set(_DISCOUNT_KEYS):
            continue
        keys.update(_DISCOUNT_KEYS)
        db.roles.update_one(
            {"_id": role["_id"]},
            {
                "$set": {
                    "permission_keys": sorted(keys),
                    "updated_at": now,
                }
            },
        )

    db.org_entitlements.update_one(
        {"_id": ORG_ENTITLEMENT_ID},
        {"$inc": {"version": 1}, "$set": {"updated_at": now}},
        upsert=False,
    )
