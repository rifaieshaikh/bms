from datetime import date, datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.inventory.rate_history import ProductRatePeriod


class MongoProductRateHistoryRepository:
    def __init__(self, db: Database, collection_name: str):
        self._collection = db[collection_name]

    def _to_doc(self, period: ProductRatePeriod) -> dict:
        return {
            "_id": period.id,
            "product_id": period.product_id,
            "value": period.value,
            "start_date": period.start_date.isoformat(),
            "end_date": period.end_date.isoformat() if period.end_date else None,
            "created_at": period.created_at,
        }

    def _from_doc(self, doc: dict) -> ProductRatePeriod:
        start = doc.get("start_date")
        if isinstance(start, str):
            start = date.fromisoformat(start[:10])
        end = doc.get("end_date")
        if isinstance(end, str) and end:
            end = date.fromisoformat(end[:10])
        else:
            end = None
        return ProductRatePeriod(
            id=doc["_id"],
            product_id=doc["product_id"],
            value=float(doc.get("value") or 0),
            start_date=start,
            end_date=end,
            created_at=doc.get("created_at", datetime.utcnow()),
        )

    def save(self, period: ProductRatePeriod) -> ProductRatePeriod:
        self._collection.replace_one({"_id": period.id}, self._to_doc(period), upsert=True)
        return period

    def find_by_id(self, period_id: str) -> Optional[ProductRatePeriod]:
        doc = self._collection.find_one({"_id": period_id})
        return self._from_doc(doc) if doc else None

    def list_for_product(self, product_id: str) -> List[ProductRatePeriod]:
        docs = self._collection.find({"product_id": product_id}).sort("start_date", -1)
        return [self._from_doc(d) for d in docs]

    def delete(self, period_id: str) -> None:
        self._collection.delete_one({"_id": period_id})
