from datetime import date, datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.orders.entities import (
    BillNumber,
    CREATED_ACTIVITY_STATUS,
    CustomizationItem,
    CustomizationOrder,
    Measurement,
    OrderActivity,
)
from vaybooks.bms.domain.orders.value_objects import BillRegistryEntry
from vaybooks.bms.domain.shared.enums import ActivityStatus, CustomizationItemStatus, OrderStatus
from vaybooks.bms.infrastructure.db.bson_utils import from_bson_date, to_bson_value


class MongoBillRegistryRepository:
    def __init__(self, db: Database):
        self._collection = db.bill_registry

    def register(self, entry: BillRegistryEntry) -> BillRegistryEntry:
        from uuid import uuid4

        doc = {
            "_id": entry.id or uuid4().hex,
            "bill_number": entry.bill_number,
            "order_id": entry.order_id,
            "bill_id": entry.bill_id,
            "created_at": entry.created_at,
        }
        self._collection.insert_one(doc)
        entry.id = doc["_id"]
        return entry

    def find_by_bill_number(self, bill_number: str) -> Optional[BillRegistryEntry]:
        doc = self._collection.find_one({"bill_number": bill_number.upper()})
        if not doc:
            return None
        return BillRegistryEntry(
            id=doc["_id"],
            bill_number=doc["bill_number"],
            order_id=doc["order_id"],
            bill_id=doc["bill_id"],
            created_at=doc.get("created_at"),
        )

    def exists(self, bill_number: str) -> bool:
        return self._collection.find_one({"bill_number": bill_number.upper()}) is not None


class MongoOrderRepository:
    def __init__(self, db: Database):
        self._collection = db.customization_orders

    def _item_to_doc(self, item: CustomizationItem) -> dict:
        return {
            "item_id": item.item_id,
            "bill_number": item.bill_number,
            "description": item.description,
            "item_status": item.item_status.value,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }

    def _item_from_doc(self, doc: dict) -> CustomizationItem:
        return CustomizationItem(
            item_id=doc.get("item_id") or doc.get("bill_id"),
            bill_number=doc["bill_number"],
            description=doc.get("description") or doc.get("item_description", ""),
            item_status=CustomizationItemStatus(
                doc.get("item_status", CustomizationItemStatus.PENDING.value)
            ),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def _items_from_order_doc(self, doc: dict) -> List[CustomizationItem]:
        if doc.get("customization_items"):
            return [self._item_from_doc(i) for i in doc["customization_items"]]
        return [self._item_from_doc(b) for b in doc.get("bill_numbers", [])]

    def _bill_to_doc(self, bill: BillNumber) -> dict:
        return {
            "bill_id": bill.bill_id,
            "bill_number": bill.bill_number,
            "item_description": bill.item_description,
            "created_at": bill.created_at,
            "updated_at": bill.updated_at,
        }

    def _measurement_to_doc(self, m: Measurement) -> dict:
        return {
            "measurement_id": m.measurement_id,
            "bill_id": m.bill_id,
            "measurement_name": m.measurement_name,
            "measurement_value": m.measurement_value,
            "unit": m.unit,
            "notes": m.notes,
        }

    def _measurement_from_doc(self, doc: dict) -> Measurement:
        return Measurement(
            measurement_id=doc["measurement_id"],
            bill_id=doc.get("bill_id"),
            measurement_name=doc["measurement_name"],
            measurement_value=doc["measurement_value"],
            unit=doc.get("unit", "inch"),
            notes=doc.get("notes", ""),
        )

    def _activity_to_doc(self, a: OrderActivity) -> dict:
        return {
            "order_activity_id": a.order_activity_id,
            "activity_id": a.activity_id,
            "activity_name": a.activity_name,
            "bill_id": a.bill_id,
            "is_required": a.is_required,
            "activity_status": a.activity_status.value,
            "current_status": a.current_status,
            "started_at": a.started_at,
            "completed_at": a.completed_at,
            "completed_by": a.completed_by,
        }

    def _activity_from_doc(self, doc: dict) -> OrderActivity:
        activity_status = ActivityStatus(doc.get("activity_status", "Pending"))
        current_status = doc.get("current_status", CREATED_ACTIVITY_STATUS)
        return OrderActivity(
            order_activity_id=doc["order_activity_id"],
            activity_id=doc["activity_id"],
            activity_name=doc["activity_name"],
            bill_id=doc.get("bill_id"),
            is_required=doc.get("is_required", True),
            activity_status=activity_status,
            current_status=current_status,
            started_at=doc.get("started_at"),
            completed_at=doc.get("completed_at"),
            completed_by=doc.get("completed_by"),
        )

    def _to_doc(self, order: CustomizationOrder) -> dict:
        return {
            "_id": order.id,
            "order_number": order.order_number,
            "customer_id": order.customer_id,
            "customer_name": order.customer_name,
            "phone_number": order.phone_number,
            "order_date": to_bson_value(order.order_date),
            "expected_delivery_date": to_bson_value(order.expected_delivery_date),
            "advance_amount": order.advance_amount,
            "order_status": order.order_status.value,
            "notes": order.notes,
            "customization_items": [
                self._item_to_doc(item) for item in order.customization_items
            ],
            "bill_numbers": [self._bill_to_doc(b) for b in order.bill_numbers],
            "measurements": [self._measurement_to_doc(m) for m in order.measurements],
            "order_activities": [
                self._activity_to_doc(a) for a in order.order_activities
            ],
            "delivery_date": to_bson_value(order.delivery_date),
            "delivery_notes": order.delivery_notes,
            "created_at": order.created_at,
            "updated_at": order.updated_at,
        }

    def _from_doc(self, doc: dict) -> CustomizationOrder:
        return CustomizationOrder(
            id=doc["_id"],
            order_number=doc["order_number"],
            customer_id=doc["customer_id"],
            customer_name=doc["customer_name"],
            phone_number=doc["phone_number"],
            order_date=from_bson_date(doc["order_date"]),
            expected_delivery_date=from_bson_date(doc["expected_delivery_date"]),
            advance_amount=doc.get("advance_amount", 0),
            order_status=OrderStatus(doc.get("order_status", "In Progress")),
            notes=doc.get("notes", ""),
            customization_items=self._items_from_order_doc(doc),
            measurements=[
                self._measurement_from_doc(m) for m in doc.get("measurements", [])
            ],
            order_activities=[
                self._activity_from_doc(a) for a in doc.get("order_activities", [])
            ],
            delivery_date=from_bson_date(doc.get("delivery_date")),
            delivery_notes=doc.get("delivery_notes"),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, order: CustomizationOrder) -> CustomizationOrder:
        self._collection.replace_one({"_id": order.id}, self._to_doc(order), upsert=True)
        return order

    def find_by_id(self, order_id: str) -> Optional[CustomizationOrder]:
        doc = self._collection.find_one({"_id": order_id})
        return self._from_doc(doc) if doc else None

    def find_by_order_number(self, order_number: str) -> Optional[CustomizationOrder]:
        doc = self._collection.find_one({"order_number": order_number})
        return self._from_doc(doc) if doc else None

    def find_by_order_activity_id(
        self, order_activity_id: str
    ) -> Optional[CustomizationOrder]:
        doc = self._collection.find_one(
            {"order_activities.order_activity_id": order_activity_id}
        )
        return self._from_doc(doc) if doc else None

    def search(self, query: str) -> List[CustomizationOrder]:
        regex = {"$regex": query, "$options": "i"}
        docs = self._collection.find(
            {
                "$or": [
                    {"customer_name": regex},
                    {"phone_number": regex},
                    {"order_number": regex},
                    {"bill_numbers.bill_number": regex},
                    {"customization_items.bill_number": regex},
                ]
            }
        )
        return [self._from_doc(d) for d in docs]

    def list_all(self) -> List[CustomizationOrder]:
        return [self._from_doc(d) for d in self._collection.find()]

    def list_by_status(self, status: str) -> List[CustomizationOrder]:
        docs = self._collection.find({"order_status": status})
        return [self._from_doc(d) for d in docs]

    def list_by_customer(self, customer_id: str) -> List[CustomizationOrder]:
        docs = self._collection.find({"customer_id": customer_id})
        return [self._from_doc(d) for d in docs]

    def count_by_customer(self, customer_id: str) -> int:
        return self._collection.count_documents({"customer_id": customer_id})

    def counts_by_customer(self) -> dict:
        """Map of customer_id -> order count, computed in one aggregation."""
        pipeline = [{"$group": {"_id": "$customer_id", "count": {"$sum": 1}}}]
        return {
            d["_id"]: d["count"]
            for d in self._collection.aggregate(pipeline)
            if d["_id"] is not None
        }

    def update_order_activity(
        self, order_id: str, order_activity_id: str, updates: dict
    ) -> CustomizationOrder:
        set_fields = {}
        for key, value in updates.items():
            if key == "activity_status" and hasattr(value, "value"):
                value = value.value
            set_fields[f"order_activities.$.{key}"] = value
        set_fields["updated_at"] = datetime.utcnow()
        self._collection.update_one(
            {"_id": order_id, "order_activities.order_activity_id": order_activity_id},
            {"$set": set_fields},
        )
        return self.find_by_id(order_id)
