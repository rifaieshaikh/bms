from datetime import datetime
from typing import List, Optional

from bson import ObjectId
from pymongo.database import Database

from vaybooks.bms.domain.identity.location_access import merge_mongo_filters
from vaybooks.bms.domain.parties.delivery_partners.entities import DeliveryPartner


class MongoDeliveryPartnerRepository:
    def __init__(self, db: Database):
        self._collection = db.delivery_partners

    def _to_doc(self, partner: DeliveryPartner) -> dict:
        doc = {
            "_id": partner.id,
            "partner_name": partner.partner_name,
            "legal_display_name": partner.legal_display_name,
            "phone_number": partner.phone_number,
            "alternate_phone_number": partner.alternate_phone_number,
            "email": partner.email,
            "address_line1": partner.address_line1,
            "address_line2": partner.address_line2,
            "city": partner.city,
            "state_code": partner.state_code,
            "pincode": partner.pincode,
            "country": partner.country,
            "pan": partner.pan,
            "default_expense_ledger_id": partner.default_expense_ledger_id,
            "payment_terms": partner.payment_terms,
            "is_active": partner.is_active,
            "notes": partner.notes,
            "location_ids": list(partner.location_ids or []),
            "created_at": partner.created_at,
            "updated_at": partner.updated_at,
        }
        if partner.gstin:
            doc["gstin"] = partner.gstin
        return doc

    def _from_doc(self, doc: dict) -> DeliveryPartner:
        return DeliveryPartner(
            id=str(doc["_id"]),
            partner_name=doc["partner_name"],
            legal_display_name=doc.get("legal_display_name", ""),
            phone_number=doc["phone_number"],
            alternate_phone_number=doc.get("alternate_phone_number"),
            email=doc.get("email", ""),
            address_line1=doc.get("address_line1", ""),
            address_line2=doc.get("address_line2", ""),
            city=doc.get("city", ""),
            state_code=doc.get("state_code", ""),
            pincode=doc.get("pincode", ""),
            country=doc.get("country", "India"),
            gstin=doc.get("gstin", ""),
            pan=doc.get("pan", ""),
            default_expense_ledger_id=doc.get("default_expense_ledger_id", ""),
            payment_terms=doc.get("payment_terms", ""),
            is_active=bool(doc.get("is_active", True)),
            notes=doc.get("notes", ""),
            location_ids=list(doc.get("location_ids") or []),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, partner: DeliveryPartner) -> DeliveryPartner:
        self._collection.replace_one(
            {"_id": partner.id}, self._to_doc(partner), upsert=True
        )
        return partner

    def find_by_id(self, partner_id: str) -> Optional[DeliveryPartner]:
        if not partner_id:
            return None
        normalized = str(partner_id)
        doc = self._collection.find_one({"_id": normalized})
        if not doc and ObjectId.is_valid(normalized):
            doc = self._collection.find_one({"_id": ObjectId(normalized)})
        return self._from_doc(doc) if doc else None

    def find_by_phone(self, phone: str) -> Optional[DeliveryPartner]:
        doc = self._collection.find_one({"phone_number": phone})
        return self._from_doc(doc) if doc else None

    def find_by_gstin(self, gstin: str) -> Optional[DeliveryPartner]:
        if not gstin:
            return None
        doc = self._collection.find_one({"gstin": gstin})
        return self._from_doc(doc) if doc else None

    def search(
        self, query: str, location_filter: dict | None = None
    ) -> List[DeliveryPartner]:
        q = (query or "").strip()
        if not q:
            return self.list_all(location_filter=location_filter)
        regex = {"$regex": q, "$options": "i"}
        mongo_query = merge_mongo_filters(
            {
                "$or": [
                    {"partner_name": regex},
                    {"legal_display_name": regex},
                    {"phone_number": regex},
                    {"gstin": regex},
                ]
            },
            location_filter or {},
        )
        docs = self._collection.find(mongo_query)
        return [self._from_doc(d) for d in docs]

    def list_all(
        self, location_filter: dict | None = None
    ) -> List[DeliveryPartner]:
        query = merge_mongo_filters(location_filter or {})
        return [self._from_doc(d) for d in self._collection.find(query)]

    def list_active(
        self, location_filter: dict | None = None
    ) -> List[DeliveryPartner]:
        query = merge_mongo_filters(
            {"is_active": {"$ne": False}},
            location_filter or {},
        )
        return [self._from_doc(d) for d in self._collection.find(query)]
