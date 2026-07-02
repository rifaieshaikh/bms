from datetime import datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.vendor_services.entities import VendorService


class MongoVendorServiceRepository:
    def __init__(self, db: Database):
        self._collection = db.vendor_services

    def _to_doc(self, service: VendorService) -> dict:
        return {
            "_id": service.id,
            "service_name": service.service_name,
            "expense_account_id": service.expense_account_id,
            "is_active": service.is_active,
            "created_at": service.created_at,
            "updated_at": service.updated_at,
        }

    def _from_doc(self, doc: dict) -> VendorService:
        return VendorService(
            id=doc["_id"],
            service_name=doc["service_name"],
            expense_account_id=doc["expense_account_id"],
            is_active=doc.get("is_active", True),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, service: VendorService) -> VendorService:
        self._collection.replace_one(
            {"_id": service.id}, self._to_doc(service), upsert=True
        )
        return service

    def find_by_id(self, service_id: str) -> Optional[VendorService]:
        doc = self._collection.find_one({"_id": service_id})
        return self._from_doc(doc) if doc else None

    def find_by_name(self, name: str) -> Optional[VendorService]:
        doc = self._collection.find_one({"service_name": name})
        return self._from_doc(doc) if doc else None

    def list_all(self, active_only: bool = True) -> List[VendorService]:
        query = {"is_active": True} if active_only else {}
        return [self._from_doc(d) for d in self._collection.find(query)]
