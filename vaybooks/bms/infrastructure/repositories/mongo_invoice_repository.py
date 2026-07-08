from datetime import date, datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.invoices.entities import Invoice
from vaybooks.bms.infrastructure.db.bson_utils import from_bson_date, to_bson_value


class MongoInvoiceRepository:
    def __init__(self, db: Database):
        self._collection = db.invoices

    def _to_doc(self, invoice: Invoice) -> dict:
        return {
            "_id": invoice.id,
            "order_id": invoice.order_id,
            "order_number": invoice.order_number,
            "invoice_number": invoice.invoice_number,
            "invoice_date": to_bson_value(invoice.invoice_date),
            "invoice_amount": invoice.invoice_amount,
            "total_amount": invoice.total_amount,
            "bill_ids": invoice.bill_ids,
            "item_amounts": invoice.item_amounts,
            "item_discounts": invoice.item_discounts,
            "discount_amount": invoice.discount_amount,
            "total_expense_purchase_price": invoice.total_expense_purchase_price,
            "total_expense_selling_price": invoice.total_expense_selling_price,
            "total_in_house_hours": invoice.total_in_house_hours,
            "margin_amount": invoice.margin_amount,
            "margin_per_hour": invoice.margin_per_hour,
            "created_at": invoice.created_at,
            "updated_at": invoice.updated_at,
        }

    def _from_doc(self, doc: dict) -> Invoice:
        return Invoice(
            id=doc["_id"],
            order_id=doc["order_id"],
            order_number=doc["order_number"],
            invoice_number=doc["invoice_number"],
            invoice_date=from_bson_date(doc["invoice_date"]),
            invoice_amount=doc["invoice_amount"],
            total_amount=doc.get("total_amount", doc.get("invoice_amount", 0)),
            bill_ids=doc.get("bill_ids", []),
            item_amounts=doc.get("item_amounts", {}) or {},
            item_discounts=doc.get("item_discounts", {}) or {},
            discount_amount=doc.get("discount_amount", 0),
            total_expense_purchase_price=doc.get("total_expense_purchase_price", 0),
            total_expense_selling_price=doc.get("total_expense_selling_price", 0),
            total_in_house_hours=doc.get("total_in_house_hours", 0),
            margin_amount=doc.get("margin_amount", 0),
            margin_per_hour=doc.get("margin_per_hour"),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, invoice: Invoice) -> Invoice:
        self._collection.replace_one(
            {"_id": invoice.id}, self._to_doc(invoice), upsert=True
        )
        return invoice

    def find_by_id(self, invoice_id: str) -> Optional[Invoice]:
        doc = self._collection.find_one({"_id": invoice_id})
        return self._from_doc(doc) if doc else None

    def list_by_order(self, order_id: str) -> List[Invoice]:
        return [self._from_doc(d) for d in self._collection.find({"order_id": order_id})]

    def find_by_bill(self, bill_id: str) -> List[Invoice]:
        return [
            self._from_doc(d)
            for d in self._collection.find({"bill_ids": bill_id})
        ]

    def list_all(self) -> List[Invoice]:
        return [self._from_doc(d) for d in self._collection.find()]

    # Backward compatibility for code still calling find_by_order singular
    def find_by_order(self, order_id: str) -> Optional[Invoice]:
        invoices = self.list_by_order(order_id)
        return invoices[0] if invoices else None
