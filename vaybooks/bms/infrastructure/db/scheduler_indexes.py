"""Index declarations for scheduler collections.

Shared by migration 019 and ``ensure_indexes`` so both stay in step.
"""

from __future__ import annotations

from pymongo import ASCENDING, DESCENDING
from pymongo.database import Database
from pymongo.errors import OperationFailure


def _create_index(collection, keys, **kwargs) -> None:
    try:
        collection.create_index(keys, **kwargs)
    except OperationFailure as exc:
        if exc.code not in (85, 86):  # IndexOptionsConflict / IndexKeySpecsConflict
            raise


def ensure_scheduler_indexes(db: Database) -> None:
    configs = db.scheduler_job_configs
    _create_index(configs, [("job_id", ASCENDING)], unique=True, name="scheduler_job_id")
    _create_index(configs, [("domain", ASCENDING), ("enabled", ASCENDING)])

    logs = db.scheduler_run_logs
    _create_index(logs, [("job_id", ASCENDING), ("started_at", DESCENDING)])
    _create_index(logs, [("started_at", DESCENDING)])
    _create_index(logs, [("trigger", ASCENDING)])

    leases = db.scheduler_job_leases
    _create_index(leases, [("expires_at", ASCENDING)])
    _create_index(
        leases, [("lease_key", ASCENDING)], unique=True, name="scheduler_lease_key"
    )

    notifications = db.scheduler_notifications
    _create_index(
        notifications,
        [("dedupe_key", ASCENDING)],
        unique=True,
        name="scheduler_notifications_dedupe_partial",
        partialFilterExpression={"dedupe_key": {"$type": "string", "$gt": ""}},
    )
    _create_index(
        notifications,
        [("recipient_id", ASCENDING), ("state", ASCENDING), ("created_at", DESCENDING)],
    )

    report_configs = db.scheduler_report_configs
    _create_index(
        report_configs,
        [("domain", ASCENDING), ("report_id", ASCENDING)],
        unique=True,
        name="scheduler_report_config_key",
    )
    _create_index(report_configs, [("domain", ASCENDING), ("enabled", ASCENDING)])

    report_logs = db.scheduler_report_run_logs
    _create_index(
        report_logs,
        [("domain", ASCENDING), ("report_id", ASCENDING), ("started_at", DESCENDING)],
    )
    _create_index(report_logs, [("trigger", ASCENDING)])

    artifacts = db.scheduler_report_artifacts
    _create_index(
        artifacts,
        [("domain", ASCENDING), ("report_id", ASCENDING), ("created_at", DESCENDING)],
    )
    _create_index(artifacts, [("expires_at", ASCENDING)])


def ensure_scheduler_query_indexes(db: Database) -> None:
    """Supporting indexes for the identify queries each domain job runs."""
    _create_index(
        db.crm_activities,
        [("status", ASCENDING), ("scheduled_at", ASCENDING), ("assigned_user_id", ASCENDING)],
    )
    _create_index(db.crm_activities, [("promised_date", ASCENDING), ("status", ASCENDING)])
    _create_index(
        db.crm_activities,
        [("customer_id", ASCENDING), ("activity_at", ASCENDING), ("origin", ASCENDING)],
    )
    _create_index(
        db.crm_leads,
        [("status", ASCENDING), ("next_follow_up_at", ASCENDING), ("is_deleted", ASCENDING)],
    )
    _create_index(
        db.crm_leads,
        [
            ("priority", ASCENDING),
            ("status", ASCENDING),
            ("last_activity_at", ASCENDING),
            ("assigned_user_id", ASCENDING),
        ],
    )
    _create_index(
        db.crm_leads,
        [
            ("assigned_user_id", ASCENDING),
            ("status", ASCENDING),
            ("created_at", ASCENDING),
            ("is_deleted", ASCENDING),
        ],
    )
    _create_index(
        db.crm_enquiries,
        [
            ("status", ASCENDING),
            ("updated_at", ASCENDING),
            ("next_follow_up_at", ASCENDING),
            ("assigned_user_id", ASCENDING),
        ],
    )

    _create_index(db.accounts, [("linked_customer_id", ASCENDING), ("current_balance", ASCENDING)])
    _create_index(db.accounts, [("linked_vendor_id", ASCENDING), ("current_balance", ASCENDING)])
    _create_index(db.vouchers, [("voucher_type", ASCENDING), ("voucher_date", ASCENDING)])
    _create_index(db.vouchers, [("reference_invoice_id", ASCENDING)])

    _create_index(db.quotations, [("status", ASCENDING), ("valid_until", ASCENDING)])
    _create_index(db.estimates, [("status", ASCENDING), ("valid_until", ASCENDING)])
    _create_index(db.sales_orders, [("status", ASCENDING), ("expected_date", ASCENDING)])
    _create_index(db.sales_orders, [("status", ASCENDING), ("order_date", ASCENDING)])
    _create_index(db.delivery_notes, [("status", ASCENDING), ("delivery_date", ASCENDING)])
    _create_index(db.sales_returns, [("status", ASCENDING), ("return_date", ASCENDING)])

    _create_index(db.purchase_orders, [("status", ASCENDING), ("expected_date", ASCENDING)])
    _create_index(db.purchase_orders, [("status", ASCENDING), ("order_date", ASCENDING)])
    _create_index(db.goods_receipts, [("status", ASCENDING), ("receipt_date", ASCENDING)])

    _create_index(db.inventory_products, [("is_active", ASCENDING), ("current_qty", ASCENDING)])
    _create_index(
        db.inventory_products,
        [("current_qty", ASCENDING)],
        name="inventory_products_negative_qty",
        partialFilterExpression={"current_qty": {"$lt": 0}},
    )
    _create_index(
        db.stock_balances,
        [("qty", ASCENDING)],
        name="stock_balances_negative_qty",
        partialFilterExpression={"qty": {"$lt": 0}},
    )
    _create_index(db.stock_transfers, [("status", ASCENDING), ("transfer_date", ASCENDING)])

    _create_index(
        db.customization_orders,
        [("order_status", ASCENDING), ("expected_delivery_date", ASCENDING)],
    )
    _create_index(
        db.customization_orders,
        [("customization_items.expected_delivery_date", ASCENDING)],
    )
    _create_index(
        db.customization_orders,
        [("order_activities.activity_status", ASCENDING), ("order_status", ASCENDING)],
    )

    _create_index(db.projects, [("status", ASCENDING), ("expected_end_date", ASCENDING)])
    _create_index(db.projects, [("status", ASCENDING), ("dlp_months", ASCENDING)])
    _create_index(
        db.projects, [("activities.status", ASCENDING), ("activities.planned_end", ASCENDING)]
    )
    _create_index(
        db.project_dprs,
        [("project_id", ASCENDING), ("report_date", ASCENDING), ("status", ASCENDING)],
    )
    _create_index(db.project_quotations, [("status", ASCENDING), ("valid_until", ASCENDING)])
    _create_index(db.project_material_requests, [("status", ASCENDING), ("need_by", ASCENDING)])
    _create_index(db.project_ra_bills, [("project_id", ASCENDING), ("status", ASCENDING)])
    _create_index(db.project_measurements, [("status", ASCENDING), ("updated_at", ASCENDING)])
    _create_index(db.project_variations, [("status", ASCENDING), ("updated_at", ASCENDING)])
    _create_index(
        db.project_quality_issues, [("status", ASCENDING), ("raised_date", ASCENDING)]
    )
    _create_index(
        db.project_quality_issues, [("project_id", ASCENDING), ("status", ASCENDING)]
    )
