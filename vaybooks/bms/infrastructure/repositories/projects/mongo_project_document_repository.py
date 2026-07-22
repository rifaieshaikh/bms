from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from bson.binary import Binary
from pymongo.database import Database

from vaybooks.bms.domain.projects.entities import ProjectDocument
from vaybooks.bms.domain.shared.enums import ProjectDocumentCategory


class MongoProjectDocumentRepository:
    def __init__(self, db: Database):
        self._collection = db.project_documents

    def _to_doc(self, document: ProjectDocument) -> dict:
        return {
            "_id": document.id,
            "project_id": document.project_id,
            "category": document.category.value,
            "name": document.name,
            "content_type": document.content_type,
            "data": Binary(document.data),
            "size_bytes": document.size_bytes,
            "uploaded_by": document.uploaded_by,
            "uploaded_at": document.uploaded_at,
            "source_ref_type": document.source_ref_type,
            "source_ref_id": document.source_ref_id,
            "is_deleted": document.is_deleted,
            "deleted_at": document.deleted_at,
        }

    def _from_doc(self, doc: dict) -> ProjectDocument:
        raw = doc.get("data") or b""
        if isinstance(raw, Binary):
            raw = bytes(raw)
        return ProjectDocument(
            id=doc["_id"],
            project_id=doc["project_id"],
            category=ProjectDocumentCategory(doc["category"]),
            name=doc.get("name", ""),
            content_type=doc.get("content_type", "application/octet-stream"),
            data=bytes(raw),
            size_bytes=int(doc.get("size_bytes") or len(raw)),
            uploaded_by=doc.get("uploaded_by", ""),
            uploaded_at=doc.get("uploaded_at", datetime.utcnow()),
            source_ref_type=doc.get("source_ref_type", ""),
            source_ref_id=doc.get("source_ref_id", ""),
            is_deleted=bool(doc.get("is_deleted", False)),
            deleted_at=doc.get("deleted_at"),
        )

    def save(self, document: ProjectDocument) -> ProjectDocument:
        self._collection.replace_one(
            {"_id": document.id}, self._to_doc(document), upsert=True
        )
        return document

    def find_by_id(self, document_id: str) -> Optional[ProjectDocument]:
        doc = self._collection.find_one({"_id": document_id})
        return self._from_doc(doc) if doc else None

    def list_by_project(
        self,
        project_id: str,
        include_deleted: bool = False,
        category: Optional[ProjectDocumentCategory] = None,
    ) -> List[ProjectDocument]:
        query: dict = {"project_id": project_id}
        if not include_deleted:
            query["is_deleted"] = False
        if category is not None:
            query["category"] = category.value
        docs = self._collection.find(query).sort("uploaded_at", -1)
        return [self._from_doc(d) for d in docs]

    def soft_delete(self, document_id: str) -> None:
        self._collection.update_one(
            {"_id": document_id},
            {
                "$set": {
                    "is_deleted": True,
                    "deleted_at": datetime.utcnow(),
                }
            },
        )
