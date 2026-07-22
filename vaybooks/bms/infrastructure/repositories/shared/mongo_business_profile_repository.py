from datetime import datetime
from typing import Optional

from pymongo.database import Database

from vaybooks.bms.domain.business.entities import BUSINESS_PROFILE_ID, BusinessProfile
from vaybooks.bms.domain.shared.document_customization import (
    DOCUMENT_TYPES,
    bank_account_from_dict,
    dataclass_to_dict,
    default_document_templates,
    template_from_dict,
)
from vaybooks.bms.domain.shared.enums import VendorRegistrationType


class MongoBusinessProfileRepository:
    def __init__(self, db: Database):
        self._collection = db.business_profile

    def _to_doc(self, profile: BusinessProfile) -> dict:
        return {
            "_id": profile.id,
            "legal_name": profile.legal_name,
            "trade_name": profile.trade_name,
            "address_line1": profile.address_line1,
            "address_line2": profile.address_line2,
            "city": profile.city,
            "state_code": profile.state_code,
            "pincode": profile.pincode,
            "country": profile.country,
            "phone": profile.phone,
            "email": profile.email,
            "gstin": profile.gstin,
            "pan": profile.pan,
            "registration_type": profile.registration_type.value,
            "composition_tax_rate": profile.composition_tax_rate,
            "bank_accounts": [
                dataclass_to_dict(account) for account in profile.bank_accounts
            ],
            "document_templates": {
                name: dataclass_to_dict(template)
                for name, template in profile.document_templates.items()
            },
            "created_at": profile.created_at,
            "updated_at": profile.updated_at,
        }

    def _from_doc(self, doc: dict) -> BusinessProfile:
        reg = doc.get("registration_type", VendorRegistrationType.UNREGISTERED.value)
        try:
            registration_type = VendorRegistrationType(reg)
        except ValueError:
            registration_type = VendorRegistrationType.UNREGISTERED
        templates = default_document_templates()
        stored_templates = doc.get("document_templates") or {}
        for name in DOCUMENT_TYPES:
            if name in stored_templates:
                templates[name] = template_from_dict(stored_templates[name])
        return BusinessProfile(
            id=str(doc["_id"]),
            legal_name=doc.get("legal_name", ""),
            trade_name=doc.get("trade_name", ""),
            address_line1=doc.get("address_line1", ""),
            address_line2=doc.get("address_line2", ""),
            city=doc.get("city", ""),
            state_code=doc.get("state_code", ""),
            pincode=doc.get("pincode", ""),
            country=doc.get("country", "India"),
            phone=doc.get("phone", ""),
            email=doc.get("email", ""),
            gstin=doc.get("gstin", ""),
            pan=doc.get("pan", ""),
            registration_type=registration_type,
            composition_tax_rate=float(doc.get("composition_tax_rate", 1.0) or 0),
            bank_accounts=[
                account
                for account in (
                    bank_account_from_dict(item)
                    for item in doc.get("bank_accounts", [])
                )
                if account is not None
            ],
            document_templates=templates,
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def get(self) -> Optional[BusinessProfile]:
        doc = self._collection.find_one({"_id": BUSINESS_PROFILE_ID})
        return self._from_doc(doc) if doc else None

    def save(self, profile: BusinessProfile) -> BusinessProfile:
        doc = self._to_doc(profile)
        self._collection.replace_one({"_id": profile.id}, doc, upsert=True)
        return profile
