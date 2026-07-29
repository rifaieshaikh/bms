from __future__ import annotations

import re
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.crm.entities import CrmLead
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.infrastructure.repositories.crm._serialize import (
    lead_from_doc,
    lead_to_doc,
    not_deleted_filter,
)


class MongoCrmLeadRepository:
    def __init__(self, db: Database):
        self._collection = db.crm_leads

    def save(self, lead: CrmLead) -> CrmLead:
        lead.updated_at = utc_now()
        self._collection.replace_one({"_id": lead.id}, lead_to_doc(lead), upsert=True)
        return lead

    def find_by_id(self, lead_id: str) -> Optional[CrmLead]:
        doc = self._collection.find_one({"_id": lead_id})
        return lead_from_doc(doc) if doc else None

    def find_by_phone_normalized(self, phone: str) -> Optional[CrmLead]:
        phone = (phone or "").strip()
        if not phone:
            return None
        doc = self._collection.find_one(
            {"phone_normalized": phone, "is_deleted": {"$ne": True}}
        )
        return lead_from_doc(doc) if doc else None

    def find_by_email_normalized(self, email: str) -> Optional[CrmLead]:
        email = (email or "").strip().lower()
        if not email:
            return None
        doc = self._collection.find_one(
            {"email_normalized": email, "is_deleted": {"$ne": True}}
        )
        return lead_from_doc(doc) if doc else None

    def find_by_gstin_normalized(self, gstin: str) -> Optional[CrmLead]:
        gstin = (gstin or "").strip().upper()
        if not gstin:
            return None
        doc = self._collection.find_one(
            {"gstin_normalized": gstin, "is_deleted": {"$ne": True}}
        )
        return lead_from_doc(doc) if doc else None

    def find_by_import_fingerprint(
        self, batch_id: str, fingerprint: str
    ) -> Optional[CrmLead]:
        if not fingerprint:
            return None
        query = {"import_row_fingerprint": fingerprint, "is_deleted": {"$ne": True}}
        if batch_id:
            query["import_batch_id"] = batch_id
        doc = self._collection.find_one(query)
        return lead_from_doc(doc) if doc else None

    def list(
        self,
        *,
        status: Optional[str] = None,
        assigned_user_id: Optional[str] = None,
        source: Optional[str] = None,
        branch: Optional[str] = None,
        include_deleted: bool = False,
        search: str = "",
        limit: int = 500,
        location_filter: dict | None = None,
    ) -> List[CrmLead]:
        from vaybooks.bms.domain.identity.location_access import merge_mongo_filters

        query: dict = dict(not_deleted_filter(include_deleted))
        if status:
            query["status"] = status
        if assigned_user_id is not None:
            if assigned_user_id == "":
                query["$or"] = [
                    {"assigned_user_id": ""},
                    {"assigned_user_id": {"$exists": False}},
                ]
            else:
                query["assigned_user_id"] = assigned_user_id
        if source:
            query["source"] = source
        if branch:
            query["branch"] = branch
        if search and search.strip():
            regex = {"$regex": re.escape(search.strip()), "$options": "i"}
            search_clause = {
                "$or": [
                    {"name": regex},
                    {"phone": regex},
                    {"email": regex},
                    {"gstin": regex},
                    {"lead_number": regex},
                    {"contact_person": regex},
                ]
            }
            if "$or" in query:
                query = {"$and": [query, search_clause]}
            else:
                query.update(search_clause)
        query = merge_mongo_filters(query, location_filter or {})
        docs = self._collection.find(query).sort("created_at", -1).limit(limit)
        return [lead_from_doc(d) for d in docs]

    def list_duplicates_candidates(self) -> List[CrmLead]:
        docs = self._collection.find(not_deleted_filter()).sort("created_at", -1).limit(
            2000
        )
        return [lead_from_doc(d) for d in docs]
