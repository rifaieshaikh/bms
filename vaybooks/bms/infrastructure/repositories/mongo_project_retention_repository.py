from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.projects.entities import ProjectRetentionEntry


class MongoProjectRetentionRepository:
    def __init__(self, db: Database):
        self._collection = db.project_retention_entries

    def _to_doc(self, entry: ProjectRetentionEntry) -> dict:
        return {
            "_id": entry.id,
            "project_id": entry.project_id,
            "invoice_voucher_id": entry.invoice_voucher_id,
            "invoice_number": entry.invoice_number,
            "withheld_amount": float(entry.withheld_amount or 0.0),
            "released_amount": float(entry.released_amount or 0.0),
            "release_voucher_id": entry.release_voucher_id,
            "created_at": entry.created_at,
        }

    def _from_doc(self, doc: dict) -> ProjectRetentionEntry:
        return ProjectRetentionEntry(
            id=doc["_id"],
            project_id=doc["project_id"],
            invoice_voucher_id=doc.get("invoice_voucher_id", ""),
            invoice_number=doc.get("invoice_number", ""),
            withheld_amount=float(doc.get("withheld_amount") or 0.0),
            released_amount=float(doc.get("released_amount") or 0.0),
            release_voucher_id=doc.get("release_voucher_id", ""),
            created_at=doc.get("created_at", datetime.utcnow()),
        )

    def save(self, entry: ProjectRetentionEntry) -> ProjectRetentionEntry:
        self._collection.replace_one(
            {"_id": entry.id}, self._to_doc(entry), upsert=True
        )
        return entry

    def find_by_id(self, entry_id: str) -> Optional[ProjectRetentionEntry]:
        doc = self._collection.find_one({"_id": entry_id})
        return self._from_doc(doc) if doc else None

    def list_by_project(self, project_id: str) -> List[ProjectRetentionEntry]:
        docs = self._collection.find({"project_id": project_id}).sort("created_at", -1)
        return [self._from_doc(d) for d in docs]
