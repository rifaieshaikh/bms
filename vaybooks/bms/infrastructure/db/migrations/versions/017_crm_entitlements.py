"""Seed CRM module entitlements: roles, plans, feature flags, enabled modules."""

from __future__ import annotations

from datetime import datetime

from vaybooks.bms.domain.entitlements.catalog import (
    ALL_FEATURE_KEYS,
    MODULE_CRM,
    ORG_ENTITLEMENT_ID,
    PLAN_DEFINITIONS,
    SYSTEM_ROLE_DEFINITIONS,
)

# Frozen snapshot of the modules that existed before CRM; later catalog
# additions must not change how this migration behaves on old databases.
_MODULES_BEFORE_CRM = frozenset(
    {
        "core",
        "parties",
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


def up(db) -> None:
    now = datetime.utcnow()

    # Re-upsert every system role so pattern-derived sets (Owner, Auditor, …)
    # pick up the new crm.* keys, and so the four CRM roles get created.
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

    # Re-upsert built-in plans; only Enterprise gains CRM, Starter/Growth keep
    # their existing feature sets.
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

    # Seed feature flags for the new catalog keys (existing flags untouched).
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

    # Enable the CRM module only for orgs that never restricted their modules;
    # a deliberate module selection is left exactly as the admin configured it.
    org = db.org_entitlements.find_one({"_id": ORG_ENTITLEMENT_ID})
    if org is not None:
        enabled = list(org.get("enabled_modules") or [])
        if MODULE_CRM not in enabled and _MODULES_BEFORE_CRM.issubset(set(enabled)):
            enabled.append(MODULE_CRM)
            db.org_entitlements.update_one(
                {"_id": ORG_ENTITLEMENT_ID},
                {"$set": {"enabled_modules": enabled, "updated_at": now}},
            )

    # Bump the entitlement version so signed-in sessions recompute cached keys.
    db.org_entitlements.update_one(
        {"_id": ORG_ENTITLEMENT_ID},
        {"$inc": {"version": 1}, "$set": {"updated_at": now}},
    )
