from __future__ import annotations

import re
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.crm.entities import CrmEnquiry
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.infrastructure.repositories.crm._serialize import (
    enquiry_from_doc,
    enquiry_to_doc,
    not_deleted_filter,
)


class MongoCrmEnquiryRepository:
    def __init__(self, db: Database):
        self._collection = db.crm_enquiries

    def save(self, enquiry: CrmEnquiry) -> CrmEnquiry:
        enquiry.updated_at = utc_now()
        self._collection.replace_one(
            {"_id": enquiry.id}, enquiry_to_doc(enquiry), upsert=True
        )
        return enquiry

    def find_by_id(self, enquiry_id: str) -> Optional[CrmEnquiry]:
        doc = self._collection.find_one({"_id": enquiry_id})
        return enquiry_from_doc(doc) if doc else None

    def list(
        self,
        *,
        status: Optional[str] = None,
        lead_id: Optional[str] = None,
        customer_id: Optional[str] = None,
        assigned_user_id: Optional[str] = None,
        branch: Optional[str] = None,
        include_deleted: bool = False,
        search: str = "",
        limit: int = 500,
    ) -> List[CrmEnquiry]:
        query: dict = dict(not_deleted_filter(include_deleted))
        if status:
            query["status"] = status
        if lead_id:
            query["lead_id"] = lead_id
        if customer_id:
            query["customer_id"] = customer_id
        if assigned_user_id is not None:
            query["assigned_user_id"] = assigned_user_id
        if branch:
            query["branch"] = branch
        if search and search.strip():
            regex = {"$regex": re.escape(search.strip()), "$options": "i"}
            query["$or"] = [
                {"enquiry_number": regex},
                {"party_name": regex},
                {"product_interest": regex},
                {"description": regex},
            ]
        docs = self._collection.find(query).sort("created_at", -1).limit(limit)
        return [enquiry_from_doc(d) for d in docs]
