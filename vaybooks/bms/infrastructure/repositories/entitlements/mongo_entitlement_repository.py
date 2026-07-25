from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.entitlements.catalog import (
    ALL_MODULES,
    ORG_ENTITLEMENT_ID,
    PLAN_DEFINITIONS,
    PLAN_ENTERPRISE,
)
from vaybooks.bms.domain.entitlements.entities import FeatureFlag, OrgEntitlement, Plan
from vaybooks.bms.domain.shared.date_utils import utc_now


class MongoFeatureFlagRepository:
    def __init__(self, db: Database):
        self._collection = db.feature_flags

    def _to_doc(self, flag: FeatureFlag) -> dict:
        return {
            "_id": flag.key,
            "key": flag.key,
            "enabled": bool(flag.enabled),
            "description": flag.description,
            "updated_at": flag.updated_at,
        }

    def _from_doc(self, doc: dict) -> FeatureFlag:
        return FeatureFlag(
            key=doc.get("key") or doc["_id"],
            enabled=bool(doc.get("enabled", True)),
            description=doc.get("description", ""),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, flag: FeatureFlag) -> FeatureFlag:
        flag.updated_at = utc_now()
        self._collection.replace_one({"_id": flag.key}, self._to_doc(flag), upsert=True)
        return flag

    def find_by_key(self, key: str) -> Optional[FeatureFlag]:
        doc = self._collection.find_one({"_id": key})
        return self._from_doc(doc) if doc else None

    def list_all(self) -> List[FeatureFlag]:
        return [self._from_doc(d) for d in self._collection.find().sort("key", 1)]


class MongoPlanRepository:
    def __init__(self, db: Database):
        self._collection = db.plans

    def _to_doc(self, plan: Plan) -> dict:
        return {
            "_id": plan.id,
            "name": plan.name,
            "feature_keys": list(plan.feature_keys or []),
            "description": plan.description,
            "is_system": bool(plan.is_system),
            "updated_at": plan.updated_at,
        }

    def _from_doc(self, doc: dict) -> Plan:
        # Docs seeded before custom plans existed have no is_system flag.
        default_system = doc["_id"] in PLAN_DEFINITIONS
        return Plan(
            id=doc["_id"],
            name=doc.get("name", ""),
            feature_keys=list(doc.get("feature_keys") or []),
            description=doc.get("description", ""),
            is_system=bool(doc.get("is_system", default_system)),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, plan: Plan) -> Plan:
        plan.updated_at = utc_now()
        self._collection.replace_one({"_id": plan.id}, self._to_doc(plan), upsert=True)
        return plan

    def find_by_id(self, plan_id: str) -> Optional[Plan]:
        doc = self._collection.find_one({"_id": plan_id})
        return self._from_doc(doc) if doc else None

    def list_all(self) -> List[Plan]:
        return [self._from_doc(d) for d in self._collection.find().sort("name", 1)]

    def delete(self, plan_id: str) -> None:
        self._collection.delete_one({"_id": plan_id})


class MongoOrgEntitlementRepository:
    def __init__(self, db: Database):
        self._collection = db.org_entitlements

    def _to_doc(self, ent: OrgEntitlement) -> dict:
        return {
            "_id": ent.id or ORG_ENTITLEMENT_ID,
            "plan_id": ent.plan_id,
            "enabled_modules": list(ent.enabled_modules or []),
            "version": int(ent.version or 1),
            "updated_at": ent.updated_at,
        }

    def _from_doc(self, doc: dict) -> OrgEntitlement:
        return OrgEntitlement(
            id=doc.get("_id", ORG_ENTITLEMENT_ID),
            plan_id=doc.get("plan_id") or PLAN_ENTERPRISE,
            enabled_modules=list(doc.get("enabled_modules") or list(ALL_MODULES)),
            version=int(doc.get("version") or 1),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def get(self) -> Optional[OrgEntitlement]:
        doc = self._collection.find_one({"_id": ORG_ENTITLEMENT_ID})
        return self._from_doc(doc) if doc else None

    def save(self, entitlement: OrgEntitlement) -> OrgEntitlement:
        entitlement.id = ORG_ENTITLEMENT_ID
        entitlement.updated_at = utc_now()
        self._collection.replace_one(
            {"_id": ORG_ENTITLEMENT_ID}, self._to_doc(entitlement), upsert=True
        )
        return entitlement
