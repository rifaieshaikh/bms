from datetime import datetime
from typing import List, Optional

from bson import ObjectId
from pymongo.database import Database

from vaybooks.bms.domain.identity.location_access import merge_mongo_filters
from vaybooks.bms.domain.parties.commission_agents.entities import CommissionAgent
from vaybooks.bms.domain.sales.commission_rules import (
    empty_commission_profile,
    profile_from_dict,
    profile_to_dict,
)
from vaybooks.bms.domain.shared.enums import PartyRegistrationType


class MongoCommissionAgentRepository:
    def __init__(self, db: Database):
        self._collection = db.commission_agents

    def _to_doc(self, agent: CommissionAgent) -> dict:
        doc = {
            "_id": agent.id,
            "agent_name": agent.agent_name,
            "phone_number": agent.phone_number,
            "alternate_phone_number": agent.alternate_phone_number,
            "email": agent.email,
            "contact_person": agent.contact_person,
            "address_line1": agent.address_line1,
            "address_line2": agent.address_line2,
            "city": agent.city,
            "state_code": agent.state_code,
            "pincode": agent.pincode,
            "country": agent.country,
            "pan": agent.pan,
            "registration_type": agent.registration_type.value,
            "msme_number": agent.msme_number,
            "bank_account_holder": agent.bank_account_holder,
            "bank_account_number": agent.bank_account_number,
            "bank_ifsc": agent.bank_ifsc,
            "bank_name": agent.bank_name,
            "notes": agent.notes,
            "commission_profile": profile_to_dict(
                agent.commission_profile or empty_commission_profile()
            ),
            "segment_ids": list(agent.segment_ids or []),
            "segment_names": list(agent.segment_names or []),
            "source_customer_id": agent.source_customer_id or "",
            "location_ids": list(agent.location_ids or []),
            "created_at": agent.created_at,
            "updated_at": agent.updated_at,
        }
        if agent.gstin:
            doc["gstin"] = agent.gstin
        return doc

    def _registration_type(self, value) -> PartyRegistrationType:
        if isinstance(value, PartyRegistrationType):
            return value
        try:
            return PartyRegistrationType(value)
        except ValueError:
            return PartyRegistrationType.UNREGISTERED

    def _profile_from_doc(self, doc: dict):
        if isinstance(doc.get("commission_profile"), dict):
            return profile_from_dict(doc.get("commission_profile"))
        # Legacy flat defaults → catch-all sales percentage rule.
        rate = float(doc.get("default_commission_rate") or 0)
        ctype = (doc.get("default_commission_type") or "percentage").strip().lower()
        if rate <= 0:
            return empty_commission_profile()
        from vaybooks.bms.domain.sales.commission_rules import (
            COMMISSION_TYPE_FLAT,
            COMMISSION_TYPE_PERCENTAGE,
            CommissionProfile,
            CommissionRule,
            GRAIN_INVOICE,
            SCOPE_ALL,
        )

        rule_type = (
            COMMISSION_TYPE_FLAT if ctype == "flat" else COMMISSION_TYPE_PERCENTAGE
        )
        return CommissionProfile(
            sales_rules=[
                CommissionRule(
                    scope_type=SCOPE_ALL,
                    grain=GRAIN_INVOICE,
                    commission_type=rule_type,
                    commission_rate=rate,
                )
            ]
        )

    def _from_doc(self, doc: dict) -> CommissionAgent:
        return CommissionAgent(
            id=str(doc["_id"]),
            agent_name=doc["agent_name"],
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
            commission_profile=self._profile_from_doc(doc),
            segment_ids=list(doc.get("segment_ids") or []),
            segment_names=list(doc.get("segment_names") or []),
            source_customer_id=doc.get("source_customer_id", "") or "",
            location_ids=list(doc.get("location_ids") or []),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, agent: CommissionAgent) -> CommissionAgent:
        doc = self._to_doc(agent)
        self._collection.replace_one({"_id": agent.id}, doc, upsert=True)
        return agent

    def find_by_id(self, agent_id: str) -> Optional[CommissionAgent]:
        if not agent_id:
            return None
        normalized = str(agent_id)
        doc = self._collection.find_one({"_id": normalized})
        if not doc and ObjectId.is_valid(normalized):
            doc = self._collection.find_one({"_id": ObjectId(normalized)})
        return self._from_doc(doc) if doc else None

    def find_by_phone(self, phone: str) -> Optional[CommissionAgent]:
        doc = self._collection.find_one({"phone_number": phone})
        return self._from_doc(doc) if doc else None

    def find_by_gstin(self, gstin: str) -> Optional[CommissionAgent]:
        if not gstin:
            return None
        doc = self._collection.find_one({"gstin": gstin.upper()})
        return self._from_doc(doc) if doc else None

    def find_by_source_customer_id(
        self, customer_id: str
    ) -> Optional[CommissionAgent]:
        if not customer_id:
            return None
        doc = self._collection.find_one({"source_customer_id": str(customer_id)})
        return self._from_doc(doc) if doc else None

    def search(
        self, query: str, location_filter: dict | None = None
    ) -> List[CommissionAgent]:
        regex = {"$regex": query, "$options": "i"}
        mongo_query = merge_mongo_filters(
            {
                "$or": [
                    {"agent_name": regex},
                    {"phone_number": regex},
                    {"gstin": regex},
                    {"pan": regex},
                    {"city": regex},
                    {"pincode": regex},
                ]
            },
            location_filter or {},
        )
        docs = self._collection.find(mongo_query)
        return [self._from_doc(d) for d in docs]

    def list_all(
        self, location_filter: dict | None = None
    ) -> List[CommissionAgent]:
        query = merge_mongo_filters(location_filter or {})
        return [self._from_doc(d) for d in self._collection.find(query)]
