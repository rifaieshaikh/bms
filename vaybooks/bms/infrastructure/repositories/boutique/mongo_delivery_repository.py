from datetime import date, datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.boutique.deliveries.entities import Delivery
from vaybooks.bms.domain.boutique.orders.order_refs import order_ref_search_variants
from vaybooks.bms.infrastructure.db.bson_utils import from_bson_date, to_bson_value


class MongoDeliveryRepository:
    def __init__(self, db: Database):
        self._collection = db.deliveries

    def _to_doc(self, delivery: Delivery) -> dict:
        return {
            "_id": delivery.id,
            "order_id": delivery.order_id,
            "order_number": delivery.order_number,
            "bill_ids": delivery.bill_ids,
            "delivery_date": to_bson_value(delivery.delivery_date),
            "delivery_notes": delivery.delivery_notes,
            "created_at": delivery.created_at,
            "updated_at": delivery.updated_at,
        }

    def _from_doc(self, doc: dict) -> Delivery:
        return Delivery(
            id=doc["_id"],
            order_id=doc["order_id"],
            order_number=doc["order_number"],
            bill_ids=doc.get("bill_ids", []),
            delivery_date=from_bson_date(doc["delivery_date"]),
            delivery_notes=doc.get("delivery_notes", ""),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, delivery: Delivery) -> Delivery:
        self._collection.replace_one(
            {"_id": delivery.id}, self._to_doc(delivery), upsert=True
        )
        return delivery

    def find_by_id(self, delivery_id: str) -> Optional[Delivery]:
        doc = self._collection.find_one({"_id": delivery_id})
        return self._from_doc(doc) if doc else None

    def list_by_order(self, order_id: str) -> List[Delivery]:
        for candidate in order_ref_search_variants(order_id) or [order_id]:
            docs = list(self._collection.find({"order_id": candidate}))
            if docs:
                return [self._from_doc(d) for d in docs]
        return []

    def list_all(self) -> List[Delivery]:
        return [self._from_doc(d) for d in self._collection.find()]
