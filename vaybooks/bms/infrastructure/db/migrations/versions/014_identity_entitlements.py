"""Seed identity, RBAC, feature flags, plans, and org entitlements."""

from __future__ import annotations

from datetime import datetime

from vaybooks.bms.domain.entitlements.catalog import (
    ALL_FEATURE_KEYS,
    ALL_MODULES,
    DEFAULT_ADMIN_PASSWORD,
    DEFAULT_ADMIN_USERNAME,
    ORG_ENTITLEMENT_ID,
    PLAN_DEFINITIONS,
    PLAN_ENTERPRISE,
    PROJECT_APP_ROLE_TO_ROLE_ID,
    ROLE_OWNER,
    SYSTEM_ROLE_DEFINITIONS,
)
from vaybooks.bms.domain.identity.passwords import hash_password


def up(db) -> None:
    now = datetime.utcnow()

    db.users.create_index("username", unique=True)
    db.roles.create_index("name", unique=True)
    db.feature_flags.create_index("key", unique=True)
    db.plans.create_index("name", unique=True)

    # --- System roles ---
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

    # --- Plans ---
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

    # --- Feature flags ---
    for key in sorted(ALL_FEATURE_KEYS):
        existing = db.feature_flags.find_one({"_id": key})
        if existing:
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

    # --- Org entitlement ---
    if not db.org_entitlements.find_one({"_id": ORG_ENTITLEMENT_ID}):
        db.org_entitlements.insert_one(
            {
                "_id": ORG_ENTITLEMENT_ID,
                "plan_id": PLAN_ENTERPRISE,
                "enabled_modules": list(ALL_MODULES),
                "version": 1,
                "updated_at": now,
            }
        )

    # --- Migrate app_users → users ---
    for doc in db.app_users.find():
        username = (doc.get("username") or "").strip()
        if not username:
            continue
        if db.users.find_one({"username": username}):
            continue
        role_ids = []
        for raw in doc.get("global_roles") or []:
            rid = PROJECT_APP_ROLE_TO_ROLE_ID.get(raw)
            if rid and rid not in role_ids:
                role_ids.append(rid)
        if not role_ids:
            role_ids = [ROLE_OWNER]
        password_hash = doc.get("password_hash") or ""
        if not password_hash and username == DEFAULT_ADMIN_USERNAME:
            password_hash = hash_password(DEFAULT_ADMIN_PASSWORD)
        db.users.insert_one(
            {
                "_id": doc.get("_id"),
                "username": username,
                "display_name": doc.get("display_name") or username,
                "password_hash": password_hash,
                "role_ids": role_ids,
                "active": bool(doc.get("active", True)),
                "created_at": doc.get("created_at", now),
                "updated_at": now,
            }
        )

    # --- Ensure admin user ---
    admin = db.users.find_one({"username": DEFAULT_ADMIN_USERNAME})
    if not admin:
        from uuid import uuid4

        db.users.insert_one(
            {
                "_id": uuid4().hex,
                "username": DEFAULT_ADMIN_USERNAME,
                "display_name": "Administrator",
                "password_hash": hash_password(DEFAULT_ADMIN_PASSWORD),
                "role_ids": [ROLE_OWNER],
                "active": True,
                "created_at": now,
                "updated_at": now,
            }
        )
    else:
        updates = {}
        if not admin.get("password_hash"):
            updates["password_hash"] = hash_password(DEFAULT_ADMIN_PASSWORD)
        role_ids = list(admin.get("role_ids") or [])
        if ROLE_OWNER not in role_ids:
            role_ids = [ROLE_OWNER] + role_ids
            updates["role_ids"] = role_ids
        if updates:
            updates["updated_at"] = now
            db.users.update_one({"_id": admin["_id"]}, {"$set": updates})

    # --- Backfill project_memberships.role_id ---
    for m in db.project_memberships.find():
        if m.get("role_id"):
            continue
        rid = PROJECT_APP_ROLE_TO_ROLE_ID.get(m.get("role") or "")
        if rid:
            db.project_memberships.update_one(
                {"_id": m["_id"]}, {"$set": {"role_id": rid}}
            )
