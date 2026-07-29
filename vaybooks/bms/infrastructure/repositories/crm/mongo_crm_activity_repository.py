from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.crm.entities import CrmActivity
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.infrastructure.repositories.crm._serialize import (
    activity_from_doc,
    activity_to_doc,
    not_deleted_filter,
)


class MongoCrmActivityRepository:
    def __init__(self, db: Database):
        self._collection = db.crm_activities

    def save(self, activity: CrmActivity) -> CrmActivity:
        activity.updated_at = utc_now()
        self._collection.replace_one(
            {"_id": activity.id}, activity_to_doc(activity), upsert=True
        )
        return activity

    def find_by_id(self, activity_id: str) -> Optional[CrmActivity]:
        doc = self._collection.find_one({"_id": activity_id})
        return activity_from_doc(doc) if doc else None

    def find_by_source(
        self,
        source_module: str,
        source_txn_type: str,
        source_txn_id: str,
        activity_type_key: str,
    ) -> Optional[CrmActivity]:
        doc = self._collection.find_one(
            {
                "source_module": source_module,
                "source_txn_type": source_txn_type,
                "source_txn_id": source_txn_id,
                "activity_type_key": activity_type_key,
            }
        )
        return activity_from_doc(doc) if doc else None

    def list(
        self,
        *,
        lead_id: Optional[str] = None,
        enquiry_id: Optional[str] = None,
        customer_id: Optional[str] = None,
        assigned_user_id: Optional[str] = None,
        status: Optional[str] = None,
        activity_type: Optional[str] = None,
        branch: Optional[str] = None,
        scheduled_from: Optional[datetime] = None,
        scheduled_to: Optional[datetime] = None,
        include_deleted: bool = False,
        limit: int = 500,
        location_filter: dict | None = None,
    ) -> List[CrmActivity]:
        from vaybooks.bms.domain.identity.location_access import merge_mongo_filters

        query: dict = dict(not_deleted_filter(include_deleted))
        if lead_id:
            query["lead_id"] = lead_id
        if enquiry_id:
            query["enquiry_id"] = enquiry_id
        if customer_id:
            query["customer_id"] = customer_id
        if assigned_user_id:
            query["assigned_user_id"] = assigned_user_id
        if status:
            query["status"] = status
        if activity_type:
            query["activity_type"] = activity_type
        if branch:
            query["branch"] = branch
        if scheduled_from or scheduled_to:
            sched: dict = {}
            if scheduled_from:
                sched["$gte"] = scheduled_from
            if scheduled_to:
                sched["$lte"] = scheduled_to
            query["scheduled_at"] = sched
        query = merge_mongo_filters(query, location_filter or {})
        docs = (
            self._collection.find(query)
            .sort([("scheduled_at", 1), ("created_at", -1)])
            .limit(limit)
        )
        return [activity_from_doc(d) for d in docs]

    def list_timeline(
        self,
        *,
        lead_id: str = "",
        enquiry_id: str = "",
        customer_id: str = "",
        limit: int = 200,
    ) -> List[CrmActivity]:
        clauses = []
        if lead_id:
            clauses.append({"lead_id": lead_id})
        if enquiry_id:
            clauses.append({"enquiry_id": enquiry_id})
        if customer_id:
            clauses.append({"customer_id": customer_id})
        if not clauses:
            return []
        query = {"$or": clauses, "is_deleted": {"$ne": True}}
        docs = self._collection.find(query).sort("created_at", -1).limit(limit)
        return [activity_from_doc(d) for d in docs]
