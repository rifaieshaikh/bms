from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from pymongo.database import Database

from vaybooks.bms.domain.boutique.activities.entities import (
    ActivityConfig,
    normalize_statuses,
)
from vaybooks.bms.domain.shared.enums import ActivityCategory, ActivityType


class MongoActivityRepository:
    def __init__(self, db: Database):
        self._collection = db.activity_config

    def _to_doc(self, activity: ActivityConfig) -> dict:
        return {
            "_id": activity.id,
            "activity_name": activity.activity_name,
            "activity_type": activity.activity_type.value,
            "activity_category": activity.activity_category.value,
            "is_in_house": activity.is_in_house,
            "requires_time_tracking": activity.requires_time_tracking,
            "default_hourly_expense": activity.default_hourly_expense,
            "statuses": activity.statuses,
            "is_active": activity.is_active,
            "created_at": activity.created_at,
            "updated_at": activity.updated_at,
        }

    def _from_doc(self, doc: dict) -> ActivityConfig:
        return ActivityConfig(
            id=doc["_id"],
            activity_name=doc["activity_name"],
            activity_type=ActivityType(doc["activity_type"]),
            activity_category=ActivityCategory(doc["activity_category"]),
            is_in_house=doc.get("is_in_house", False),
            requires_time_tracking=doc.get("requires_time_tracking", False),
            default_hourly_expense=doc.get("default_hourly_expense", 0) or 0,
            statuses=normalize_statuses(doc.get("statuses")),
            is_active=doc.get("is_active", True),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, activity: ActivityConfig) -> ActivityConfig:
        self._collection.replace_one(
            {"_id": activity.id}, self._to_doc(activity), upsert=True
        )
        return activity

    def find_by_id(self, activity_id: str) -> Optional[ActivityConfig]:
        doc = self._collection.find_one({"_id": activity_id})
        return self._from_doc(doc) if doc else None

    def find_by_name(self, name: str) -> Optional[ActivityConfig]:
        doc = self._collection.find_one({"activity_name": name})
        return self._from_doc(doc) if doc else None

    def list_all(self, active_only: bool = True) -> List[ActivityConfig]:
        query = {"is_active": True} if active_only else {}
        return [self._from_doc(d) for d in self._collection.find(query)]
