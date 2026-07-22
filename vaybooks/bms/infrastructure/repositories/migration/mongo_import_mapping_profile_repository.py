from datetime import datetime
from typing import Dict, List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.migration.entities import ImportMappingProfile


class MongoImportMappingProfileRepository:
    def __init__(self, db: Database):
        self._collection = db.import_mapping_profiles

    def _to_doc(self, profile: ImportMappingProfile) -> dict:
        return {
            "_id": profile.id,
            "name": profile.name,
            "entity_type": profile.entity_type,
            "mapping": dict(profile.mapping),
            "created_at": profile.created_at,
            "updated_at": profile.updated_at,
        }

    def _from_doc(self, doc: dict) -> ImportMappingProfile:
        return ImportMappingProfile(
            id=doc["_id"],
            name=doc["name"],
            entity_type=doc["entity_type"],
            mapping=dict(doc.get("mapping") or {}),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, profile: ImportMappingProfile) -> ImportMappingProfile:
        self._collection.replace_one(
            {"_id": profile.id}, self._to_doc(profile), upsert=True
        )
        return profile

    def find_by_id(self, profile_id: str) -> Optional[ImportMappingProfile]:
        doc = self._collection.find_one({"_id": profile_id})
        return self._from_doc(doc) if doc else None

    def find_by_entity_and_name(
        self, entity_type: str, name: str
    ) -> Optional[ImportMappingProfile]:
        doc = self._collection.find_one(
            {"entity_type": entity_type, "name": name.strip()}
        )
        return self._from_doc(doc) if doc else None

    def list_by_entity(self, entity_type: str) -> List[ImportMappingProfile]:
        docs = self._collection.find({"entity_type": entity_type}).sort("name", 1)
        return [self._from_doc(doc) for doc in docs]

    def delete(self, profile_id: str) -> None:
        self._collection.delete_one({"_id": profile_id})
