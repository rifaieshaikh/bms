"""CRM module collections, indexes, and default settings seed.

Note: plan referred to 014_crm_module.py; 014–016 already exist and 017 is
reserved for CRM entitlements, so this migration is numbered 018.
"""

from __future__ import annotations

from datetime import datetime

from pymongo.database import Database

from vaybooks.bms.domain.crm.entities import CrmSettings
from vaybooks.bms.domain.crm.enums import CRM_SETTINGS_ID
from vaybooks.bms.infrastructure.repositories.crm._serialize import settings_to_doc


def _create_index(collection, keys, **kwargs):
    collection.create_index(keys, **kwargs)


def up(db: Database) -> None:
    now = datetime.utcnow()

    # --- crm_leads ---
    # Contact identifiers are intentionally non-unique: authorised users may
    # keep a separate lead after acknowledging a potential duplicate. Domain
    # services perform duplicate detection before normal creates/imports.
    leads = db.crm_leads
    _create_index(
        leads,
        [("phone_normalized", 1)],
        name="crm_leads_phone_normalized_partial",
    )
    _create_index(
        leads,
        [("email_normalized", 1)],
        name="crm_leads_email_normalized_partial",
    )
    _create_index(
        leads,
        [("gstin_normalized", 1)],
        name="crm_leads_gstin_normalized_partial",
    )
    _create_index(leads, "status")
    _create_index(leads, "assigned_user_id")
    _create_index(leads, "next_follow_up_at")
    _create_index(leads, "source")
    _create_index(leads, "created_at")
    _create_index(leads, "import_batch_id")
    _create_index(leads, "branch")
    _create_index(
        leads,
        "lead_number",
        unique=True,
        partialFilterExpression={"lead_number": {"$type": "string", "$gt": ""}},
    )
    _create_index(
        leads,
        [("import_batch_id", 1), ("import_row_fingerprint", 1)],
        unique=True,
        name="crm_leads_import_fingerprint",
        partialFilterExpression={
            "import_batch_id": {"$type": "string", "$gt": ""},
            "import_row_fingerprint": {"$type": "string", "$gt": ""},
        },
    )

    # --- crm_enquiries ---
    enquiries = db.crm_enquiries
    _create_index(enquiries, "enquiry_number")
    _create_index(enquiries, "status")
    _create_index(enquiries, "assigned_user_id")
    _create_index(enquiries, "next_follow_up_at")
    _create_index(enquiries, "lead_id")
    _create_index(enquiries, "customer_id")
    _create_index(enquiries, "branch")

    # --- crm_activities: unique auto-activity idempotency ---
    activities = db.crm_activities
    _create_index(
        activities,
        [
            ("source_module", 1),
            ("source_txn_type", 1),
            ("source_txn_id", 1),
            ("activity_type_key", 1),
        ],
        unique=True,
        name="crm_activities_auto_idempotency_partial",
        partialFilterExpression={
            "source_module": {"$type": "string", "$gt": ""},
            "source_txn_type": {"$type": "string", "$gt": ""},
            "source_txn_id": {"$type": "string", "$gt": ""},
            "activity_type_key": {"$type": "string", "$gt": ""},
        },
    )
    _create_index(activities, "lead_id")
    _create_index(activities, "enquiry_id")
    _create_index(activities, "customer_id")
    _create_index(activities, "assigned_user_id")
    _create_index(activities, "scheduled_at")
    _create_index(activities, "status")
    _create_index(activities, "activity_type")
    _create_index(activities, "branch")

    # --- notifications dedupe ---
    notifications = db.crm_notifications
    _create_index(
        notifications,
        [("dedupe_key", 1)],
        unique=True,
        name="crm_notifications_dedupe_partial",
        partialFilterExpression={"dedupe_key": {"$type": "string", "$gt": ""}},
    )
    _create_index(notifications, "recipient_id")
    _create_index(notifications, [("recipient_id", 1), ("kind", 1), ("ref_type", 1), ("ref_id", 1), ("state", 1)])

    prefs = db.crm_notification_preferences
    _create_index(prefs, "user_id", unique=True)

    audits = db.crm_audit_entries
    _create_index(audits, [("entity_type", 1), ("entity_id", 1)])
    _create_index(audits, "created_at")

    batches = db.crm_import_batches
    _create_index(batches, "file_hash")
    _create_index(batches, "created_at")

    # --- seed default settings ---
    settings_col = db.crm_settings
    if not settings_col.find_one({"_id": CRM_SETTINGS_ID}):
        settings = CrmSettings()
        settings.updated_at = now
        settings_col.insert_one(settings_to_doc(settings))

    # Customer assignee index (non-unique)
    try:
        db.customers.create_index("assigned_user_id")
    except Exception:
        pass
