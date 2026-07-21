from __future__ import annotations

from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.projects.offline import ProjectPortalToken
from vaybooks.bms.domain.shared.date_utils import utc_now


class MongoProjectPortalTokenRepository:
    def __init__(self, db: Database):
        self._collection = db.project_portal_tokens

    def _to_doc(self, portal: ProjectPortalToken) -> dict:
        return {
            "_id": portal.id,
            "project_id": portal.project_id,
            "token": portal.token,
            "scope": portal.scope,
            "expires_at": portal.expires_at,
            "revoked": bool(portal.revoked),
            "label": portal.label,
            "created_at": portal.created_at,
        }

    def _from_doc(self, doc: dict) -> ProjectPortalToken:
        return ProjectPortalToken(
            id=doc["_id"],
            project_id=doc.get("project_id", ""),
            token=doc.get("token", ""),
            scope=doc.get("scope", "quote"),
            expires_at=doc.get("expires_at"),
            revoked=bool(doc.get("revoked", False)),
            label=doc.get("label", ""),
            created_at=doc.get("created_at", utc_now()),
        )

    def save(self, portal: ProjectPortalToken) -> ProjectPortalToken:
        self._collection.replace_one(
            {"_id": portal.id}, self._to_doc(portal), upsert=True
        )
        return portal

    def find_by_token(self, token: str) -> Optional[ProjectPortalToken]:
        if not token:
            return None
        doc = self._collection.find_one({"token": token})
        return self._from_doc(doc) if doc else None

    def list_by_project(self, project_id: str) -> List[ProjectPortalToken]:
        docs = self._collection.find({"project_id": project_id}).sort("created_at", -1)
        return [self._from_doc(d) for d in docs]
