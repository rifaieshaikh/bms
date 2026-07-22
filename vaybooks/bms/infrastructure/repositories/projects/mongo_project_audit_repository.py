from __future__ import annotations

from datetime import datetime
from typing import List

from pymongo.database import Database

from vaybooks.bms.domain.projects.access import ProjectAuditEntry


class MongoProjectAuditRepository:
    def __init__(self, db: Database):
        self._collection = db.project_audit_entries

    def _to_doc(self, entry: ProjectAuditEntry) -> dict:
        return {
            "_id": entry.id,
            "project_id": entry.project_id,
            "entity_type": entry.entity_type,
            "entity_id": entry.entity_id,
            "action": entry.action,
            "actor_id": entry.actor_id,
            "actor_name": entry.actor_name,
            "reason": entry.reason,
            "before": entry.before,
            "after": entry.after,
            "created_at": entry.created_at,
        }

    def _from_doc(self, doc: dict) -> ProjectAuditEntry:
        return ProjectAuditEntry(
            id=doc["_id"],
            project_id=doc["project_id"],
            entity_type=doc.get("entity_type", ""),
            entity_id=doc.get("entity_id", ""),
            action=doc.get("action", ""),
            actor_id=doc.get("actor_id", ""),
            actor_name=doc.get("actor_name", ""),
            reason=doc.get("reason", ""),
            before=doc.get("before"),
            after=doc.get("after"),
            created_at=doc.get("created_at", datetime.utcnow()),
        )

    def save(self, entry: ProjectAuditEntry) -> ProjectAuditEntry:
        self._collection.replace_one(
            {"_id": entry.id}, self._to_doc(entry), upsert=True
        )
        return entry

    def list_by_project(self, project_id: str, limit: int = 200) -> List[ProjectAuditEntry]:
        docs = (
            self._collection.find({"project_id": project_id})
            .sort("created_at", -1)
            .limit(int(limit or 200))
        )
        return [self._from_doc(d) for d in docs]
