from datetime import date, datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.boutique.expenses.entities import Expense
from vaybooks.bms.domain.shared.enums import ExpenseSource
from vaybooks.bms.infrastructure.db.bson_utils import from_bson_date, to_bson_value


class MongoExpenseRepository:
    def __init__(self, db: Database):
        self._collection = db.expenses

    def _to_doc(self, expense: Expense) -> dict:
        return {
            "_id": expense.id,
            "order_id": expense.order_id,
            "order_number": expense.order_number,
            "bill_id": expense.bill_id,
            "bill_number": expense.bill_number,
            "activity_id": expense.activity_id,
            "activity_name": expense.activity_name,
            "expense_date": to_bson_value(expense.expense_date),
            "expense_name": expense.expense_name,
            "expense_source": expense.expense_source.value,
            "purchase_price": expense.purchase_price,
            "selling_price": expense.selling_price,
            "quantity": expense.quantity,
            "total_purchase_price": expense.total_purchase_price,
            "total_selling_price": expense.total_selling_price,
            "linked_time_minutes": expense.linked_time_minutes,
            "linked_time_hours": expense.linked_time_hours,
            "vendor_or_worker_name": expense.vendor_or_worker_name,
            "account_id": expense.account_id,
            "notes": expense.notes,
            "created_at": expense.created_at,
            "updated_at": expense.updated_at,
        }

    def _from_doc(self, doc: dict) -> Expense:
        expense = Expense(
            id=doc["_id"],
            order_id=doc["order_id"],
            order_number=doc["order_number"],
            expense_date=from_bson_date(doc["expense_date"]),
            expense_name=doc["expense_name"],
            expense_source=ExpenseSource(doc["expense_source"]),
            purchase_price=doc["purchase_price"],
            selling_price=doc["selling_price"],
            quantity=doc.get("quantity", 1),
            bill_id=doc.get("bill_id"),
            bill_number=doc.get("bill_number"),
            activity_id=doc.get("activity_id"),
            activity_name=doc.get("activity_name"),
            total_purchase_price=doc.get("total_purchase_price", 0),
            total_selling_price=doc.get("total_selling_price", 0),
            linked_time_minutes=doc.get("linked_time_minutes", 0),
            linked_time_hours=doc.get("linked_time_hours", 0),
            vendor_or_worker_name=doc.get("vendor_or_worker_name", ""),
            account_id=doc.get("account_id"),
            notes=doc.get("notes", ""),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )
        return expense

    def save(self, expense: Expense) -> Expense:
        self._collection.replace_one(
            {"_id": expense.id}, self._to_doc(expense), upsert=True
        )
        return expense

    def find_by_id(self, expense_id: str) -> Optional[Expense]:
        doc = self._collection.find_one({"_id": expense_id})
        return self._from_doc(doc) if doc else None

    def find_by_order(self, order_id: str) -> List[Expense]:
        return [self._from_doc(d) for d in self._collection.find({"order_id": order_id})]

    def find_by_bill(self, bill_id: str) -> List[Expense]:
        return [self._from_doc(d) for d in self._collection.find({"bill_id": bill_id})]

    def list_all(self) -> List[Expense]:
        return [self._from_doc(d) for d in self._collection.find()]

    def delete(self, expense_id: str) -> None:
        self._collection.delete_one({"_id": expense_id})
