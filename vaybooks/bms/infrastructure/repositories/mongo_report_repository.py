from datetime import date, datetime, time
from typing import List

from pymongo.database import Database

from vaybooks.bms.domain.shared.enums import CustomizationItemStatus, OrderStatus
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

    def count_orders_created(self, start: date, end: date) -> int:
        return self._db.customization_orders.count_documents(
            {"order_date": {"$gte": to_bson_value(start), "$lte": to_bson_value(end)}}
        )

    def count_customers_created(self, start: date, end: date) -> int:
        start_dt = datetime.combine(start, time.min)
        end_dt = datetime.combine(end, time.max)
        return self._db.customers.count_documents(
            {"created_at": {"$gte": start_dt, "$lte": end_dt}}
        )

    def count_distinct_customers_with_orders(self, start: date, end: date) -> int:
        pipeline = [
            {
                "$match": {
                    "order_date": {
                        "$gte": to_bson_value(start),
                        "$lte": to_bson_value(end),
                    }
                }
            },
            {"$group": {"_id": "$customer_id"}},
            {"$count": "total"},
        ]
        result = list(self._db.customization_orders.aggregate(pipeline))
        return result[0]["total"] if result else 0

    def count_repeat_customers_with_orders(self, start: date, end: date) -> int:
        pipeline = [
            {
                "$match": {
                    "order_date": {
                        "$gte": to_bson_value(start),
                        "$lte": to_bson_value(end),
                    }
                }
            },
            {"$group": {"_id": "$customer_id", "count": {"$sum": 1}}},
            {"$match": {"count": {"$gte": 2}}},
            {"$count": "total"},
        ]
        result = list(self._db.customization_orders.aggregate(pipeline))
        return result[0]["total"] if result else 0

    def count_distinct_customers_invoiced(self, start: date, end: date) -> int:
        pipeline = [
            {
                "$match": {
                    "invoice_date": {
                        "$gte": to_bson_value(start),
                        "$lte": to_bson_value(end),
                    }
                }
            },
            {
                "$lookup": {
                    "from": "customization_orders",
                    "localField": "order_id",
                    "foreignField": "_id",
                    "as": "order",
                }
            },
            {"$unwind": "$order"},
            {"$group": {"_id": "$order.customer_id"}},
            {"$count": "total"},
        ]
        result = list(self._db.invoices.aggregate(pipeline))
        return result[0]["total"] if result else 0

    def sum_expenses_total(self, start: date, end: date) -> float:
        pipeline = [
            {
                "$match": {
                    "expense_date": {
                        "$gte": to_bson_value(start),
                        "$lte": to_bson_value(end),
                    }
                }
            },
            {"$group": {"_id": None, "total": {"$sum": "$total_purchase_price"}}},
        ]
        result = list(self._db.expenses.aggregate(pipeline))
        return result[0]["total"] if result else 0.0

    def sum_invoice_margin(self, start: date, end: date) -> float:
        pipeline = [
            {
                "$match": {
                    "invoice_date": {
                        "$gte": to_bson_value(start),
                        "$lte": to_bson_value(end),
                    }
                }
            },
            {"$group": {"_id": None, "total": {"$sum": "$margin_amount"}}},
        ]
        result = list(self._db.invoices.aggregate(pipeline))
        return result[0]["total"] if result else 0.0

    def sum_payment_voucher_amount(
        self, voucher_type: str, start: date, end: date
    ) -> float:
        # Vendor/salary payments are 4-line double-entry vouchers where the paid
        # amount appears on two debit lines, so sum(debits) / 2 == amount.
        pipeline = [
            {
                "$match": {
                    "voucher_type": voucher_type,
                    "voucher_date": {
                        "$gte": to_bson_value(start),
                        "$lte": to_bson_value(end),
                    },
                }
            },
            {"$unwind": "$lines"},
            {"$group": {"_id": None, "debits": {"$sum": "$lines.debit_amount"}}},
        ]
        result = list(self._db.vouchers.aggregate(pipeline))
        return (result[0]["debits"] / 2.0) if result else 0.0

    def count_items_created(self, start: date, end: date) -> int:
        # Per-item created_at is a full datetime, so span the whole end day.
        start_dt = datetime.combine(start, time.min)
        end_dt = datetime.combine(end, time.max)
        pipeline = [
            {"$unwind": "$customization_items"},
            {
                "$match": {
                    "customization_items.created_at": {"$gte": start_dt, "$lte": end_dt}
                }
            },
            {"$count": "total"},
        ]
        result = list(self._db.customization_orders.aggregate(pipeline))
        return result[0]["total"] if result else 0

    def count_items_delivered(self, start: date, end: date) -> int:
        pipeline = [
            {
                "$match": {
                    "delivery_date": {
                        "$gte": to_bson_value(start),
                        "$lte": to_bson_value(end),
                    }
                }
            },
            {"$project": {"n": {"$size": {"$ifNull": ["$bill_ids", []]}}}},
            {"$group": {"_id": None, "total": {"$sum": "$n"}}},
        ]
        result = list(self._db.deliveries.aggregate(pipeline))
        return result[0]["total"] if result else 0

    def item_delivery_snapshot(self) -> dict:
        """Point-in-time counts of items not yet delivered."""
        delivered_ids = self._db.deliveries.distinct("bill_ids")
        pipeline = [
            {"$match": {"order_status": {"$ne": OrderStatus.CANCELLED.value}}},
            {"$unwind": "$customization_items"},
            {"$match": {"customization_items.item_id": {"$nin": delivered_ids}}},
            {
                "$group": {
                    "_id": None,
                    "not_delivered": {"$sum": 1},
                    "awaiting": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$eq": [
                                        "$customization_items.item_status",
                                        CustomizationItemStatus.COMPLETED.value,
                                    ]
                                },
                                1,
                                0,
                            ]
                        }
                    },
                }
            },
        ]
        result = list(self._db.customization_orders.aggregate(pipeline))
        return {
            "not_delivered": result[0]["not_delivered"] if result else 0,
            "awaiting": result[0]["awaiting"] if result else 0,
        }

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

    def get_item_profitability(
        self, start: date | None = None, end: date | None = None
    ) -> List[dict]:
        """One row per customization item whose MPH is frozen (delivered +
        invoiced), highest margin-per-hour first."""
        snapshot_match: dict = {"customization_items.mph_snapshot_at": {"$ne": None}}
        if start is not None and end is not None:
            start_dt = datetime.combine(start, time.min)
            end_dt = datetime.combine(end, time.max)
            snapshot_match["customization_items.mph_snapshot_at"] = {
                "$gte": start_dt,
                "$lte": end_dt,
            }
        pipeline = [
            {"$unwind": "$customization_items"},
            {"$match": snapshot_match},
            {
                "$project": {
                    "_id": 0,
                    "order_number": 1,
                    "customer_name": 1,
                    "bill_number": "$customization_items.bill_number",
                    "description": "$customization_items.description",
                    "sell_amount": "$customization_items.sell_amount",
                    "expense_selling_total": "$customization_items.expense_selling_total",
                    "expense_purchase_total": "$customization_items.expense_purchase_total",
                    "in_house_hours": "$customization_items.in_house_hours",
                    "margin_amount": "$customization_items.margin_amount",
                    "margin_per_hour": "$customization_items.margin_per_hour",
                    "delivered_on": "$customization_items.mph_snapshot_at",
                }
            },
            {"$sort": {"margin_per_hour": -1}},
        ]
        return list(self._db.customization_orders.aggregate(pipeline))

    def get_time_entries(
        self,
        start: date,
        end: date,
        worker: str | None = None,
        activity_name: str | None = None,
    ) -> List[dict]:
        query: dict = {
            "work_date": {
                "$gte": to_bson_value(start),
                "$lte": to_bson_value(end),
            }
        }
        if worker:
            query["worker_name"] = {"$regex": worker, "$options": "i"}
        if activity_name:
            query["activity_name"] = {"$regex": activity_name, "$options": "i"}
        return list(self._db.time_entries.find(query).sort("work_date", -1))

    def labor_minutes_by_order(
        self, start: date | None = None, end: date | None = None
    ) -> dict:
        """Sum of logged time-entry minutes per order_number.

        This reflects *actual* labor logged in time_entries, unlike the item-level
        ``in_house_hours`` snapshot which can be stale/zero. Optionally filtered by
        work_date range.
        """
        match: dict = {}
        if start is not None and end is not None:
            match["work_date"] = {
                "$gte": to_bson_value(start),
                "$lte": to_bson_value(end),
            }
        pipeline: list = []
        if match:
            pipeline.append({"$match": match})
        pipeline.append(
            {
                "$group": {
                    "_id": "$order_number",
                    "minutes": {"$sum": "$duration_minutes"},
                }
            }
        )
        return {
            (row["_id"] or ""): int(row["minutes"] or 0)
            for row in self._db.time_entries.aggregate(pipeline)
        }

    def get_expenses(
        self,
        start: date,
        end: date,
        expense_source: str | None = None,
    ) -> List[dict]:
        query: dict = {
            "expense_date": {
                "$gte": to_bson_value(start),
                "$lte": to_bson_value(end),
            }
        }
        if expense_source:
            query["expense_source"] = expense_source
        return list(self._db.expenses.find(query).sort("expense_date", -1))

    def get_orders_for_activity_pending(self) -> List[dict]:
        return list(
            self._db.customization_orders.find(
                {"order_status": {"$nin": _INACTIVE_STATUSES + [OrderStatus.CANCELLED.value]}},
                {
                    "order_number": 1,
                    "customer_name": 1,
                    "order_status": 1,
                    "expected_delivery_date": 1,
                    "order_activities": 1,
                },
            )
        )

    def get_customer_orders(
        self,
        customer_id: str,
        start: date | None = None,
        end: date | None = None,
    ) -> List[dict]:
        query: dict = {"customer_id": customer_id}
        if start is not None and end is not None:
            query["order_date"] = {
                "$gte": to_bson_value(start),
                "$lte": to_bson_value(end),
            }
        return list(
            self._db.customization_orders.find(query).sort("order_date", -1)
        )

    def get_completed_orders(
        self, start: date, end: date, statuses: List[str]
    ) -> List[dict]:
        query = {
            "order_status": {"$in": statuses},
            "delivery_date": {
                "$gte": to_bson_value(start),
                "$lte": to_bson_value(end),
            },
        }
        projection = {
            **_CARD_PROJECTION,
            "order_date": 1,
            "delivery_date": 1,
        }
        return [
            self._normalize_order(d)
            for d in self._db.customization_orders.find(query, projection).sort(
                "delivery_date", -1
            )
        ]

    def get_bills_pending_invoice_rows(self, limit: int = 500) -> List[dict]:
        pipeline = [
            {"$match": {"order_status": {"$ne": OrderStatus.CANCELLED.value}}},
            {"$unwind": "$bill_numbers"},
            {"$match": {"bill_numbers.bill_id": {"$ne": None}}},
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
                    "order_number": 1,
                    "customer_name": 1,
                    "order_status": 1,
                    "expected_delivery_date": 1,
                    "bill_id": "$bill_numbers.bill_id",
                    "bill_number": "$bill_numbers.bill_number",
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
            {
                "$project": {
                    "_id": 0,
                    "order_number": 1,
                    "customer_name": 1,
                    "bill_number": 1,
                    "order_status": 1,
                    "expected_delivery_date": 1,
                }
            },
            {"$limit": limit},
        ]
        return list(self._db.customization_orders.aggregate(pipeline))

    def get_voucher_totals_by_type(self, start: date, end: date) -> dict:
        from vaybooks.bms.domain.shared.enums import VoucherType

        keys = {
            VoucherType.RECEIPT.value: "receipt",
            VoucherType.REFUND.value: "refund",
            VoucherType.VENDOR_PAYMENT.value: "vendor_payment",
            VoucherType.SALARY_PAYMENT.value: "salary_payment",
        }
        totals: dict[str, float] = {}
        for vtype, key in keys.items():
            if vtype in (
                VoucherType.VENDOR_PAYMENT.value,
                VoucherType.SALARY_PAYMENT.value,
            ):
                totals[key] = self.sum_payment_voucher_amount(vtype, start, end)
            else:
                pipeline = [
                    {
                        "$match": {
                            "voucher_type": vtype,
                            "voucher_date": {
                                "$gte": to_bson_value(start),
                                "$lte": to_bson_value(end),
                            },
                        }
                    },
                    {"$unwind": "$lines"},
                    {
                        "$group": {
                            "_id": None,
                            "total": {"$sum": "$lines.debit_amount"},
                        }
                    },
                ]
                result = list(self._db.vouchers.aggregate(pipeline))
                totals[key] = result[0]["total"] if result else 0.0
        return totals

    def get_orders_pipeline_snapshot(self) -> List[dict]:
        pipeline = [
            {"$match": {"order_status": {"$ne": OrderStatus.CANCELLED.value}}},
            {
                "$group": {
                    "_id": "$order_status",
                    "order_count": {"$sum": 1},
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "order_status": "$_id",
                    "order_count": "$order_count",
                }
            },
            {"$sort": {"order_count": -1}},
        ]
        return list(self._db.customization_orders.aggregate(pipeline))

    def get_all_vouchers(self) -> List[dict]:
        return list(self._db.vouchers.find())
