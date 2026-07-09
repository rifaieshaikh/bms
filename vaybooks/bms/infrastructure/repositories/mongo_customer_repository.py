from datetime import datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.customers.entities import Customer


class MongoCustomerRepository:
    def __init__(self, db: Database):
        self._collection = db.customers

    def _to_doc(self, customer: Customer) -> dict:
        doc = {
            "_id": customer.id,
            "customer_name": customer.customer_name,
            "alternate_phone_number": customer.alternate_phone_number,
            "address": customer.address,
            "notes": customer.notes,
            "created_at": customer.created_at,
            "updated_at": customer.updated_at,
        }
        if (customer.phone_number or "").strip():
            doc["phone_number"] = customer.phone_number.strip()
        return doc

    def _from_doc(self, doc: dict) -> Customer:
        return Customer(
            id=doc["_id"],
            customer_name=doc["customer_name"],
            phone_number=doc.get("phone_number") or "",
            alternate_phone_number=doc.get("alternate_phone_number"),
            address=doc.get("address", ""),
            notes=doc.get("notes", ""),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, customer: Customer) -> Customer:
        doc = self._to_doc(customer)
        self._collection.replace_one({"_id": customer.id}, doc, upsert=True)
        return customer

    def find_by_id(self, customer_id: str) -> Optional[Customer]:
        doc = self._collection.find_one({"_id": customer_id})
        return self._from_doc(doc) if doc else None

    def find_by_phone(self, phone: str) -> Optional[Customer]:
        phone = (phone or "").strip()
        if not phone:
            return None
        doc = self._collection.find_one({"phone_number": phone})
        return self._from_doc(doc) if doc else None

    def search(self, query: str) -> List[Customer]:
        regex = {"$regex": query, "$options": "i"}
        docs = self._collection.find(
            {"$or": [{"customer_name": regex}, {"phone_number": regex}]}
        )
        return [self._from_doc(d) for d in docs]

    def list_all(self) -> List[Customer]:
        return [self._from_doc(d) for d in self._collection.find()]
