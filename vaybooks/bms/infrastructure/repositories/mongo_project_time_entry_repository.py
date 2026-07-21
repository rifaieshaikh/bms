from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.projects.entities import ProjectTimeEntry
from vaybooks.bms.infrastructure.db.bson_utils import from_bson_date, to_bson_value


class MongoProjectTimeEntryRepository:
    def __init__(self, db: Database):
        self._collection = db.project_time_entries

    def _to_doc(self, entry: ProjectTimeEntry) -> dict:
        return {
            "_id": entry.id,
            "project_id": entry.project_id,
            "activity_id": entry.activity_id,
            "worker_id": entry.worker_id,
            "worker_name": entry.worker_name,
            "work_date": to_bson_value(entry.work_date),
            "duration_minutes": entry.duration_minutes,
            "hourly_rate": float(entry.hourly_rate or 0.0),
            "labour_cost": float(entry.labour_cost or 0.0),
            "notes": entry.notes,
            "batch_id": entry.batch_id,
            "zero_cost_override": entry.zero_cost_override,
            "wbs_node_id": getattr(entry, "wbs_node_id", ""),
            "site_id": getattr(entry, "site_id", ""),
            "boq_item_id": getattr(entry, "boq_item_id", ""),
            "cost_category": getattr(entry, "cost_category", "Labour"),
            "created_at": entry.created_at,
            "updated_at": entry.updated_at,
        }

    def _from_doc(self, doc: dict) -> ProjectTimeEntry:
        return ProjectTimeEntry(
            id=doc["_id"],
            project_id=doc["project_id"],
            activity_id=doc["activity_id"],
            worker_id=doc.get("worker_id", ""),
            worker_name=doc.get("worker_name", ""),
            work_date=from_bson_date(doc["work_date"]),
            duration_minutes=int(doc.get("duration_minutes") or 0),
            hourly_rate=float(doc.get("hourly_rate") or 0.0),
            labour_cost=float(doc.get("labour_cost") or 0.0),
            notes=doc.get("notes", ""),
            batch_id=doc.get("batch_id", ""),
            zero_cost_override=bool(doc.get("zero_cost_override", False)),
            wbs_node_id=doc.get("wbs_node_id", ""),
            site_id=doc.get("site_id", ""),
            boq_item_id=doc.get("boq_item_id", ""),
            cost_category=doc.get("cost_category", "Labour"),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, entry: ProjectTimeEntry) -> ProjectTimeEntry:
        self._collection.replace_one(
            {"_id": entry.id}, self._to_doc(entry), upsert=True
        )
        return entry

    def save_many(self, entries: List[ProjectTimeEntry]) -> List[ProjectTimeEntry]:
        for entry in entries:
            self.save(entry)
        return entries

    def find_by_id(self, entry_id: str) -> Optional[ProjectTimeEntry]:
        doc = self._collection.find_one({"_id": entry_id})
        return self._from_doc(doc) if doc else None

    def list_by_project(self, project_id: str) -> List[ProjectTimeEntry]:
        docs = self._collection.find({"project_id": project_id}).sort("work_date", -1)
        return [self._from_doc(d) for d in docs]

    def list_by_activity(self, activity_id: str) -> List[ProjectTimeEntry]:
        docs = self._collection.find({"activity_id": activity_id}).sort("work_date", -1)
        return [self._from_doc(d) for d in docs]

    def delete(self, entry_id: str) -> None:
        self._collection.delete_one({"_id": entry_id})
