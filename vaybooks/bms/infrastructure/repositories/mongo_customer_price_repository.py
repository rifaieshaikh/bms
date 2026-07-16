"""Mongo repository for customer sales price history."""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.sales.customer_prices import CustomerPriceEntry


class MongoCustomerPriceRepository:
    def __init__(self, db: Database):
        self._collection = db.customer_prices

    def _to_doc(self, row: CustomerPriceEntry) -> dict:
        effective = row.effective_date
        if isinstance(effective, datetime):
            effective = effective.date()
        return {
            "_id": row.id,
            "customer_id": row.customer_id,
            "customer_name": row.customer_name,
            "product_id": row.product_id,
            "sku": row.sku,
            "product_name": row.product_name,
            "rate": float(row.rate or 0),
            "voucher_id": row.voucher_id or "",
            "store_invoice_number": row.store_invoice_number or "",
            "effective_date": (
                effective.isoformat() if isinstance(effective, date) else effective
            ),
            "created_at": row.created_at,
        }

    def _from_doc(self, doc: dict) -> CustomerPriceEntry:
        effective = doc.get("effective_date")
        if isinstance(effective, str):
            effective = date.fromisoformat(effective[:10])
        elif isinstance(effective, datetime):
            effective = effective.date()
        return CustomerPriceEntry(
            id=doc["_id"],
            customer_id=str(doc.get("customer_id") or ""),
            customer_name=str(doc.get("customer_name") or ""),
            product_id=str(doc.get("product_id") or ""),
            sku=str(doc.get("sku") or ""),
            product_name=str(doc.get("product_name") or ""),
            rate=float(doc.get("rate") or 0),
            voucher_id=str(doc.get("voucher_id") or ""),
            store_invoice_number=str(doc.get("store_invoice_number") or ""),
            effective_date=effective or date.today(),
            created_at=doc.get("created_at", datetime.utcnow()),
        )

    def save(self, row: CustomerPriceEntry) -> CustomerPriceEntry:
        self._collection.replace_one(
            {"_id": row.id}, self._to_doc(row), upsert=True
        )
        return row

    def latest(
        self, customer_id: str, product_id: str
    ) -> Optional[CustomerPriceEntry]:
        if not customer_id or not product_id:
            return None
        doc = self._collection.find_one(
            {"customer_id": customer_id, "product_id": product_id},
            sort=[("effective_date", -1), ("created_at", -1)],
        )
        return self._from_doc(doc) if doc else None

    def list_for_customer(
        self, customer_id: str, *, limit: int = 200
    ) -> List[CustomerPriceEntry]:
        docs = (
            self._collection.find({"customer_id": customer_id})
            .sort([("effective_date", -1), ("created_at", -1)])
            .limit(limit)
        )
        return [self._from_doc(doc) for doc in docs]

    def list_for_product(
        self, product_id: str, *, limit: int = 200
    ) -> List[CustomerPriceEntry]:
        docs = (
            self._collection.find({"product_id": product_id})
            .sort([("effective_date", -1), ("created_at", -1)])
            .limit(limit)
        )
        return [self._from_doc(doc) for doc in docs]

    def list_for_pair(
        self, customer_id: str, product_id: str, *, limit: int = 50
    ) -> List[CustomerPriceEntry]:
        docs = (
            self._collection.find(
                {"customer_id": customer_id, "product_id": product_id}
            )
            .sort([("effective_date", -1), ("created_at", -1)])
            .limit(limit)
        )
        return [self._from_doc(doc) for doc in docs]

    def list_all(self, *, limit: int = 500) -> List[CustomerPriceEntry]:
        docs = (
            self._collection.find({})
            .sort([("effective_date", -1), ("created_at", -1)])
            .limit(limit)
        )
        return [self._from_doc(doc) for doc in docs]

    def delete_by_voucher(self, voucher_id: str) -> int:
        if not voucher_id:
            return 0
        result = self._collection.delete_many({"voucher_id": voucher_id})
        return int(result.deleted_count or 0)
