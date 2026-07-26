from datetime import date, datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.store.activities.entities import CREATED_STATUS
from vaybooks.bms.domain.store.time_tracking.entities import StoreTimeEntry
from vaybooks.bms.infrastructure.db.bson_utils import from_bson_date, to_bson_value


class MongoStoreTimeTrackingRepository:
    def __init__(self, db: Database):
        self._collection = db.store_time_entries

    def _to_doc(self, entry: StoreTimeEntry) -> dict:
        return {
            "_id": entry.id,
            "activity_id": entry.activity_id,
            "activity_name": entry.activity_name,
            "worker_id": entry.worker_id,
            "worker_name": entry.worker_name,
            "work_date": to_bson_value(entry.work_date),
            "start_time": entry.start_time,
            "end_time": entry.end_time,
            "duration_minutes": entry.duration_minutes,
            "hourly_rate": float(entry.hourly_rate or 0.0),
            "labour_cost": float(entry.labour_cost or 0.0),
            "location_id": entry.location_id or "",
            "location_name": entry.location_name or "",
            "notes": entry.notes,
            "status": entry.status,
            "completed_at": entry.completed_at,
            "created_at": entry.created_at,
            "updated_at": entry.updated_at,
        }

    def _from_doc(self, doc: dict) -> StoreTimeEntry:
        return StoreTimeEntry(
            id=doc["_id"],
            activity_id=doc["activity_id"],
            activity_name=doc.get("activity_name", ""),
            worker_id=doc.get("worker_id", ""),
            worker_name=doc.get("worker_name", ""),
            work_date=from_bson_date(doc["work_date"]),
            start_time=doc.get("start_time", ""),
            end_time=doc.get("end_time", ""),
            duration_minutes=doc.get("duration_minutes", 0),
            hourly_rate=float(doc.get("hourly_rate") or 0.0),
            labour_cost=float(doc.get("labour_cost") or 0.0),
            location_id=doc.get("location_id", "") or "",
            location_name=doc.get("location_name", "") or "",
            notes=doc.get("notes", ""),
            status=doc.get("status") or CREATED_STATUS,
            completed_at=doc.get("completed_at"),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, entry: StoreTimeEntry) -> StoreTimeEntry:
        self._collection.replace_one({"_id": entry.id}, self._to_doc(entry), upsert=True)
        return entry

    def find_by_id(self, entry_id: str) -> Optional[StoreTimeEntry]:
        doc = self._collection.find_one({"_id": entry_id})
        return self._from_doc(doc) if doc else None

    def list_all(self) -> List[StoreTimeEntry]:
        return [self._from_doc(d) for d in self._collection.find()]

    def search(
        self,
        worker_name: Optional[str] = None,
        activity_name: Optional[str] = None,
        location_id: Optional[str] = None,
        work_date_from: Optional[date] = None,
        work_date_to: Optional[date] = None,
    ) -> List[StoreTimeEntry]:
        query: dict = {}
        if worker_name:
            query["worker_name"] = {"$regex": worker_name, "$options": "i"}
        if activity_name:
            query["activity_name"] = activity_name
        if location_id:
            query["location_id"] = location_id
        if work_date_from is not None or work_date_to is not None:
            date_clause = {}
            if work_date_from is not None:
                date_clause["$gte"] = to_bson_value(work_date_from)
            if work_date_to is not None:
                date_clause["$lte"] = to_bson_value(work_date_to)
            query["work_date"] = date_clause
        if not query:
            return self.list_all()
        return [
            self._from_doc(d)
            for d in self._collection.find(query).sort("work_date", -1)
        ]

    def delete(self, entry_id: str) -> None:
        self._collection.delete_one({"_id": entry_id})
