from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.projects.entities import ProjectProforma, ProjectQuotationLine
from vaybooks.bms.infrastructure.db.bson_utils import from_bson_date, to_bson_value


class MongoProjectProformaRepository:
    def __init__(self, db: Database):
        self._collection = db.project_proformas

    def _line_to_doc(self, line: ProjectQuotationLine) -> dict:
        return {
            "id": line.id,
            "description": line.description,
            "quantity": float(line.quantity or 0.0),
            "rate": float(line.rate or 0.0),
            "discount_pct": float(line.discount_pct or 0.0),
            "hsn_sac": line.hsn_sac,
            "activity_id": line.activity_id,
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
        )

    def _to_doc(self, proforma: ProjectProforma) -> dict:
        return {
            "_id": proforma.id,
            "project_id": proforma.project_id,
            "proforma_number": proforma.proforma_number,
            "proforma_date": to_bson_value(proforma.proforma_date),
            "amount": float(proforma.amount or 0.0),
            "description": proforma.description,
            "status": proforma.status,
            "lines": [self._line_to_doc(line) for line in proforma.lines],
            "created_at": proforma.created_at,
        }

    def _from_doc(self, doc: dict) -> ProjectProforma:
        return ProjectProforma(
            id=doc["_id"],
            project_id=doc["project_id"],
            proforma_number=doc.get("proforma_number", ""),
            proforma_date=from_bson_date(doc["proforma_date"]),
            amount=float(doc.get("amount") or 0.0),
            description=doc.get("description", ""),
            status=doc.get("status", "Draft"),
            lines=[self._line_from_doc(line) for line in doc.get("lines", [])],
            created_at=doc.get("created_at", datetime.utcnow()),
        )

    def save(self, proforma: ProjectProforma) -> ProjectProforma:
        self._collection.replace_one(
            {"_id": proforma.id}, self._to_doc(proforma), upsert=True
        )
        return proforma

    def find_by_id(self, proforma_id: str) -> Optional[ProjectProforma]:
        doc = self._collection.find_one({"_id": proforma_id})
        return self._from_doc(doc) if doc else None

    def list_by_project(self, project_id: str) -> List[ProjectProforma]:
        docs = self._collection.find({"project_id": project_id}).sort(
            "proforma_date", -1
        )
        return [self._from_doc(d) for d in docs]
