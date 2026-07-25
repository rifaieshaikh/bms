"""Seed warehouse and retail store system roles."""

from __future__ import annotations

from datetime import datetime

from vaybooks.bms.domain.entitlements.catalog import (
    ROLE_STORE_ASSOCIATE,
    ROLE_STORE_MANAGER,
    ROLE_WAREHOUSE_MANAGER,
    SYSTEM_ROLE_DEFINITIONS,
)

NEW_ROLE_IDS = (
    ROLE_WAREHOUSE_MANAGER,
    ROLE_STORE_MANAGER,
    ROLE_STORE_ASSOCIATE,
)


def up(db) -> None:
    now = datetime.utcnow()
    for role_id in NEW_ROLE_IDS:
        meta = SYSTEM_ROLE_DEFINITIONS[role_id]
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
