"""Create indexes for project accounting collections."""

from __future__ import annotations

from pymongo.database import Database


def up(db: Database) -> None:
    db.project_enquiries.create_index("enquiry_number", unique=True)
    db.project_enquiries.create_index("project_id")
    db.project_enquiries.create_index("status")
    db.project_enquiries.create_index("customer_id")
    db.project_site_assessments.create_index("enquiry_id")

    db.project_dprs.create_index("project_id")
    db.project_dprs.create_index("idempotency_key")

    db.project_material_requests.create_index("project_id")
    db.project_rfqs.create_index("project_id")
    db.project_site_stock_movements.create_index("project_id")

    db.project_subcontract_orders.create_index("project_id")
    db.project_petty_cash_advances.create_index("project_id")

    db.project_recognition_entries.create_index("project_id")
    db.project_recognition_entries.create_index("idempotency_key")
    db.project_reconciliations.create_index("project_id")

    db.project_quality_issues.create_index("project_id")
    db.project_handovers.create_index("project_id", unique=True)
    db.project_wbs_nodes.create_index("project_id")
    db.project_config_snapshots.create_index("project_id")
    db.project_config_snapshots.create_index(
        [("project_id", 1), ("revision", -1)]
    )

    db.project_budget_headers.create_index("project_id", unique=True)
