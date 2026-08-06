from datetime import datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.identity.location_access import merge_mongo_filters
from vaybooks.bms.domain.parties.workers.entities import (
    SOURCE_CUSTOMIZATION,
    Worker,
    normalize_activity_refs,
)
from vaybooks.bms.domain.sales.commission_rules import (
    empty_commission_profile,
    profile_from_dict,
    profile_to_dict,
)


class MongoWorkerRepository:
    def __init__(self, db: Database):
        self._collection = db.workers

    def _to_doc(self, worker: Worker) -> dict:
        profile = None
        if worker.commission_enabled:
            profile = profile_to_dict(
                worker.commission_profile or empty_commission_profile()
            )
        return {
            "_id": worker.id,
            "worker_name": worker.worker_name,
            "activity_refs": [
                {"activity_id": ref.activity_id, "source": ref.source}
                for ref in worker.activity_refs
            ],
            # Legacy flat list kept in sync for older indexes/queries.
            "activity_ids": list(worker.activity_ids),
            "is_active": worker.is_active,
            "default_hourly_rate": float(worker.default_hourly_rate or 0.0),
            "linked_user_id": worker.linked_user_id or "",
            "location_ids": list(worker.location_ids or []),
            "commission_enabled": bool(worker.commission_enabled),
            "commission_profile": profile,
            "created_at": worker.created_at,
            "updated_at": worker.updated_at,
        }

    def _from_doc(self, doc: dict) -> Worker:
        refs = doc.get("activity_refs")
        if refs is None:
            # Pre-migration document: plain ids are customization activities.
            refs = list(doc.get("activity_ids") or [])
        enabled = bool(doc.get("commission_enabled"))
        raw_profile = doc.get("commission_profile")
        profile = None
        if enabled:
            profile = (
                profile_from_dict(raw_profile)
                if isinstance(raw_profile, dict)
                else empty_commission_profile()
            )
        return Worker(
            id=doc["_id"],
            worker_name=doc.get("worker_name", ""),
            activity_refs=normalize_activity_refs(refs),
            is_active=doc.get("is_active", True),
            default_hourly_rate=float(doc.get("default_hourly_rate") or 0.0),
            linked_user_id=doc.get("linked_user_id", "") or "",
            location_ids=list(doc.get("location_ids") or []),
            commission_enabled=enabled,
            commission_profile=profile,
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, worker: Worker) -> Worker:
        self._collection.replace_one({"_id": worker.id}, self._to_doc(worker), upsert=True)
        return worker

    def find_by_id(self, worker_id: str) -> Optional[Worker]:
        doc = self._collection.find_one({"_id": worker_id})
        return self._from_doc(doc) if doc else None

    def list_all(
        self,
        active_only: bool = True,
        location_filter: dict | None = None,
    ) -> List[Worker]:
        base = {"is_active": True} if active_only else {}
        query = merge_mongo_filters(base, location_filter or {})
        return [self._from_doc(d) for d in self._collection.find(query)]

    def list_commission_enabled(
        self,
        active_only: bool = True,
        location_filter: dict | None = None,
    ) -> List[Worker]:
        base = {"commission_enabled": True}
        if active_only:
            base["is_active"] = True
        query = merge_mongo_filters(base, location_filter or {})
        return [self._from_doc(d) for d in self._collection.find(query)]

    def list_by_activity(
        self,
        activity_id: str,
        source: str = SOURCE_CUSTOMIZATION,
        active_only: bool = True,
    ) -> List[Worker]:
        if not activity_id:
            return []
        ref_clause = {
            "activity_refs": {
                "$elemMatch": {"activity_id": activity_id, "source": source}
            }
        }
        if source == SOURCE_CUSTOMIZATION:
            # Pre-migration documents only carry the legacy flat id list.
            query: dict = {
                "$or": [
                    ref_clause,
                    {
                        "activity_refs": {"$exists": False},
                        "activity_ids": activity_id,
                    },
                ]
            }
        else:
            query = ref_clause
        if active_only:
            query["is_active"] = True
        return [self._from_doc(d) for d in self._collection.find(query)]
