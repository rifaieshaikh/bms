from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.projects.entities import ProjectQuotation, ProjectQuotationLine
from vaybooks.bms.domain.shared.enums import ProjectQuotationStatus
from vaybooks.bms.infrastructure.db.bson_utils import from_bson_date, to_bson_value


class MongoProjectQuotationRepository:
    def __init__(self, db: Database):
        self._collection = db.project_quotations

    def _line_to_doc(self, line: ProjectQuotationLine) -> dict:
        return {
            "id": line.id,
            "description": line.description,
            "quantity": float(line.quantity or 0.0),
            "rate": float(line.rate or 0.0),
            "discount_pct": float(line.discount_pct or 0.0),
            "hsn_sac": line.hsn_sac,
            "activity_id": line.activity_id,
            "boq_item_id": line.boq_item_id,
        }

    def _line_from_doc(self, doc: dict) -> ProjectQuotationLine:
        return ProjectQuotationLine(
            id=doc.get("id", ""),
            description=doc.get("description", ""),
            quantity=float(doc.get("quantity") or 0.0),
            rate=float(doc.get("rate") or 0.0),
            discount_pct=float(doc.get("discount_pct") or 0.0),
            hsn_sac=doc.get("hsn_sac", ""),
            activity_id=doc.get("activity_id"),
            boq_item_id=doc.get("boq_item_id"),
        )

    def _to_doc(self, quotation: ProjectQuotation) -> dict:
        return {
            "_id": quotation.id,
            "project_id": quotation.project_id,
            "quotation_number": quotation.quotation_number,
            "quotation_date": to_bson_value(quotation.quotation_date),
            "status": quotation.status.value,
            "customer_id": quotation.customer_id,
            "customer_name": quotation.customer_name,
            "lines": [self._line_to_doc(line) for line in quotation.lines],
            "notes": quotation.notes,
            "revision_no": quotation.revision_no,
            "root_id": quotation.root_id,
            "supersedes_id": quotation.supersedes_id,
            "approved_by": quotation.approved_by,
            "approved_at": quotation.approved_at,
            "sent_at": quotation.sent_at,
            "valid_until": to_bson_value(quotation.valid_until),
            "confirmation_date": to_bson_value(quotation.confirmation_date),
            "confirmation_note": quotation.confirmation_note,
            "confirmation_evidence": getattr(quotation, "confirmation_evidence", ""),
            "submitted_by": getattr(quotation, "submitted_by", ""),
            "created_by": getattr(quotation, "created_by", ""),
            "created_at": quotation.created_at,
            "updated_at": quotation.updated_at,
        }

    def _from_doc(self, doc: dict) -> ProjectQuotation:
        return ProjectQuotation(
            id=doc["_id"],
            project_id=doc["project_id"],
            quotation_number=doc.get("quotation_number", ""),
            quotation_date=from_bson_date(doc["quotation_date"]),
            status=ProjectQuotationStatus(
                doc.get("status", ProjectQuotationStatus.DRAFT.value)
            ),
            customer_id=doc.get("customer_id", ""),
            customer_name=doc.get("customer_name", ""),
            lines=[self._line_from_doc(line) for line in doc.get("lines", [])],
            notes=doc.get("notes", ""),
            revision_no=int(doc.get("revision_no") or 1),
            root_id=doc.get("root_id", ""),
            supersedes_id=doc.get("supersedes_id", ""),
            approved_by=doc.get("approved_by", ""),
            approved_at=doc.get("approved_at"),
            sent_at=doc.get("sent_at"),
            valid_until=from_bson_date(doc.get("valid_until")),
            confirmation_date=from_bson_date(doc.get("confirmation_date")),
            confirmation_note=doc.get("confirmation_note", ""),
            confirmation_evidence=doc.get("confirmation_evidence", ""),
            submitted_by=doc.get("submitted_by", ""),
            created_by=doc.get("created_by", ""),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, quotation: ProjectQuotation) -> ProjectQuotation:
        self._collection.replace_one(
            {"_id": quotation.id}, self._to_doc(quotation), upsert=True
        )
        return quotation

    def find_by_id(self, quotation_id: str) -> Optional[ProjectQuotation]:
        doc = self._collection.find_one({"_id": quotation_id})
        return self._from_doc(doc) if doc else None

    def list_by_project(self, project_id: str) -> List[ProjectQuotation]:
        docs = self._collection.find({"project_id": project_id}).sort(
            "quotation_date", -1
        )
        return [self._from_doc(d) for d in docs]

    def list_all(self) -> List[ProjectQuotation]:
        return [self._from_doc(d) for d in self._collection.find()]
