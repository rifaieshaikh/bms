"""Projected Mongo queries backing the scheduler identify phase.

Every method projects `_id` (or a tiny tuple) and applies a hard limit so a
large database never produces an unbounded in-memory result.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Sequence, Tuple

from pymongo.database import Database


def _ids(cursor) -> List[str]:
    return [str(doc["_id"]) for doc in cursor]


def _date_before(field: str, boundary: date) -> Dict[str, Any]:
    """Match documents whose date field precedes ``boundary``.

    Sales, purchase, and inventory documents persist dates as ISO strings while
    boutique and project documents persist BSON datetimes, so both encodings are
    matched.
    """
    as_dt = datetime.combine(boundary, datetime.min.time())
    return {
        "$or": [
            {field: {"$lt": boundary.isoformat(), "$type": "string"}},
            {field: {"$lt": as_dt, "$type": "date"}},
        ]
    }


def _date_on_or_before(field: str, boundary: date) -> Dict[str, Any]:
    as_dt = datetime.combine(boundary, datetime.max.time())
    return {
        "$or": [
            {field: {"$lte": boundary.isoformat(), "$type": "string"}},
            {field: {"$lte": as_dt, "$type": "date"}},
        ]
    }


class MongoSchedulerQueries:
    def __init__(self, db: Database):
        self._db = db

    # --- CRM -----------------------------------------------------------------

    def crm_activity_ids_scheduled_between(
        self, start: datetime, end: datetime, *, limit: int
    ) -> List[str]:
        cursor = self._db.crm_activities.find(
            {
                "status": {"$in": ["Scheduled", "In Progress"]},
                "scheduled_at": {"$gte": start, "$lt": end},
                "assigned_user_id": {"$nin": ["", None]},
            },
            {"_id": 1},
        ).limit(limit)
        return _ids(cursor)

    def crm_activity_ids_overdue(self, before: datetime, *, limit: int) -> List[str]:
        cursor = self._db.crm_activities.find(
            {
                "status": {"$in": ["Scheduled", "In Progress"]},
                "scheduled_at": {"$lt": before, "$ne": None},
            },
            {"_id": 1},
        ).limit(limit)
        return _ids(cursor)

    def crm_activity_ids_by_type_scheduled_between(
        self, type_keys: Sequence[str], start: datetime, end: datetime, *, limit: int
    ) -> List[str]:
        if not type_keys:
            return []
        cursor = self._db.crm_activities.find(
            {
                "status": {"$in": ["Scheduled", "In Progress"]},
                "activity_type_key": {"$in": list(type_keys)},
                "scheduled_at": {"$gte": start, "$lt": end},
            },
            {"_id": 1},
        ).limit(limit)
        return _ids(cursor)

    def crm_activity_ids_promise_due(
        self, boundary: datetime, *, limit: int
    ) -> List[str]:
        cursor = self._db.crm_activities.find(
            {
                "promised_date": {"$lte": boundary, "$ne": None},
                "status": {"$nin": ["Cancelled", "Reversed"]},
            },
            {"_id": 1},
        ).limit(limit)
        return _ids(cursor)

    def crm_lead_ids_follow_up_due(self, before: datetime, *, limit: int) -> List[str]:
        cursor = self._db.crm_leads.find(
            {
                "is_deleted": {"$ne": True},
                "status": {"$nin": ["Converted", "Lost", "Not Interested"]},
                "next_follow_up_at": {"$lt": before, "$ne": None},
            },
            {"_id": 1},
        ).limit(limit)
        return _ids(cursor)

    def crm_lead_ids_high_priority_idle(
        self, priorities: Sequence[str], before: datetime, *, limit: int
    ) -> List[str]:
        cursor = self._db.crm_leads.find(
            {
                "is_deleted": {"$ne": True},
                "priority": {"$in": list(priorities or ["High", "Urgent"])},
                "status": {"$nin": ["Converted", "Lost", "Not Interested"]},
                "assigned_user_id": {"$nin": ["", None]},
                "$or": [
                    {"last_activity_at": None},
                    {"last_activity_at": {"$exists": False}},
                    {"last_activity_at": {"$lt": before}},
                ],
            },
            {"_id": 1},
        ).limit(limit)
        return _ids(cursor)

    def crm_lead_ids_unassigned(self, before: datetime, *, limit: int) -> List[str]:
        cursor = self._db.crm_leads.find(
            {
                "is_deleted": {"$ne": True},
                "status": {"$nin": ["Converted", "Lost", "Not Interested"]},
                "$or": [
                    {"assigned_user_id": ""},
                    {"assigned_user_id": None},
                    {"assigned_user_id": {"$exists": False}},
                ],
                "created_at": {"$lt": before},
            },
            {"_id": 1},
        ).limit(limit)
        return _ids(cursor)

    def crm_enquiry_ids_stale(self, before: datetime, *, limit: int) -> List[str]:
        cursor = self._db.crm_enquiries.find(
            {
                "is_deleted": {"$ne": True},
                "status": {"$nin": ["Converted", "Lost", "Closed", "Cancelled"]},
                "$or": [
                    {"updated_at": {"$lt": before}},
                    {"next_follow_up_at": {"$lt": before, "$ne": None}},
                ],
            },
            {"_id": 1},
        ).limit(limit)
        return _ids(cursor)

    def crm_customer_ids_without_activity_since(
        self, since: datetime, *, limit: int
    ) -> List[str]:
        recent = self._db.crm_activities.distinct(
            "customer_id",
            {"activity_at": {"$gte": since}, "origin": "Manual"},
        )
        cursor = self._db.customers.find(
            {"_id": {"$nin": [r for r in recent if r]}}, {"_id": 1}
        ).limit(limit)
        return _ids(cursor)

    def crm_customer_ids_without_visit_since(
        self, type_keys: Sequence[str], since: datetime, *, limit: int
    ) -> List[str]:
        visited = self._db.crm_activities.distinct(
            "customer_id",
            {
                "activity_type_key": {"$in": list(type_keys or [])},
                "status": "Completed",
                "completed_at": {"$gte": since},
            },
        )
        cursor = self._db.customers.find(
            {"_id": {"$nin": [v for v in visited if v]}}, {"_id": 1}
        ).limit(limit)
        return _ids(cursor)

    def receivable_customer_ids(self, minimum: float, *, limit: int) -> List[str]:
        cursor = self._db.accounts.find(
            {
                "linked_customer_id": {"$type": "string", "$ne": ""},
                "current_balance": {"$gte": float(minimum)},
            },
            {"linked_customer_id": 1},
        ).limit(limit)
        return [str(d["linked_customer_id"]) for d in cursor if d.get("linked_customer_id")]

    def crm_customer_ids_with_recent_collection(
        self, type_keys: Sequence[str], since: datetime
    ) -> List[str]:
        values = self._db.crm_activities.distinct(
            "customer_id",
            {
                "activity_type_key": {"$in": list(type_keys or [])},
                "activity_at": {"$gte": since},
            },
        )
        return [str(v) for v in values if v]

    # --- Sales ---------------------------------------------------------------

    def sales_document_ids_expiring(
        self,
        collection: str,
        statuses: Sequence[str],
        on_or_before: date,
        *,
        limit: int,
    ) -> List[str]:
        query = {
            "status": {"$in": list(statuses)},
            "valid_until": {"$ne": None, "$exists": True},
        }
        query.update(_date_on_or_before("valid_until", on_or_before))
        cursor = self._db[collection].find(query, {"_id": 1}).limit(limit)
        return _ids(cursor)

    def sales_order_ids_overdue(
        self, statuses: Sequence[str], before: date, *, limit: int
    ) -> List[str]:
        query: Dict[str, Any] = {
            "status": {"$in": list(statuses)},
            "expected_date": {"$ne": None, "$exists": True},
        }
        query.update(_date_before("expected_date", before))
        cursor = self._db.sales_orders.find(query, {"_id": 1}).limit(limit)
        return _ids(cursor)

    def sales_order_ids_without_progress(
        self, statuses: Sequence[str], before: date, *, limit: int
    ) -> List[str]:
        query: Dict[str, Any] = {
            "status": {"$in": list(statuses)},
            "lines": {"$not": {"$elemMatch": {"qty_delivered": {"$gt": 0}}}},
        }
        query.update(_date_before("order_date", before))
        cursor = self._db.sales_orders.find(query, {"_id": 1}).limit(limit)
        return _ids(cursor)

    def sales_document_ids_by_status_before(
        self,
        collection: str,
        statuses: Sequence[str],
        date_field: str,
        before: date,
        *,
        limit: int,
    ) -> List[str]:
        query: Dict[str, Any] = {"status": {"$in": list(statuses)}}
        query.update(_date_before(date_field, before))
        cursor = self._db[collection].find(query, {"_id": 1}).limit(limit)
        return _ids(cursor)

    # --- Purchases -----------------------------------------------------------

    def purchase_order_ids_overdue(
        self, statuses: Sequence[str], before: date, *, limit: int
    ) -> List[str]:
        query: Dict[str, Any] = {
            "status": {"$in": list(statuses)},
            "expected_date": {"$ne": None, "$exists": True},
        }
        query.update(_date_before("expected_date", before))
        cursor = self._db.purchase_orders.find(query, {"_id": 1}).limit(limit)
        return _ids(cursor)

    def purchase_order_ids_without_receipt(
        self, statuses: Sequence[str], before: date, *, limit: int
    ) -> List[str]:
        query: Dict[str, Any] = {
            "status": {"$in": list(statuses)},
            "lines": {"$not": {"$elemMatch": {"qty_received": {"$gt": 0}}}},
        }
        query.update(_date_before("order_date", before))
        cursor = self._db.purchase_orders.find(query, {"_id": 1}).limit(limit)
        return _ids(cursor)

    def vendor_ids_with_open_bills(self, minimum: float, *, limit: int) -> List[str]:
        cursor = self._db.accounts.find(
            {
                "linked_vendor_id": {"$type": "string", "$ne": ""},
                "current_balance": {"$lte": -float(minimum)},
            },
            {"linked_vendor_id": 1},
        ).limit(limit)
        return [str(d["linked_vendor_id"]) for d in cursor if d.get("linked_vendor_id")]

    # --- Inventory -----------------------------------------------------------

    def product_ids_low_stock(self, threshold: float, *, limit: int) -> List[str]:
        cursor = self._db.inventory_products.find(
            {"is_active": True, "current_qty": {"$gte": 0, "$lte": float(threshold)}},
            {"_id": 1},
        ).limit(limit)
        return _ids(cursor)

    def product_ids_negative_stock(self, *, limit: int) -> List[str]:
        cursor = self._db.inventory_products.find(
            {"current_qty": {"$lt": -0.001}}, {"_id": 1}
        ).limit(limit)
        return _ids(cursor)

    def stock_balance_keys_negative(self, *, limit: int) -> List[str]:
        cursor = self._db.stock_balances.find(
            {"qty": {"$lt": -0.001}}, {"product_id": 1, "location_id": 1}
        ).limit(limit)
        return [
            f"{d.get('product_id', '')}|{d.get('location_id', '')}"
            for d in cursor
            if d.get("product_id")
        ]

    def product_ids_inactive_with_stock(
        self, minimum_qty: float, *, limit: int
    ) -> List[str]:
        cursor = self._db.inventory_products.find(
            {"is_active": False, "current_qty": {"$gt": float(minimum_qty)}},
            {"_id": 1},
        ).limit(limit)
        return _ids(cursor)

    def stock_transfer_ids_stale(
        self, statuses: Sequence[str], before: date, *, limit: int
    ) -> List[str]:
        query: Dict[str, Any] = {"status": {"$in": list(statuses)}}
        query.update(_date_before("transfer_date", before))
        cursor = self._db.stock_transfers.find(query, {"_id": 1}).limit(limit)
        return _ids(cursor)

    # --- Boutique ------------------------------------------------------------

    def boutique_order_ids_by_etd(
        self,
        exclude_statuses: Sequence[str],
        start: datetime,
        end: datetime,
        *,
        limit: int,
    ) -> List[str]:
        cursor = self._db.customization_orders.find(
            {
                "order_status": {"$nin": list(exclude_statuses)},
                "expected_delivery_date": {"$gte": start, "$lt": end},
            },
            {"_id": 1},
        ).limit(limit)
        return _ids(cursor)

    def boutique_order_ids_etd_before(
        self, exclude_statuses: Sequence[str], before: datetime, *, limit: int
    ) -> List[str]:
        cursor = self._db.customization_orders.find(
            {
                "order_status": {"$nin": list(exclude_statuses)},
                "expected_delivery_date": {"$lt": before, "$ne": None},
            },
            {"_id": 1},
        ).limit(limit)
        return _ids(cursor)

    def boutique_item_refs_due(
        self, exclude_statuses: Sequence[str], on_or_before: datetime, *, limit: int
    ) -> List[str]:
        pipeline = [
            {"$match": {"order_status": {"$nin": list(exclude_statuses)}}},
            {"$unwind": "$customization_items"},
            {
                "$match": {
                    "customization_items.expected_delivery_date": {
                        "$lte": on_or_before,
                        "$ne": None,
                    },
                    "customization_items.is_cancellation_charge": {"$ne": True},
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "ref": {
                        "$concat": [
                            {"$toString": "$_id"},
                            "|",
                            {"$toString": "$customization_items.bill_number"},
                        ]
                    },
                }
            },
            {"$limit": int(limit)},
        ]
        return [d["ref"] for d in self._db.customization_orders.aggregate(pipeline)]

    def boutique_activity_bottlenecks(
        self, exclude_statuses: Sequence[str], statuses: Sequence[str]
    ) -> Dict[str, Tuple[int, int]]:
        pipeline = [
            {"$match": {"order_status": {"$nin": list(exclude_statuses)}}},
            {"$unwind": "$order_activities"},
            {
                "$match": {
                    "order_activities.activity_status": {"$in": list(statuses)},
                    "order_activities.is_required": {"$ne": False},
                }
            },
            {
                "$group": {
                    "_id": "$order_activities.activity_name",
                    "pending": {"$sum": 1},
                    "overdue": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$lt": [
                                        "$expected_delivery_date",
                                        datetime.utcnow(),
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
        out: Dict[str, Tuple[int, int]] = {}
        for doc in self._db.customization_orders.aggregate(pipeline):
            name = doc.get("_id") or ""
            if name:
                out[name] = (int(doc.get("pending", 0)), int(doc.get("overdue", 0)))
        return out

    def boutique_activity_refs_overdue(
        self,
        exclude_statuses: Sequence[str],
        statuses: Sequence[str],
        before: datetime,
        *,
        limit: int,
    ) -> List[str]:
        pipeline = [
            {
                "$match": {
                    "order_status": {"$nin": list(exclude_statuses)},
                    "expected_delivery_date": {"$lt": before, "$ne": None},
                }
            },
            {"$unwind": "$order_activities"},
            {
                "$match": {
                    "order_activities.activity_status": {"$in": list(statuses)},
                    "order_activities.is_required": {"$ne": False},
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "ref": {
                        "$concat": [
                            {"$toString": "$_id"},
                            "|",
                            {"$toString": "$order_activities.activity_name"},
                        ]
                    },
                }
            },
            {"$limit": int(limit)},
        ]
        return [d["ref"] for d in self._db.customization_orders.aggregate(pipeline)]

    def boutique_order_ids_pending_invoice(
        self, exclude_statuses: Sequence[str], *, limit: int
    ) -> List[str]:
        invoiced = self._invoiced_bill_numbers()
        pipeline = [
            {"$match": {"order_status": {"$nin": list(exclude_statuses)}}},
            {"$unwind": "$customization_items"},
            {
                "$match": {
                    "customization_items.is_cancellation_charge": {"$ne": True},
                    "customization_items.bill_number": {"$nin": invoiced},
                }
            },
            {"$group": {"_id": "$_id"}},
            {"$limit": int(limit)},
        ]
        return [str(d["_id"]) for d in self._db.customization_orders.aggregate(pipeline)]

    def boutique_order_ids_pending_delivery(
        self, exclude_statuses: Sequence[str], *, limit: int
    ) -> List[str]:
        delivered = self._delivered_bill_numbers()
        pipeline = [
            {"$match": {"order_status": {"$nin": list(exclude_statuses)}}},
            {"$unwind": "$customization_items"},
            {
                "$match": {
                    "customization_items.is_cancellation_charge": {"$ne": True},
                    "customization_items.bill_number": {"$nin": delivered},
                }
            },
            {"$group": {"_id": "$_id"}},
            {"$limit": int(limit)},
        ]
        return [str(d["_id"]) for d in self._db.customization_orders.aggregate(pipeline)]

    def _invoiced_bill_numbers(self) -> List[str]:
        values = self._db.invoices.distinct("bill_ids")
        return [str(v) for v in values if v]

    def _delivered_bill_numbers(self) -> List[str]:
        values = self._db.deliveries.distinct("bill_ids")
        return [str(v) for v in values if v]

    def boutique_invoice_ids_with_outstanding(
        self, before: datetime, *, limit: int
    ) -> List[str]:
        referenced = [
            str(v)
            for v in self._db.vouchers.distinct(
                "reference_invoice_id", {"voucher_type": "Sales Invoice"}
            )
            if v
        ]
        if not referenced:
            return []
        cursor = self._db.invoices.find(
            {
                "_id": {"$in": referenced},
                "is_cancellation": {"$ne": True},
                "invoice_date": {"$lte": before},
            },
            {"_id": 1},
        ).limit(limit)
        return _ids(cursor)

    # --- Projects ------------------------------------------------------------

    def project_activity_refs_overdue(
        self,
        project_statuses: Sequence[str],
        activity_statuses: Sequence[str],
        before: datetime,
        *,
        limit: int,
    ) -> List[str]:
        pipeline = [
            {"$match": {"status": {"$in": list(project_statuses)}}},
            {"$unwind": "$activities"},
            {
                "$match": {
                    "activities.status": {"$in": list(activity_statuses)},
                    "activities.planned_end": {"$lt": before, "$ne": None},
                }
            },
            {
                "$project": {
                    "_id": 0,
                    "ref": {
                        "$concat": [
                            {"$toString": "$_id"},
                            "|",
                            {"$toString": "$activities.id"},
                        ]
                    },
                }
            },
            {"$limit": int(limit)},
        ]
        return [d["ref"] for d in self._db.projects.aggregate(pipeline)]

    def project_ids_end_overdue(
        self, statuses: Sequence[str], before: datetime, *, limit: int
    ) -> List[str]:
        cursor = self._db.projects.find(
            {
                "status": {"$in": list(statuses)},
                "expected_end_date": {"$lt": before, "$ne": None},
            },
            {"_id": 1},
        ).limit(limit)
        return _ids(cursor)

    def project_ids_active(self, statuses: Sequence[str], *, limit: int) -> List[str]:
        cursor = self._db.projects.find(
            {"status": {"$in": list(statuses)}}, {"_id": 1}
        ).limit(limit)
        return _ids(cursor)

    def project_ids_with_dpr_on(
        self, project_ids: Sequence[str], day: date, statuses: Sequence[str]
    ) -> List[str]:
        if not project_ids:
            return []
        start = datetime.combine(day, datetime.min.time())
        end = datetime.combine(day, datetime.max.time())
        values = self._db.project_dprs.distinct(
            "project_id",
            {
                "project_id": {"$in": list(project_ids)},
                "status": {"$in": list(statuses)},
                "$or": [
                    {"report_date": {"$gte": start, "$lte": end}},
                    {"report_date": day.isoformat()},
                ],
            },
        )
        return [str(v) for v in values if v]

    def project_document_ids_by_status(
        self,
        collection: str,
        statuses: Sequence[str],
        date_field: str,
        before: datetime,
        *,
        limit: int,
    ) -> List[str]:
        query: Dict[str, Any] = {"status": {"$in": list(statuses)}}
        if date_field:
            query[date_field] = {"$lt": before}
        cursor = self._db[collection].find(query, {"_id": 1}).limit(limit)
        return _ids(cursor)

    def project_document_ids_date_before(
        self,
        collection: str,
        statuses: Sequence[str],
        date_field: str,
        boundary: datetime,
        *,
        limit: int,
    ) -> List[str]:
        query: Dict[str, Any] = {
            "status": {"$in": list(statuses)},
            date_field: {"$lte": boundary, "$ne": None},
        }
        cursor = self._db[collection].find(query, {"_id": 1}).limit(limit)
        return _ids(cursor)

    def project_ids_dlp_candidates(
        self, statuses: Sequence[str], *, limit: int
    ) -> List[str]:
        cursor = self._db.projects.find(
            {"status": {"$in": list(statuses)}, "dlp_months": {"$gt": 0}}, {"_id": 1}
        ).limit(limit)
        return _ids(cursor)
