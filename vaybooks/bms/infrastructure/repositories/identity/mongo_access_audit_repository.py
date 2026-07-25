from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.identity.audit import AccessAuditEntry


class MongoAccessAuditRepository:
    def __init__(self, db: Database):
        self._collection = db.access_audit_entries

    def _to_doc(self, entry: AccessAuditEntry) -> dict:
        return {
            "_id": entry.id,
            "action": entry.action,
            "actor_id": entry.actor_id,
            "actor_name": entry.actor_name,
            "target_type": entry.target_type,
            "target_id": entry.target_id,
            "target_label": entry.target_label,
            "detail": dict(entry.detail or {}),
            "created_at": entry.created_at,
        }

    def _from_doc(self, doc: dict) -> AccessAuditEntry:
        return AccessAuditEntry(
            id=doc["_id"],
            action=doc.get("action", ""),
            actor_id=doc.get("actor_id", ""),
            actor_name=doc.get("actor_name", ""),
            target_type=doc.get("target_type", ""),
            target_id=doc.get("target_id", ""),
            target_label=doc.get("target_label", ""),
            detail=dict(doc.get("detail") or {}),
            created_at=doc.get("created_at", datetime.utcnow()),
        )

    def save(self, entry: AccessAuditEntry) -> AccessAuditEntry:
        self._collection.insert_one(self._to_doc(entry))
        return entry

    def count(self) -> int:
        return int(self._collection.estimated_document_count())

    def list_entries(
        self,
        *,
        actor_id: str = "",
        action: str = "",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 200,
    ) -> List[AccessAuditEntry]:
        query: dict = {}
        if actor_id:
            query["actor_id"] = actor_id
        if action:
            query["action"] = action
        created: dict = {}
        if start is not None:
            created["$gte"] = start
        if end is not None:
            created["$lte"] = end
        if created:
            query["created_at"] = created
        docs = self._collection.find(query).sort("created_at", -1).limit(limit)
        return [self._from_doc(d) for d in docs]
