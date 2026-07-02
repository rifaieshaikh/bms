from datetime import datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.vendors.entities import Vendor


class MongoVendorRepository:
    def __init__(self, db: Database):
        self._collection = db.vendors

    def _to_doc(self, vendor: Vendor) -> dict:
        return {
            "_id": vendor.id,
            "vendor_name": vendor.vendor_name,
            "phone_number": vendor.phone_number,
            "alternate_phone_number": vendor.alternate_phone_number,
            "address": vendor.address,
            "notes": vendor.notes,
            "created_at": vendor.created_at,
            "updated_at": vendor.updated_at,
        }

    def _from_doc(self, doc: dict) -> Vendor:
        return Vendor(
            id=doc["_id"],
            vendor_name=doc["vendor_name"],
            phone_number=doc["phone_number"],
            alternate_phone_number=doc.get("alternate_phone_number"),
            address=doc.get("address", ""),
            notes=doc.get("notes", ""),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, vendor: Vendor) -> Vendor:
        doc = self._to_doc(vendor)
        self._collection.replace_one({"_id": vendor.id}, doc, upsert=True)
        return vendor

    def find_by_id(self, vendor_id: str) -> Optional[Vendor]:
        doc = self._collection.find_one({"_id": vendor_id})
        return self._from_doc(doc) if doc else None

    def find_by_phone(self, phone: str) -> Optional[Vendor]:
        doc = self._collection.find_one({"phone_number": phone})
        return self._from_doc(doc) if doc else None

    def search(self, query: str) -> List[Vendor]:
        regex = {"$regex": query, "$options": "i"}
        docs = self._collection.find(
            {"$or": [{"vendor_name": regex}, {"phone_number": regex}]}
        )
        return [self._from_doc(d) for d in docs]

    def list_all(self) -> List[Vendor]:
        return [self._from_doc(d) for d in self._collection.find()]
