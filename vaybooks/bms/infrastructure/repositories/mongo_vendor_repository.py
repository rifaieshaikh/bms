from datetime import datetime
from typing import List, Optional

from bson import ObjectId
from pymongo.database import Database

from vaybooks.bms.domain.shared.enums import VendorRegistrationType
from vaybooks.bms.domain.vendors.entities import Vendor


class MongoVendorRepository:
    def __init__(self, db: Database):
        self._collection = db.vendors

    def _to_doc(self, vendor: Vendor) -> dict:
        doc = {
            "_id": vendor.id,
            "vendor_name": vendor.vendor_name,
            "phone_number": vendor.phone_number,
            "alternate_phone_number": vendor.alternate_phone_number,
            "email": vendor.email,
            "contact_person": vendor.contact_person,
            "address_line1": vendor.address_line1,
            "address_line2": vendor.address_line2,
            "city": vendor.city,
            "state_code": vendor.state_code,
            "pincode": vendor.pincode,
            "country": vendor.country,
            "pan": vendor.pan,
            "registration_type": vendor.registration_type.value,
            "msme_number": vendor.msme_number,
            "bank_account_holder": vendor.bank_account_holder,
            "bank_account_number": vendor.bank_account_number,
            "bank_ifsc": vendor.bank_ifsc,
            "bank_name": vendor.bank_name,
            "notes": vendor.notes,
            "created_at": vendor.created_at,
            "updated_at": vendor.updated_at,
        }
        if vendor.gstin:
            doc["gstin"] = vendor.gstin
        return doc

    def _registration_type(self, value) -> VendorRegistrationType:
        if isinstance(value, VendorRegistrationType):
            return value
        try:
            return VendorRegistrationType(value)
        except ValueError:
            return VendorRegistrationType.UNREGISTERED

    def _from_doc(self, doc: dict) -> Vendor:
        return Vendor(
            id=str(doc["_id"]),
            vendor_name=doc["vendor_name"],
            phone_number=doc["phone_number"],
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
            bank_account_holder=doc.get("bank_account_holder", ""),
            bank_account_number=doc.get("bank_account_number", ""),
            bank_ifsc=doc.get("bank_ifsc", ""),
            bank_name=doc.get("bank_name", ""),
            notes=doc.get("notes", ""),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, vendor: Vendor) -> Vendor:
        doc = self._to_doc(vendor)
        self._collection.replace_one({"_id": vendor.id}, doc, upsert=True)
        return vendor

    def find_by_id(self, vendor_id: str) -> Optional[Vendor]:
        if not vendor_id:
            return None
        normalized = str(vendor_id)
        doc = self._collection.find_one({"_id": normalized})
        if not doc and ObjectId.is_valid(normalized):
            doc = self._collection.find_one({"_id": ObjectId(normalized)})
        return self._from_doc(doc) if doc else None

    def find_by_phone(self, phone: str) -> Optional[Vendor]:
        doc = self._collection.find_one({"phone_number": phone})
        return self._from_doc(doc) if doc else None

    def find_by_gstin(self, gstin: str) -> Optional[Vendor]:
        if not gstin:
            return None
        doc = self._collection.find_one({"gstin": gstin.upper()})
        return self._from_doc(doc) if doc else None

    def search(self, query: str) -> List[Vendor]:
        regex = {"$regex": query, "$options": "i"}
        docs = self._collection.find(
            {
                "$or": [
                    {"vendor_name": regex},
                    {"phone_number": regex},
                    {"gstin": regex},
                    {"pan": regex},
                    {"city": regex},
                    {"pincode": regex},
                ]
            }
        )
        return [self._from_doc(d) for d in docs]

    def list_all(self) -> List[Vendor]:
        return [self._from_doc(d) for d in self._collection.find()]
