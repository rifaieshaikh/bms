from datetime import date, datetime
from typing import List

from pymongo.database import Database

from vaybooks.bms.domain.shared.enums import OrderStatus
from vaybooks.bms.infrastructure.db.bson_utils import to_bson_value


# Only the fields the dashboard / list cards actually read. Fetching just these
# keeps documents small over the wire instead of hydrating full order docs
# (items, measurements, activities, ...).
_CARD_PROJECTION = {
    "order_number": 1,
    "customer_name": 1,
    "phone_number": 1,
    "order_status": 1,
    "expected_delivery_date": 1,
    "created_at": 1,
    "updated_at": 1,
}

_INACTIVE_STATUSES = [
    OrderStatus.DELIVERED.value,
    OrderStatus.COMPLETED.value,
    OrderStatus.CANCELLED.value,
]


class MongoReportRepository:
    def __init__(self, db: Database):
        self._db = db

    @staticmethod
    def _normalize_order(doc: dict) -> dict:
        doc["id"] = doc.get("_id")
        return doc

    def count_orders_by_status(self, status: str) -> int:
        return self._db.customization_orders.count_documents({"order_status": status})

    def count_orders_by_statuses(self, statuses: List[str]) -> int:
        return self._db.customization_orders.count_documents(
            {"order_status": {"$in": statuses}}
        )

    def get_orders_by_status(self, status: str, limit: int = 0) -> List[dict]:
        cursor = self._db.customization_orders.find(
            {"order_status": status}, _CARD_PROJECTION
        ).sort("updated_at", -1)
        if limit:
            cursor = cursor.limit(limit)
        return [self._normalize_order(d) for d in cursor]

    def get_orders_by_statuses(self, statuses: List[str], limit: int = 0) -> List[dict]:
        cursor = self._db.customization_orders.find(
            {"order_status": {"$in": statuses}}, _CARD_PROJECTION
        ).sort("updated_at", -1)
        if limit:
            cursor = cursor.limit(limit)
        return [self._normalize_order(d) for d in cursor]

    def get_overdue_orders(self, today: date, limit: int = 200) -> List[dict]:
        cursor = self._db.customization_orders.find(
            {
                "expected_delivery_date": {"$lt": to_bson_value(today)},
                "order_status": {"$nin": _INACTIVE_STATUSES},
            },
            _CARD_PROJECTION,
        ).sort("expected_delivery_date", 1)
        if limit:
            cursor = cursor.limit(limit)
        return [self._normalize_order(d) for d in cursor]

    def get_etd_today(self, today: date, limit: int = 200) -> List[dict]:
        cursor = self._db.customization_orders.find(
            {
                "expected_delivery_date": to_bson_value(today),
                "order_status": {"$nin": _INACTIVE_STATUSES},
            },
            _CARD_PROJECTION,
        )
        if limit:
            cursor = cursor.limit(limit)
        return [self._normalize_order(d) for d in cursor]

    def get_delivered_this_month(self, start: date, end: date) -> List[dict]:
        deliveries = list(
            self._db.deliveries.find(
                {
                    "delivery_date": {
                        "$gte": to_bson_value(start),
                        "$lte": to_bson_value(end),
                    }
                }
            )
        )
        if deliveries:
            order_ids = list({d["order_id"] for d in deliveries})
            return [
                self._normalize_order(d)
                for d in self._db.customization_orders.find({"_id": {"$in": order_ids}})
            ]
        return [
            self._normalize_order(d)
            for d in self._db.customization_orders.find(
                {
                    "order_status": {
                        "$in": [
                            OrderStatus.DELIVERED.value,
                            OrderStatus.COMPLETED.value,
                        ]
                    },
                    "delivery_date": {
                        "$gte": to_bson_value(start),
                        "$lte": to_bson_value(end),
                    },
                }
            )
        ]

    def count_delivered_this_month(self, start: date, end: date) -> int:
        order_ids = self._db.deliveries.distinct(
            "order_id",
            {"delivery_date": {"$gte": to_bson_value(start), "$lte": to_bson_value(end)}},
        )
        if order_ids:
            return len(order_ids)
        return self._db.customization_orders.count_documents(
            {
                "order_status": {
                    "$in": [OrderStatus.DELIVERED.value, OrderStatus.COMPLETED.value]
                },
                "delivery_date": {
                    "$gte": to_bson_value(start),
                    "$lte": to_bson_value(end),
                },
            }
        )

    def get_bills_pending_invoice_count(self) -> int:
        # Count bills (across non-cancelled orders) whose bill_id is not present
        # in any of that order's invoices. Done in a single aggregation instead
        # of an N+1 query-per-order loop.
        pipeline = [
            {"$match": {"order_status": {"$ne": OrderStatus.CANCELLED.value}}},
            {"$project": {"bill_id": "$bill_numbers.bill_id"}},
            {"$unwind": "$bill_id"},
            {"$match": {"bill_id": {"$ne": None}}},
            {
                "$lookup": {
                    "from": "invoices",
                    "localField": "_id",
                    "foreignField": "order_id",
                    "as": "invoices",
                }
            },
            {
                "$project": {
                    "bill_id": 1,
                    "invoiced": {
                        "$reduce": {
                            "input": "$invoices",
                            "initialValue": [],
                            "in": {
                                "$concatArrays": [
                                    "$$value",
                                    {"$ifNull": ["$$this.bill_ids", []]},
                                ]
                            },
                        }
                    },
                }
            },
            {"$match": {"$expr": {"$not": [{"$in": ["$bill_id", "$invoiced"]}]}}},
            {"$count": "total"},
        ]
        result = list(self._db.customization_orders.aggregate(pipeline))
        return result[0]["total"] if result else 0

    def get_pending_activities_count(self) -> int:
        pipeline = [
            {"$unwind": "$order_activities"},
            {
                "$match": {
                    "order_activities.is_required": True,
                    "order_activities.activity_status": {
                        "$in": ["Pending", "In Progress"]
                    },
                }
            },
            {"$count": "total"},
        ]
        result = list(self._db.customization_orders.aggregate(pipeline))
        return result[0]["total"] if result else 0

    def get_monthly_invoice_total(self, start: date, end: date) -> float:
        pipeline = [
            {
                "$match": {
                    "invoice_date": {
                        "$gte": to_bson_value(start),
                        "$lte": to_bson_value(end),
                    }
                }
            },
            {"$group": {"_id": None, "total": {"$sum": "$invoice_amount"}}},
        ]
        result = list(self._db.invoices.aggregate(pipeline))
        return result[0]["total"] if result else 0.0

    def get_monthly_advance_total(self, start: date, end: date) -> float:
        pipeline = [
            {
                "$match": {
                    "voucher_type": "Receipt",
                    "voucher_date": {
                        "$gte": to_bson_value(start),
                        "$lte": to_bson_value(end),
                    },
                }
            },
            {"$unwind": "$lines"},
            {"$match": {"lines.debit_amount": {"$gt": 0}}},
            {"$group": {"_id": None, "total": {"$sum": "$lines.debit_amount"}}},
        ]
        result = list(self._db.vouchers.aggregate(pipeline))
        return result[0]["total"] if result else 0.0

    def get_all_expenses(self) -> List[dict]:
        return list(self._db.expenses.find())

    def get_all_time_entries(self) -> List[dict]:
        return list(self._db.time_entries.find())

    def get_all_invoices(self) -> List[dict]:
        return list(self._db.invoices.find())

    def get_all_customers(self) -> List[dict]:
        return list(self._db.customers.find())

    def get_all_orders(self) -> List[dict]:
        return list(self._db.customization_orders.find())

    def get_all_vouchers(self) -> List[dict]:
        return list(self._db.vouchers.find())

    def get_customer_orders(self, customer_id: str) -> List[dict]:
        return list(self._db.customization_orders.find({"customer_id": customer_id}))
