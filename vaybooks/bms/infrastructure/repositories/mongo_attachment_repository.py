from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from bson.binary import Binary
from pymongo.database import Database

from vaybooks.bms.domain.attachments.entities import Attachment
from vaybooks.bms.domain.shared.enums import AttachmentCategory


class MongoAttachmentRepository:
    def __init__(self, db: Database):
        self._collection = db.attachments

    def _to_doc(self, attachment: Attachment) -> dict:
        return {
            "_id": attachment.id,
            "order_id": attachment.order_id,
            "item_id": attachment.item_id,
            "category": attachment.category.value,
            "name": attachment.name,
            "content_type": attachment.content_type,
            "data": Binary(attachment.data),
            "size_bytes": attachment.size_bytes,
            "uploaded_by": attachment.uploaded_by,
            "uploaded_at": attachment.uploaded_at,
        }

    def _from_doc(self, doc: dict) -> Attachment:
        raw = doc.get("data") or b""
        if isinstance(raw, Binary):
            raw = bytes(raw)
        return Attachment(
            id=doc["_id"],
            order_id=doc["order_id"],
            item_id=doc["item_id"],
            category=AttachmentCategory(doc["category"]),
            name=doc.get("name", ""),
            content_type=doc.get("content_type", "application/octet-stream"),
            data=bytes(raw),
            size_bytes=int(doc.get("size_bytes") or len(raw)),
            uploaded_by=doc.get("uploaded_by", ""),
            uploaded_at=doc.get("uploaded_at", datetime.utcnow()),
        )

    def save(self, attachment: Attachment) -> Attachment:
        self._collection.replace_one(
            {"_id": attachment.id}, self._to_doc(attachment), upsert=True
        )
        return attachment

    def find_by_id(self, attachment_id: str) -> Optional[Attachment]:
        doc = self._collection.find_one({"_id": attachment_id})
        return self._from_doc(doc) if doc else None

    def list_by_item(
        self,
        item_id: str,
        category: Optional[AttachmentCategory] = None,
    ) -> List[Attachment]:
        query: dict = {"item_id": item_id}
        if category is not None:
            query["category"] = category.value
        docs = self._collection.find(query).sort("uploaded_at", -1)
        return [self._from_doc(d) for d in docs]

    def list_by_order(self, order_id: str) -> List[Attachment]:
        docs = self._collection.find({"order_id": order_id}).sort(
            "uploaded_at", -1
        )
        return [self._from_doc(d) for d in docs]

    def delete(self, attachment_id: str) -> None:
        self._collection.delete_one({"_id": attachment_id})

    def count_by_item_category(
        self, item_id: str, category: AttachmentCategory
    ) -> int:
        return self._collection.count_documents(
            {"item_id": item_id, "category": category.value}
        )
