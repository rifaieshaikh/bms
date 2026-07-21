from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.projects.petty_cash import (
    ProjectPettyCashAdvance,
    ProjectPettyCashExpenseLine,
)
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import ProjectPettyCashStatus
from vaybooks.bms.infrastructure.db.bson_utils import from_bson_date, to_bson_value


class MongoProjectPettyCashRepository:
    def __init__(self, db: Database):
        self._collection = db.project_petty_cash_advances

    def _expense_to_doc(self, line: ProjectPettyCashExpenseLine) -> dict:
        return {
            "id": line.id,
            "description": line.description,
            "amount": float(line.amount or 0.0),
            "expense_date": to_bson_value(line.expense_date),
            "activity_id": line.activity_id,
            "receipt_ref": line.receipt_ref,
        }

    def _expense_from_doc(self, doc: dict) -> ProjectPettyCashExpenseLine:
        return ProjectPettyCashExpenseLine(
            id=doc.get("id", ""),
            description=doc.get("description", ""),
            amount=float(doc.get("amount") or 0.0),
            expense_date=from_bson_date(doc["expense_date"]),
            activity_id=doc.get("activity_id", ""),
            receipt_ref=doc.get("receipt_ref", ""),
        )

    def _to_doc(self, advance: ProjectPettyCashAdvance) -> dict:
        return {
            "_id": advance.id,
            "project_id": advance.project_id,
            "advance_number": advance.advance_number,
            "custodian": advance.custodian,
            "advance_date": to_bson_value(advance.advance_date),
            "amount": float(advance.amount or 0.0),
            "expenses": [self._expense_to_doc(line) for line in advance.expenses],
            "returned_amount": float(advance.returned_amount or 0.0),
            "reimbursement_amount": float(advance.reimbursement_amount or 0.0),
            "status": advance.status.value,
            "notes": advance.notes,
            "created_at": advance.created_at,
            "updated_at": advance.updated_at,
        }

    def _from_doc(self, doc: dict) -> ProjectPettyCashAdvance:
        return ProjectPettyCashAdvance(
            id=doc["_id"],
            project_id=doc["project_id"],
            advance_number=doc.get("advance_number", ""),
            custodian=doc.get("custodian", ""),
            advance_date=from_bson_date(doc["advance_date"]),
            amount=float(doc.get("amount") or 0.0),
            expenses=[self._expense_from_doc(line) for line in doc.get("expenses", [])],
            returned_amount=float(doc.get("returned_amount") or 0.0),
            reimbursement_amount=float(doc.get("reimbursement_amount") or 0.0),
            status=ProjectPettyCashStatus(
                doc.get("status", ProjectPettyCashStatus.OPEN.value)
            ),
            notes=doc.get("notes", ""),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, advance: ProjectPettyCashAdvance) -> ProjectPettyCashAdvance:
        advance.updated_at = utc_now()
        self._collection.replace_one(
            {"_id": advance.id}, self._to_doc(advance), upsert=True
        )
        return advance

    def find_by_id(self, advance_id: str) -> Optional[ProjectPettyCashAdvance]:
        doc = self._collection.find_one({"_id": advance_id})
        return self._from_doc(doc) if doc else None

    def list_by_project(self, project_id: str) -> List[ProjectPettyCashAdvance]:
        docs = self._collection.find({"project_id": project_id}).sort(
            "advance_date", -1
        )
        return [self._from_doc(d) for d in docs]
