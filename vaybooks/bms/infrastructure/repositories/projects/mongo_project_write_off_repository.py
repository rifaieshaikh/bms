from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.projects.entities import ProjectWriteOff


class MongoProjectWriteOffRepository:
    def __init__(self, db: Database):
        self._collection = db.project_write_offs

    def _to_doc(self, write_off: ProjectWriteOff) -> dict:
        return {
            "_id": write_off.id,
            "project_id": write_off.project_id,
            "party_id": write_off.party_id,
            "amount": float(write_off.amount or 0.0),
            "reason": write_off.reason,
            "voucher_id": write_off.voucher_id,
            "written_off_by": write_off.written_off_by,
            "created_at": write_off.created_at,
        }

    def _from_doc(self, doc: dict) -> ProjectWriteOff:
        return ProjectWriteOff(
            id=doc["_id"],
            project_id=doc["project_id"],
            party_id=doc.get("party_id", ""),
            amount=float(doc.get("amount") or 0.0),
            reason=doc.get("reason", ""),
            voucher_id=doc.get("voucher_id", ""),
            written_off_by=doc.get("written_off_by", ""),
            created_at=doc.get("created_at", datetime.utcnow()),
        )

    def save(self, write_off: ProjectWriteOff) -> ProjectWriteOff:
        self._collection.replace_one(
            {"_id": write_off.id}, self._to_doc(write_off), upsert=True
        )
        return write_off

    def find_by_id(self, write_off_id: str) -> Optional[ProjectWriteOff]:
        doc = self._collection.find_one({"_id": write_off_id})
        return self._from_doc(doc) if doc else None

    def list_by_project(self, project_id: str) -> List[ProjectWriteOff]:
        docs = self._collection.find({"project_id": project_id}).sort("created_at", -1)
        return [self._from_doc(d) for d in docs]
