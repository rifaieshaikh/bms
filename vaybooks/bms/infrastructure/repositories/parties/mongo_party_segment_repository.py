from datetime import datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.parties.segments.entities import PartySegment


class MongoPartySegmentRepository:
    def __init__(self, db: Database):
        self._collection = db.party_segments

    def _to_doc(self, segment: PartySegment) -> dict:
        return {
            "_id": segment.id,
            "name": segment.name,
            "applies_to": list(segment.applies_to or []),
            "is_active": bool(segment.is_active),
            "created_at": segment.created_at,
            "updated_at": segment.updated_at,
        }

    def _from_doc(self, doc: dict) -> PartySegment:
        return PartySegment(
            id=doc["_id"],
            name=doc.get("name", ""),
            applies_to=list(doc.get("applies_to") or []),
            is_active=bool(doc.get("is_active", True)),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, segment: PartySegment) -> PartySegment:
        doc = self._to_doc(segment)
        self._collection.replace_one({"_id": segment.id}, doc, upsert=True)
        return segment

    def find_by_id(self, segment_id: str) -> Optional[PartySegment]:
        if not segment_id:
            return None
        doc = self._collection.find_one({"_id": segment_id})
        return self._from_doc(doc) if doc else None

    def find_by_name(self, name: str) -> Optional[PartySegment]:
        clean = (name or "").strip()
        if not clean:
            return None
        doc = self._collection.find_one(
            {"name": {"$regex": f"^{clean}$", "$options": "i"}}
        )
        return self._from_doc(doc) if doc else None

    def list_all(self, active_only: bool = False) -> List[PartySegment]:
        query = {"is_active": True} if active_only else {}
        docs = self._collection.find(query).sort("name", 1)
        return [self._from_doc(d) for d in docs]

    def delete(self, segment_id: str) -> None:
        self._collection.delete_one({"_id": segment_id})
