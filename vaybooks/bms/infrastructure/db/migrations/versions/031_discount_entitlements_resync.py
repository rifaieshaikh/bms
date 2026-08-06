"""Re-sync system roles after expanding sales.discounts on more roles."""

from datetime import datetime

from pymongo.database import Database

from vaybooks.bms.domain.entitlements.catalog import (
    ORG_ENTITLEMENT_ID,
    SYSTEM_ROLE_DEFINITIONS,
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

    db.org_entitlements.update_one(
        {"_id": ORG_ENTITLEMENT_ID},
        {"$inc": {"version": 1}, "$set": {"updated_at": now}},
        upsert=False,
    )
