"""Shared CRM Mongo document serialization helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from vaybooks.bms.domain.crm.entities import (
    CrmActivity,
    CrmAuditEntry,
    CrmEnquiry,
    CrmImportBatch,
    CrmLead,
    CrmNotification,
    CrmNotificationPreferences,
    CrmSettings,
)
from vaybooks.bms.domain.crm.enums import CRM_SETTINGS_ID


def lead_to_doc(lead: CrmLead) -> dict:
    return {
        "_id": lead.id,
        "lead_number": lead.lead_number,
        "name": lead.name,
        "contact_person": lead.contact_person,
        "phone": lead.phone,
        "alternate_phone": lead.alternate_phone,
        "email": lead.email,
        "address_line1": lead.address_line1,
        "address_line2": lead.address_line2,
        "area": lead.area,
        "city": lead.city,
        "state_code": lead.state_code,
        "pincode": lead.pincode,
        "gstin": lead.gstin,
        "source": lead.source,
        "interested_products": lead.interested_products,
        "estimated_value": float(lead.estimated_value or 0),
        "assigned_user_id": lead.assigned_user_id,
        "assigned_user_name": lead.assigned_user_name,
        "priority": lead.priority,
        "status": lead.status,
        "next_follow_up_at": lead.next_follow_up_at,
        "notes": lead.notes,
        "last_activity_at": lead.last_activity_at,
        "phone_normalized": lead.phone_normalized,
        "email_normalized": lead.email_normalized,
        "gstin_normalized": lead.gstin_normalized,
        "customer_id": lead.customer_id,
        "customer_name": lead.customer_name,
        "converted_at": lead.converted_at,
        "converted_by_id": lead.converted_by_id,
        "converted_by_name": lead.converted_by_name,
        "lost_reason": lead.lost_reason,
        "lost_at": lead.lost_at,
        "lost_by_id": lead.lost_by_id,
        "lost_by_name": lead.lost_by_name,
        "import_batch_id": lead.import_batch_id,
        "import_row_fingerprint": lead.import_row_fingerprint,
        "branch": lead.branch,
        "is_deleted": lead.is_deleted,
        "deleted_at": lead.deleted_at,
        "created_by_id": lead.created_by_id,
        "created_by_name": lead.created_by_name,
        "updated_by_id": lead.updated_by_id,
        "updated_by_name": lead.updated_by_name,
        "created_at": lead.created_at,
        "updated_at": lead.updated_at,
    }


def lead_from_doc(doc: dict) -> CrmLead:
    return CrmLead(
        id=doc["_id"],
        lead_number=doc.get("lead_number", "") or "",
        name=doc.get("name", "") or "",
        contact_person=doc.get("contact_person", "") or "",
        phone=doc.get("phone", "") or "",
        alternate_phone=doc.get("alternate_phone", "") or "",
        email=doc.get("email", "") or "",
        address_line1=doc.get("address_line1", "") or "",
        address_line2=doc.get("address_line2", "") or "",
        area=doc.get("area", "") or "",
        city=doc.get("city", "") or "",
        state_code=doc.get("state_code", "") or "",
        pincode=doc.get("pincode", "") or "",
        gstin=doc.get("gstin", "") or "",
        source=doc.get("source", "") or "",
        interested_products=doc.get("interested_products", "") or "",
        estimated_value=float(doc.get("estimated_value") or 0),
        assigned_user_id=doc.get("assigned_user_id", "") or "",
        assigned_user_name=doc.get("assigned_user_name", "") or "",
        priority=doc.get("priority", "") or "",
        status=doc.get("status", "") or "",
        next_follow_up_at=doc.get("next_follow_up_at"),
        notes=doc.get("notes", "") or "",
        last_activity_at=doc.get("last_activity_at"),
        phone_normalized=doc.get("phone_normalized", "") or "",
        email_normalized=doc.get("email_normalized", "") or "",
        gstin_normalized=doc.get("gstin_normalized", "") or "",
        customer_id=doc.get("customer_id", "") or "",
        customer_name=doc.get("customer_name", "") or "",
        converted_at=doc.get("converted_at"),
        converted_by_id=doc.get("converted_by_id", "") or "",
        converted_by_name=doc.get("converted_by_name", "") or "",
        lost_reason=doc.get("lost_reason", "") or "",
        lost_at=doc.get("lost_at"),
        lost_by_id=doc.get("lost_by_id", "") or "",
        lost_by_name=doc.get("lost_by_name", "") or "",
        import_batch_id=doc.get("import_batch_id", "") or "",
        import_row_fingerprint=doc.get("import_row_fingerprint", "") or "",
        branch=doc.get("branch", "") or "",
        is_deleted=bool(doc.get("is_deleted", False)),
        deleted_at=doc.get("deleted_at"),
        created_by_id=doc.get("created_by_id", "") or "",
        created_by_name=doc.get("created_by_name", "") or "",
        updated_by_id=doc.get("updated_by_id", "") or "",
        updated_by_name=doc.get("updated_by_name", "") or "",
        created_at=doc.get("created_at", datetime.utcnow()),
        updated_at=doc.get("updated_at", datetime.utcnow()),
    )


def enquiry_to_doc(enquiry: CrmEnquiry) -> dict:
    return {
        "_id": enquiry.id,
        "enquiry_number": enquiry.enquiry_number,
        "lead_id": enquiry.lead_id,
        "customer_id": enquiry.customer_id,
        "party_name": enquiry.party_name,
        "enquiry_date": enquiry.enquiry_date,
        "source": enquiry.source,
        "product_interest": enquiry.product_interest,
        "description": enquiry.description,
        "expected_quantity": float(enquiry.expected_quantity or 0),
        "estimated_value": float(enquiry.estimated_value or 0),
        "priority": enquiry.priority,
        "assigned_user_id": enquiry.assigned_user_id,
        "assigned_user_name": enquiry.assigned_user_name,
        "expected_decision_at": enquiry.expected_decision_at,
        "next_follow_up_at": enquiry.next_follow_up_at,
        "status": enquiry.status,
        "lost_reason": enquiry.lost_reason,
        "notes": enquiry.notes,
        "attachment_ids": list(enquiry.attachment_ids or []),
        "quotation_id": enquiry.quotation_id,
        "sales_order_id": enquiry.sales_order_id,
        "branch": enquiry.branch,
        "is_deleted": enquiry.is_deleted,
        "deleted_at": enquiry.deleted_at,
        "created_by_id": enquiry.created_by_id,
        "created_by_name": enquiry.created_by_name,
        "updated_by_id": enquiry.updated_by_id,
        "updated_by_name": enquiry.updated_by_name,
        "created_at": enquiry.created_at,
        "updated_at": enquiry.updated_at,
    }


def enquiry_from_doc(doc: dict) -> CrmEnquiry:
    return CrmEnquiry(
        id=doc["_id"],
        enquiry_number=doc.get("enquiry_number", "") or "",
        lead_id=doc.get("lead_id", "") or "",
        customer_id=doc.get("customer_id", "") or "",
        party_name=doc.get("party_name", "") or "",
        enquiry_date=doc.get("enquiry_date"),
        source=doc.get("source", "") or "",
        product_interest=doc.get("product_interest", "") or "",
        description=doc.get("description", "") or "",
        expected_quantity=float(doc.get("expected_quantity") or 0),
        estimated_value=float(doc.get("estimated_value") or 0),
        priority=doc.get("priority", "") or "",
        assigned_user_id=doc.get("assigned_user_id", "") or "",
        assigned_user_name=doc.get("assigned_user_name", "") or "",
        expected_decision_at=doc.get("expected_decision_at"),
        next_follow_up_at=doc.get("next_follow_up_at"),
        status=doc.get("status", "") or "",
        lost_reason=doc.get("lost_reason", "") or "",
        notes=doc.get("notes", "") or "",
        attachment_ids=list(doc.get("attachment_ids") or []),
        quotation_id=doc.get("quotation_id", "") or "",
        sales_order_id=doc.get("sales_order_id", "") or "",
        branch=doc.get("branch", "") or "",
        is_deleted=bool(doc.get("is_deleted", False)),
        deleted_at=doc.get("deleted_at"),
        created_by_id=doc.get("created_by_id", "") or "",
        created_by_name=doc.get("created_by_name", "") or "",
        updated_by_id=doc.get("updated_by_id", "") or "",
        updated_by_name=doc.get("updated_by_name", "") or "",
        created_at=doc.get("created_at", datetime.utcnow()),
        updated_at=doc.get("updated_at", datetime.utcnow()),
    )


def activity_to_doc(activity: CrmActivity) -> dict:
    return {
        "_id": activity.id,
        "activity_type": activity.activity_type,
        "activity_type_key": activity.activity_type_key,
        "origin": activity.origin,
        "status": activity.status,
        "lead_id": activity.lead_id,
        "enquiry_id": activity.enquiry_id,
        "customer_id": activity.customer_id,
        "party_name": activity.party_name,
        "assigned_user_id": activity.assigned_user_id,
        "assigned_user_name": activity.assigned_user_name,
        "activity_at": activity.activity_at,
        "scheduled_at": activity.scheduled_at,
        "completed_at": activity.completed_at,
        "outcome": activity.outcome,
        "notes": activity.notes,
        "next_action": activity.next_action,
        "next_follow_up_at": activity.next_follow_up_at,
        "location": activity.location,
        "priority": activity.priority,
        "attachment_ids": list(activity.attachment_ids or []),
        "source_module": activity.source_module,
        "source_txn_type": activity.source_txn_type,
        "source_txn_id": activity.source_txn_id,
        "promised_amount": float(activity.promised_amount or 0),
        "promised_date": activity.promised_date,
        "cancel_reason": activity.cancel_reason,
        "branch": activity.branch,
        "is_deleted": activity.is_deleted,
        "deleted_at": activity.deleted_at,
        "created_by_id": activity.created_by_id,
        "created_by_name": activity.created_by_name,
        "updated_by_id": activity.updated_by_id,
        "updated_by_name": activity.updated_by_name,
        "created_at": activity.created_at,
        "updated_at": activity.updated_at,
    }


def activity_from_doc(doc: dict) -> CrmActivity:
    return CrmActivity(
        id=doc["_id"],
        activity_type=doc.get("activity_type", "") or "",
        activity_type_key=doc.get("activity_type_key", "") or "",
        origin=doc.get("origin", "") or "",
        status=doc.get("status", "") or "",
        lead_id=doc.get("lead_id", "") or "",
        enquiry_id=doc.get("enquiry_id", "") or "",
        customer_id=doc.get("customer_id", "") or "",
        party_name=doc.get("party_name", "") or "",
        assigned_user_id=doc.get("assigned_user_id", "") or "",
        assigned_user_name=doc.get("assigned_user_name", "") or "",
        activity_at=doc.get("activity_at"),
        scheduled_at=doc.get("scheduled_at"),
        due_at=doc.get("due_at"),
        completed_at=doc.get("completed_at"),
        outcome=doc.get("outcome", "") or "",
        notes=doc.get("notes", "") or "",
        next_action=doc.get("next_action", "") or "",
        next_follow_up_at=doc.get("next_follow_up_at"),
        location=doc.get("location", "") or "",
        priority=doc.get("priority", "") or "",
        attachment_ids=list(doc.get("attachment_ids") or []),
        source_module=doc.get("source_module", "") or "",
        source_txn_type=doc.get("source_txn_type", "") or "",
        source_txn_id=doc.get("source_txn_id", "") or "",
        promised_amount=float(doc.get("promised_amount") or 0),
        promised_date=doc.get("promised_date"),
        cancel_reason=doc.get("cancel_reason", "") or "",
        branch=doc.get("branch", "") or "",
        is_deleted=bool(doc.get("is_deleted", False)),
        deleted_at=doc.get("deleted_at"),
        created_by_id=doc.get("created_by_id", "") or "",
        created_by_name=doc.get("created_by_name", "") or "",
        updated_by_id=doc.get("updated_by_id", "") or "",
        updated_by_name=doc.get("updated_by_name", "") or "",
        created_at=doc.get("created_at", datetime.utcnow()),
        updated_at=doc.get("updated_at", datetime.utcnow()),
    )


def audit_to_doc(entry: CrmAuditEntry) -> dict:
    return {
        "_id": entry.id,
        "entity_type": entry.entity_type,
        "entity_id": entry.entity_id,
        "action": entry.action,
        "actor_id": entry.actor_id,
        "actor_name": entry.actor_name,
        "reason": entry.reason,
        "before": entry.before,
        "after": entry.after,
        "branch": entry.branch,
        "created_at": entry.created_at,
    }


def audit_from_doc(doc: dict) -> CrmAuditEntry:
    return CrmAuditEntry(
        id=doc["_id"],
        entity_type=doc.get("entity_type", "") or "",
        entity_id=doc.get("entity_id", "") or "",
        action=doc.get("action", "") or "",
        actor_id=doc.get("actor_id", "") or "",
        actor_name=doc.get("actor_name", "") or "",
        reason=doc.get("reason", "") or "",
        before=doc.get("before"),
        after=doc.get("after"),
        branch=doc.get("branch", "") or "",
        created_at=doc.get("created_at", datetime.utcnow()),
    )


def notification_to_doc(n: CrmNotification) -> dict:
    return {
        "_id": n.id,
        "recipient_id": n.recipient_id,
        "kind": n.kind,
        "title": n.title,
        "message": n.message,
        "ref_type": n.ref_type,
        "ref_id": n.ref_id,
        "state": n.state,
        "read_at": n.read_at,
        "dedupe_key": n.dedupe_key,
        "branch": n.branch,
        "created_at": n.created_at,
    }


def notification_from_doc(doc: dict) -> CrmNotification:
    return CrmNotification(
        id=doc["_id"],
        recipient_id=doc.get("recipient_id", "") or "",
        kind=doc.get("kind", "") or "",
        title=doc.get("title", "") or "",
        message=doc.get("message", "") or "",
        ref_type=doc.get("ref_type", "") or "",
        ref_id=doc.get("ref_id", "") or "",
        state=doc.get("state", "open") or "open",
        read_at=doc.get("read_at"),
        dedupe_key=doc.get("dedupe_key", "") or "",
        branch=doc.get("branch", "") or "",
        created_at=doc.get("created_at", datetime.utcnow()),
    )


def prefs_to_doc(prefs: CrmNotificationPreferences) -> dict:
    return {
        "_id": prefs.id,
        "user_id": prefs.user_id,
        "activity_due_today": prefs.activity_due_today,
        "upcoming_visits": prefs.upcoming_visits,
        "overdue_follow_ups": prefs.overdue_follow_ups,
        "lead_assigned": prefs.lead_assigned,
        "enquiry_reassigned": prefs.enquiry_reassigned,
        "payment_promises": prefs.payment_promises,
        "high_priority_idle": prefs.high_priority_idle,
        "payment_reminder_due": prefs.payment_reminder_due,
        "updated_at": prefs.updated_at,
    }


def prefs_from_doc(doc: dict) -> CrmNotificationPreferences:
    return CrmNotificationPreferences(
        id=doc["_id"],
        user_id=doc.get("user_id", "") or "",
        activity_due_today=bool(doc.get("activity_due_today", True)),
        upcoming_visits=bool(doc.get("upcoming_visits", True)),
        overdue_follow_ups=bool(doc.get("overdue_follow_ups", True)),
        lead_assigned=bool(doc.get("lead_assigned", True)),
        enquiry_reassigned=bool(doc.get("enquiry_reassigned", True)),
        payment_promises=bool(doc.get("payment_promises", True)),
        high_priority_idle=bool(doc.get("high_priority_idle", True)),
        payment_reminder_due=bool(doc.get("payment_reminder_due", True)),
        updated_at=doc.get("updated_at", datetime.utcnow()),
    )


def batch_to_doc(batch: CrmImportBatch) -> dict:
    return {
        "_id": batch.id,
        "entity_type": batch.entity_type,
        "source_filename": batch.source_filename,
        "file_hash": batch.file_hash,
        "imported_by_id": batch.imported_by_id,
        "imported_by_name": batch.imported_by_name,
        "status": batch.status,
        "total_rows": batch.total_rows,
        "created_count": batch.created_count,
        "updated_count": batch.updated_count,
        "skipped_count": batch.skipped_count,
        "failed_count": batch.failed_count,
        "linked_count": batch.linked_count,
        "row_outcomes": list(batch.row_outcomes or []),
        "error_summary": batch.error_summary,
        "branch": batch.branch,
        "created_at": batch.created_at,
        "completed_at": batch.completed_at,
    }


def batch_from_doc(doc: dict) -> CrmImportBatch:
    return CrmImportBatch(
        id=doc["_id"],
        entity_type=doc.get("entity_type", "leads") or "leads",
        source_filename=doc.get("source_filename", "") or "",
        file_hash=doc.get("file_hash", "") or "",
        imported_by_id=doc.get("imported_by_id", "") or "",
        imported_by_name=doc.get("imported_by_name", "") or "",
        status=doc.get("status", "") or "",
        total_rows=int(doc.get("total_rows") or 0),
        created_count=int(doc.get("created_count") or 0),
        updated_count=int(doc.get("updated_count") or 0),
        skipped_count=int(doc.get("skipped_count") or 0),
        failed_count=int(doc.get("failed_count") or 0),
        linked_count=int(doc.get("linked_count") or 0),
        row_outcomes=list(doc.get("row_outcomes") or []),
        error_summary=doc.get("error_summary", "") or "",
        branch=doc.get("branch", "") or "",
        created_at=doc.get("created_at", datetime.utcnow()),
        completed_at=doc.get("completed_at"),
    )


def settings_to_doc(settings: CrmSettings) -> dict:
    return {
        "_id": settings.id or CRM_SETTINGS_ID,
        "lead_sources": list(settings.lead_sources or []),
        "lead_statuses": list(settings.lead_statuses or []),
        "enquiry_statuses": list(settings.enquiry_statuses or []),
        "activity_types": list(settings.activity_types or []),
        "activity_outcomes": list(settings.activity_outcomes or []),
        "lost_reasons": list(settings.lost_reasons or []),
        "default_inactivity_days": int(settings.default_inactivity_days or 30),
        "default_follow_up_days": int(settings.default_follow_up_days or 3),
        "order_trigger_status": settings.order_trigger_status,
        "payment_trigger": settings.payment_trigger,
        "business_display_name": settings.business_display_name,
        "payment_reminder_template": settings.payment_reminder_template,
        "payment_reminder_due_offsets_days": list(
            settings.payment_reminder_due_offsets_days or []
        ),
        "updated_at": settings.updated_at,
        "updated_by_id": settings.updated_by_id,
        "updated_by_name": settings.updated_by_name,
    }


def settings_from_doc(doc: Optional[dict]) -> CrmSettings:
    if not doc:
        return CrmSettings()
    return CrmSettings(
        id=doc.get("_id", CRM_SETTINGS_ID),
        lead_sources=list(doc.get("lead_sources") or []),
        lead_statuses=list(doc.get("lead_statuses") or []),
        enquiry_statuses=list(doc.get("enquiry_statuses") or []),
        activity_types=list(doc.get("activity_types") or []),
        activity_outcomes=list(doc.get("activity_outcomes") or []),
        lost_reasons=list(doc.get("lost_reasons") or []),
        default_inactivity_days=int(doc.get("default_inactivity_days") or 30),
        default_follow_up_days=int(doc.get("default_follow_up_days") or 3),
        order_trigger_status=doc.get("order_trigger_status", "Confirmed") or "Confirmed",
        payment_trigger=doc.get("payment_trigger", "receipt_create") or "receipt_create",
        business_display_name=doc.get("business_display_name", "") or "",
        payment_reminder_template=doc.get("payment_reminder_template")
        or CrmSettings().payment_reminder_template,
        payment_reminder_due_offsets_days=list(
            doc.get("payment_reminder_due_offsets_days") or [0, 3, 7]
        ),
        updated_at=doc.get("updated_at", datetime.utcnow()),
        updated_by_id=doc.get("updated_by_id", "") or "",
        updated_by_name=doc.get("updated_by_name", "") or "",
    )


def not_deleted_filter(include_deleted: bool = False) -> Dict[str, Any]:
    if include_deleted:
        return {}
    return {"is_deleted": {"$ne": True}}
