from __future__ import annotations

from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.projects.offline import ProjectOfflineDraft
from vaybooks.bms.domain.shared.date_utils import utc_now


class MongoProjectOfflineDraftRepository:
    def __init__(self, db: Database):
        self._collection = db.project_offline_drafts

    def _to_doc(self, draft: ProjectOfflineDraft) -> dict:
        return {
            "_id": draft.id,
            "project_id": draft.project_id,
            "section": draft.section,
            "payload": draft.payload or {},
            "device_id": draft.device_id,
            "synced": bool(draft.synced),
            "synced_at": draft.synced_at,
            "created_by": draft.created_by,
            "created_at": draft.created_at,
            "updated_at": draft.updated_at,
        }

    def _from_doc(self, doc: dict) -> ProjectOfflineDraft:
        return ProjectOfflineDraft(
            id=doc["_id"],
            project_id=doc.get("project_id", ""),
            section=doc.get("section", ""),
            payload=dict(doc.get("payload") or {}),
            device_id=doc.get("device_id", ""),
            synced=bool(doc.get("synced", False)),
            synced_at=doc.get("synced_at"),
            created_by=doc.get("created_by", ""),
            created_at=doc.get("created_at", utc_now()),
            updated_at=doc.get("updated_at", utc_now()),
        )

    def save(self, draft: ProjectOfflineDraft) -> ProjectOfflineDraft:
        draft.updated_at = utc_now()
        self._collection.replace_one(
            {"_id": draft.id}, self._to_doc(draft), upsert=True
        )
        return draft

    def find_by_id(self, draft_id: str) -> Optional[ProjectOfflineDraft]:
        doc = self._collection.find_one({"_id": draft_id})
        return self._from_doc(doc) if doc else None

    def list_by_project(self, project_id: str) -> List[ProjectOfflineDraft]:
        docs = self._collection.find({"project_id": project_id}).sort("created_at", -1)
        return [self._from_doc(d) for d in docs]
