from datetime import datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.projects.activity_catalog import (
    ProjectActivityConfig,
    normalize_statuses,
)
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import ActivityCategory, ActivityType


class MongoProjectActivityConfigRepository:
    def __init__(self, db: Database):
        self._collection = db.project_activity_configs

    def _to_doc(self, config: ProjectActivityConfig) -> dict:
        return {
            "_id": config.id,
            "activity_name": config.activity_name,
            "activity_type": config.activity_type.value,
            "activity_category": config.activity_category.value,
            "is_in_house": config.is_in_house,
            "requires_time_tracking": config.requires_time_tracking,
            "default_hourly_rate": config.default_hourly_rate,
            "default_amount": config.default_amount,
            "statuses": config.statuses,
            "is_active": config.is_active,
            "is_system": config.is_system,
            "created_at": config.created_at,
            "updated_at": config.updated_at,
        }

    def _from_doc(self, doc: dict) -> ProjectActivityConfig:
        return ProjectActivityConfig(
            id=doc["_id"],
            activity_name=doc["activity_name"],
            activity_type=ActivityType(doc["activity_type"]),
            activity_category=ActivityCategory(doc["activity_category"]),
            is_in_house=doc.get("is_in_house", False),
            requires_time_tracking=doc.get("requires_time_tracking", False),
            default_hourly_rate=float(doc.get("default_hourly_rate") or 0),
            default_amount=float(doc.get("default_amount") or 0),
            statuses=normalize_statuses(doc.get("statuses")),
            is_active=doc.get("is_active", True),
            is_system=bool(doc.get("is_system", False)),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, config: ProjectActivityConfig) -> ProjectActivityConfig:
        config.updated_at = utc_now()
        self._collection.replace_one(
            {"_id": config.id}, self._to_doc(config), upsert=True
        )
        return config

    def find_by_id(self, config_id: str) -> Optional[ProjectActivityConfig]:
        doc = self._collection.find_one({"_id": config_id})
        return self._from_doc(doc) if doc else None

    def find_by_name(self, name: str) -> Optional[ProjectActivityConfig]:
        doc = self._collection.find_one({"activity_name": name})
        return self._from_doc(doc) if doc else None

    def list_all(self, active_only: bool = True) -> List[ProjectActivityConfig]:
        query = {"is_active": True} if active_only else {}
        return [self._from_doc(d) for d in self._collection.find(query)]

    def delete(self, config_id: str) -> None:
        self._collection.update_one(
            {"_id": config_id}, {"$set": {"is_active": False, "updated_at": utc_now()}}
        )
