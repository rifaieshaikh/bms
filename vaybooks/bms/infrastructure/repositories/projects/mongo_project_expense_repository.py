from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.projects.entities import ProjectExpense
from vaybooks.bms.domain.shared.enums import ProjectExpenseSource
from vaybooks.bms.infrastructure.db.bson_utils import from_bson_date, to_bson_value


class MongoProjectExpenseRepository:
    def __init__(self, db: Database):
        self._collection = db.project_expenses

    def _to_doc(self, expense: ProjectExpense) -> dict:
        return {
            "_id": expense.id,
            "project_id": expense.project_id,
            "expense_date": to_bson_value(expense.expense_date),
            "expense_name": expense.expense_name,
            "expense_source": expense.expense_source.value,
            "amount": float(expense.amount or 0.0),
            "activity_id": expense.activity_id,
            "boq_item_id": expense.boq_item_id,
            "vendor_id": expense.vendor_id,
            "vendor_name": expense.vendor_name,
            "notes": expense.notes,
            "purchase_voucher_id": expense.purchase_voucher_id,
            "wbs_node_id": getattr(expense, "wbs_node_id", ""),
            "site_id": getattr(expense, "site_id", ""),
            "cost_category": getattr(expense, "cost_category", ""),
            "created_at": expense.created_at,
            "updated_at": expense.updated_at,
        }

    def _from_doc(self, doc: dict) -> ProjectExpense:
        return ProjectExpense(
            id=doc["_id"],
            project_id=doc["project_id"],
            expense_date=from_bson_date(doc["expense_date"]),
            expense_name=doc.get("expense_name", ""),
            expense_source=ProjectExpenseSource(doc["expense_source"]),
            amount=float(doc.get("amount") or 0.0),
            activity_id=doc.get("activity_id"),
            boq_item_id=doc.get("boq_item_id", ""),
            vendor_id=doc.get("vendor_id", ""),
            vendor_name=doc.get("vendor_name", ""),
            notes=doc.get("notes", ""),
            purchase_voucher_id=doc.get("purchase_voucher_id", ""),
            wbs_node_id=doc.get("wbs_node_id", ""),
            site_id=doc.get("site_id", ""),
            cost_category=doc.get("cost_category", ""),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, expense: ProjectExpense) -> ProjectExpense:
        self._collection.replace_one(
            {"_id": expense.id}, self._to_doc(expense), upsert=True
        )
        return expense

    def find_by_id(self, expense_id: str) -> Optional[ProjectExpense]:
        doc = self._collection.find_one({"_id": expense_id})
        return self._from_doc(doc) if doc else None

    def list_by_project(self, project_id: str) -> List[ProjectExpense]:
        docs = self._collection.find({"project_id": project_id}).sort(
            "expense_date", -1
        )
        return [self._from_doc(d) for d in docs]

    def delete(self, expense_id: str) -> None:
        self._collection.delete_one({"_id": expense_id})
