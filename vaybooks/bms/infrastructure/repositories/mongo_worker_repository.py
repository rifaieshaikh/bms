from datetime import datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.workers.entities import Worker


class MongoWorkerRepository:
    def __init__(self, db: Database):
        self._collection = db.workers

    def _to_doc(self, worker: Worker) -> dict:
        return {
            "_id": worker.id,
            "worker_name": worker.worker_name,
            "activity_ids": list(worker.activity_ids or []),
            "is_active": worker.is_active,
            "default_hourly_rate": float(worker.default_hourly_rate or 0.0),
            "created_at": worker.created_at,
            "updated_at": worker.updated_at,
        }

    def _from_doc(self, doc: dict) -> Worker:
        return Worker(
            id=doc["_id"],
            worker_name=doc.get("worker_name", ""),
            activity_ids=list(doc.get("activity_ids") or []),
            is_active=doc.get("is_active", True),
            default_hourly_rate=float(doc.get("default_hourly_rate") or 0.0),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, worker: Worker) -> Worker:
        self._collection.replace_one({"_id": worker.id}, self._to_doc(worker), upsert=True)
        return worker

    def find_by_id(self, worker_id: str) -> Optional[Worker]:
        doc = self._collection.find_one({"_id": worker_id})
        return self._from_doc(doc) if doc else None

    def list_all(self, active_only: bool = True) -> List[Worker]:
        query = {"is_active": True} if active_only else {}
        return [self._from_doc(d) for d in self._collection.find(query)]

    def list_by_activity(self, activity_id: str, active_only: bool = True) -> List[Worker]:
        if not activity_id:
            return []
        query: dict = {"activity_ids": activity_id}
        if active_only:
            query["is_active"] = True
        return [self._from_doc(d) for d in self._collection.find(query)]

