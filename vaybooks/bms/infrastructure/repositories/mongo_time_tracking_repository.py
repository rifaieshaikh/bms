from datetime import date, datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.time_tracking.entities import TimeEntry
from vaybooks.bms.infrastructure.db.bson_utils import from_bson_date, to_bson_value


class MongoTimeTrackingRepository:
    def __init__(self, db: Database):
        self._collection = db.time_entries

    def _to_doc(self, entry: TimeEntry) -> dict:
        return {
            "_id": entry.id,
            "order_id": entry.order_id,
            "order_number": entry.order_number,
            "bill_id": entry.bill_id,
            "bill_number": entry.bill_number,
            "activity_id": entry.activity_id,
            "activity_name": entry.activity_name,
            "work_date": to_bson_value(entry.work_date),
            "start_time": entry.start_time,
            "end_time": entry.end_time,
            "duration_minutes": entry.duration_minutes,
            "worker_name": entry.worker_name,
            "notes": entry.notes,
            "created_at": entry.created_at,
            "updated_at": entry.updated_at,
        }

    def _from_doc(self, doc: dict) -> TimeEntry:
        return TimeEntry(
            id=doc["_id"],
            order_id=doc["order_id"],
            order_number=doc["order_number"],
            bill_id=doc["bill_id"],
            bill_number=doc["bill_number"],
            activity_id=doc["activity_id"],
            activity_name=doc["activity_name"],
            work_date=from_bson_date(doc["work_date"]),
            start_time=doc["start_time"],
            end_time=doc["end_time"],
            duration_minutes=doc["duration_minutes"],
            worker_name=doc.get("worker_name", ""),
            notes=doc.get("notes", ""),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, entry: TimeEntry) -> TimeEntry:
        self._collection.replace_one({"_id": entry.id}, self._to_doc(entry), upsert=True)
        return entry

    def find_by_id(self, entry_id: str) -> Optional[TimeEntry]:
        doc = self._collection.find_one({"_id": entry_id})
        return self._from_doc(doc) if doc else None

    def find_by_order(self, order_id: str) -> List[TimeEntry]:
        return [self._from_doc(d) for d in self._collection.find({"order_id": order_id})]

    def find_by_order_and_activity(
        self, order_id: str, activity_id: str
    ) -> List[TimeEntry]:
        docs = self._collection.find({"order_id": order_id, "activity_id": activity_id})
        return [self._from_doc(d) for d in docs]

    def find_by_bill_number(self, bill_number: str) -> List[TimeEntry]:
        docs = self._collection.find({"bill_number": bill_number.upper()})
        return [self._from_doc(d) for d in docs]

    def list_all(self) -> List[TimeEntry]:
        return [self._from_doc(d) for d in self._collection.find()]

    def delete(self, entry_id: str) -> None:
        self._collection.delete_one({"_id": entry_id})
