"""Indexes and seed for Wave 1 access / audit collections."""


def up(db) -> None:
    db.app_users.create_index("username", unique=True)
    db.project_memberships.create_index([("project_id", 1), ("user_id", 1)])
    db.project_audit_entries.create_index([("project_id", 1), ("created_at", -1)])
    db.project_expenses.create_index([("project_id", 1), ("cost_category", 1)])
    db.project_time_entries.create_index([("project_id", 1), ("activity_id", 1)])
    db.project_cash_flow_plans.create_index([("project_id", 1), ("period_start", 1)])
    db.project_offline_drafts.create_index([("project_id", 1), ("synced", 1)])
    db.project_portal_tokens.create_index("token", unique=True)
