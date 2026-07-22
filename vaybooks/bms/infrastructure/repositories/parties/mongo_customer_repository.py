from datetime import datetime
import re
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.parties.customers.entities import Customer
from vaybooks.bms.domain.shared.enums import PartyRegistrationType


class MongoCustomerRepository:
    def __init__(self, db: Database):
        self._collection = db.customers

    def _registration_type(self, value) -> PartyRegistrationType:
        if isinstance(value, PartyRegistrationType):
            return value
        try:
            return PartyRegistrationType(value)
        except ValueError:
            return PartyRegistrationType.UNREGISTERED

    def _to_doc(self, customer: Customer) -> dict:
        doc = {
            "_id": customer.id,
            "customer_name": customer.customer_name,
            "alternate_phone_number": customer.alternate_phone_number,
            "email": customer.email,
            "contact_person": customer.contact_person,
            "address_line1": customer.address_line1,
            "address_line2": customer.address_line2,
            "city": customer.city,
            "state_code": customer.state_code,
            "pincode": customer.pincode,
            "country": customer.country,
            "pan": customer.pan,
            "registration_type": customer.registration_type.value,
            "msme_number": customer.msme_number,
            "notes": customer.notes,
            "created_at": customer.created_at,
            "updated_at": customer.updated_at,
        }
        if (customer.phone_number or "").strip():
            doc["phone_number"] = customer.phone_number.strip()
        if customer.gstin:
            doc["gstin"] = customer.gstin
        if customer.legacy_address:
            doc["address"] = customer.legacy_address
        return doc

    def _from_doc(self, doc: dict) -> Customer:
        legacy = doc.get("address", "")
        return Customer(
            id=doc["_id"],
            customer_name=doc["customer_name"],
            phone_number=doc.get("phone_number") or "",
            alternate_phone_number=doc.get("alternate_phone_number"),
            email=doc.get("email", ""),
            contact_person=doc.get("contact_person", ""),
            address_line1=doc.get("address_line1", ""),
            address_line2=doc.get("address_line2", ""),
            city=doc.get("city", ""),
            state_code=doc.get("state_code", ""),
            pincode=doc.get("pincode", ""),
            country=doc.get("country", "India"),
            gstin=doc.get("gstin", ""),
            pan=doc.get("pan", ""),
            registration_type=self._registration_type(doc.get("registration_type")),
            msme_number=doc.get("msme_number", ""),
            legacy_address=legacy if not doc.get("address_line1") else "",
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

    def find_by_gstin(self, gstin: str) -> Optional[Customer]:
        if not gstin:
            return None
        doc = self._collection.find_one({"gstin": gstin.upper()})
        return self._from_doc(doc) if doc else None

    def search(self, query: str) -> List[Customer]:
        regex = {"$regex": re.escape((query or "").strip()), "$options": "i"}
        docs = self._collection.find(
            {
                "$or": [
                    {"customer_name": regex},
                    {"phone_number": regex},
                    {"gstin": regex},
                    {"pan": regex},
                    {"city": regex},
                    {"pincode": regex},
                ]
            }
        )
        return [self._from_doc(d) for d in docs]

    def list_all(self) -> List[Customer]:
        return [self._from_doc(d) for d in self._collection.find()]
