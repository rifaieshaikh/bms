"""Access audit collection + re-seed roles/flags with new access permissions."""

from __future__ import annotations

from datetime import datetime

from vaybooks.bms.domain.entitlements.catalog import (
    ALL_FEATURE_KEYS,
    ORG_ENTITLEMENT_ID,
    SYSTEM_ROLE_DEFINITIONS,
)


def up(db) -> None:
    now = datetime.utcnow()

    db.access_audit_entries.create_index([("actor_id", 1), ("created_at", -1)])
    db.access_audit_entries.create_index([("action", 1), ("created_at", -1)])
    db.access_audit_entries.create_index([("created_at", -1)])

    # Re-upsert system roles so pattern-derived sets pick up the new
    # settings.permissions.view / settings.audit.view keys.
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

    # Seed feature flags for any new catalog keys (existing flags untouched).
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

    # Bump the org entitlement version so already-signed-in sessions recompute
    # their cached permissions once and pick up the new Access permissions.
    db.org_entitlements.update_one(
        {"_id": ORG_ENTITLEMENT_ID},
        {"$inc": {"version": 1}, "$set": {"updated_at": now}},
    )
