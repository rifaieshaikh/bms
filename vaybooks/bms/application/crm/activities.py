"""CRM activity and automatic activity services."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import List, Optional

from vaybooks.bms.domain.crm.entities import CrmActivity, CrmAuditEntry
from vaybooks.bms.domain.crm.enums import (
    ActivityOrigin,
    ActivityStatus,
    AUTO_ACTIVITY_TYPE_KEYS,
)
from vaybooks.bms.domain.crm.services import activity_type_key
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.exceptions import ValidationError


class CrmActivityAppService:
    def __init__(
        self,
        activity_repo,
        settings_repo=None,
        audit_repo=None,
        lead_repo=None,
        user_service=None,
    ):
        self._activities = activity_repo
        self._settings = settings_repo
        self._audit = audit_repo
        self._leads = lead_repo
        self._users = user_service

    def _settings_obj(self):
        if self._settings:
            return self._settings.get()
        from vaybooks.bms.domain.crm.entities import CrmSettings

        return CrmSettings()

    def create_manual(
        self,
        *,
        activity_type: str,
        lead_id: str = "",
        enquiry_id: str = "",
        customer_id: str = "",
        party_name: str = "",
        assigned_user_id: str = "",
        assigned_user_name: str = "",
        activity_at: Optional[datetime] = None,
        scheduled_at: Optional[datetime] = None,
        due_at: Optional[datetime] = None,
        outcome: str = "",
        notes: str = "",
        next_action: str = "",
        next_follow_up_at: Optional[datetime] = None,
        location: str = "",
        location_id: str = "",
        location_name: str = "",
        priority: str = "Medium",
        promised_amount: float = 0.0,
        promised_date: Optional[datetime] = None,
        status: str = ActivityStatus.SCHEDULED.value,
        branch: str = "",
        actor_id: str = "",
        actor_name: str = "",
    ) -> CrmActivity:
        from vaybooks.bms.domain.shared.party_location import require_location_id

        if not activity_type:
            raise ValidationError("Activity type is required")
        if not (lead_id or enquiry_id or customer_id):
            raise ValidationError("Activity requires a lead, enquiry, or customer")
        location_id = require_location_id(location_id)
        settings = self._settings_obj()
        active_types = {
            item.get("label")
            for item in settings.activity_types
            if item.get("active", True)
        }
        if activity_type not in active_types:
            raise ValidationError("Unknown or inactive activity type")
        if status not in {item.value for item in ActivityStatus}:
            raise ValidationError("Invalid activity status")
        if assigned_user_id and self._users:
            loader = getattr(self._users, "get_user", None)
            if callable(loader) and loader(assigned_user_id) is None:
                raise ValidationError("Assigned user was not found")
        activity = CrmActivity(
            activity_type=activity_type,
            activity_type_key=activity_type_key(activity_type),
            origin=ActivityOrigin.MANUAL.value,
            status=status or ActivityStatus.SCHEDULED.value,
            lead_id=lead_id or "",
            enquiry_id=enquiry_id or "",
            customer_id=customer_id or "",
            party_name=party_name or "",
            assigned_user_id=assigned_user_id or "",
            assigned_user_name=assigned_user_name or "",
            activity_at=activity_at or utc_now(),
            scheduled_at=scheduled_at or activity_at or utc_now(),
            due_at=due_at,
            outcome=outcome or "",
            notes=notes or "",
            next_action=next_action or "",
            next_follow_up_at=next_follow_up_at,
            location=location or "",
            location_id=location_id,
            location_name=(location_name or "").strip(),
            priority=priority or "Medium",
            promised_amount=float(promised_amount or 0),
            promised_date=promised_date,
            branch=branch or "",
        )
        activity.touch(actor_id=actor_id, actor_name=actor_name, creating=True)
        saved = self._activities.save(activity)
        self._touch_lead_activity(saved)
        return saved

    def get_activity(self, activity_id: str) -> CrmActivity:
        activity = self._activities.find_by_id(activity_id)
        if not activity or activity.is_deleted:
            raise ValidationError("Activity not found")
        return activity

    def list_activities(self, **kwargs) -> List[CrmActivity]:
        return self._activities.list(**kwargs)

    def list_timeline(self, **kwargs) -> List[CrmActivity]:
        return self._activities.list_timeline(**kwargs)

    def update_activity(
        self,
        activity_id: str,
        *,
        actor_id: str = "",
        actor_name: str = "",
        allow_automatic: bool = False,
        **fields,
    ) -> CrmActivity:
        activity = self.get_activity(activity_id)
        if activity.is_automatic and not allow_automatic:
            raise ValidationError("Automatic activities are read-only")
        allowed = {
            "activity_type",
            "assigned_user_id",
            "assigned_user_name",
            "activity_at",
            "scheduled_at",
            "due_at",
            "outcome",
            "notes",
            "next_action",
            "next_follow_up_at",
            "location",
            "location_id",
            "location_name",
            "priority",
            "promised_amount",
            "promised_date",
        }
        for key, value in fields.items():
            if key in allowed and value is not None:
                setattr(activity, key, value)
        if "activity_type" in fields:
            activity.activity_type_key = activity_type_key(activity.activity_type)
        activity.touch(actor_id=actor_id, actor_name=actor_name)
        return self._activities.save(activity)

    def complete(
        self,
        activity_id: str,
        *,
        outcome: str = "",
        notes: str = "",
        next_action: str = "",
        next_follow_up_at: Optional[datetime] = None,
        actor_id: str = "",
        actor_name: str = "",
        allow_automatic: bool = False,
    ) -> CrmActivity:
        activity = self.get_activity(activity_id)
        if activity.is_automatic and not allow_automatic:
            raise ValidationError("Automatic activities cannot be completed manually")
        settings = self._settings_obj()
        if settings.outcome_required_for(activity.activity_type) and not (outcome or "").strip():
            raise ValidationError("Outcome is required to complete this activity")
        before = {"status": activity.status}
        activity.status = ActivityStatus.COMPLETED.value
        activity.completed_at = utc_now()
        activity.outcome = (outcome or activity.outcome or "").strip()
        if notes:
            activity.notes = notes
        if next_action:
            activity.next_action = next_action
        if next_follow_up_at is not None:
            activity.next_follow_up_at = next_follow_up_at
        activity.touch(actor_id=actor_id, actor_name=actor_name)
        saved = self._activities.save(activity)
        if self._audit:
            self._audit.save(
                CrmAuditEntry(
                    entity_type="crm_activity",
                    entity_id=saved.id,
                    action="complete",
                    actor_id=actor_id,
                    actor_name=actor_name,
                    before=before,
                    after={"status": saved.status, "outcome": saved.outcome},
                )
            )
        self._touch_lead_activity(saved)
        return saved

    def reschedule(
        self,
        activity_id: str,
        scheduled_at: datetime,
        *,
        actor_id: str = "",
        actor_name: str = "",
        reason: str = "",
        allow_automatic: bool = False,
    ) -> CrmActivity:
        activity = self.get_activity(activity_id)
        if activity.is_automatic and not allow_automatic:
            raise ValidationError("Automatic activities are read-only")
        before = {"scheduled_at": str(activity.scheduled_at)}
        activity.scheduled_at = scheduled_at
        activity.touch(actor_id=actor_id, actor_name=actor_name)
        saved = self._activities.save(activity)
        if self._audit:
            self._audit.save(
                CrmAuditEntry(
                    entity_type="crm_activity",
                    entity_id=saved.id,
                    action="reschedule",
                    actor_id=actor_id,
                    actor_name=actor_name,
                    reason=reason,
                    before=before,
                    after={"scheduled_at": str(saved.scheduled_at)},
                )
            )
        return saved

    def cancel(
        self,
        activity_id: str,
        *,
        reason: str = "",
        actor_id: str = "",
        actor_name: str = "",
        allow_automatic: bool = False,
    ) -> CrmActivity:
        activity = self.get_activity(activity_id)
        if activity.is_automatic and not allow_automatic:
            raise ValidationError("Automatic activities are read-only")
        if not (reason or "").strip():
            raise ValidationError("Cancellation reason is required")
        activity.status = ActivityStatus.CANCELLED.value
        activity.cancel_reason = reason or ""
        activity.touch(actor_id=actor_id, actor_name=actor_name)
        return self._activities.save(activity)

    def _touch_lead_activity(self, activity: CrmActivity) -> None:
        if not self._leads or not activity.lead_id:
            return
        lead = self._leads.find_by_id(activity.lead_id)
        if not lead:
            return
        lead.last_activity_at = utc_now()
        if activity.next_follow_up_at:
            lead.next_follow_up_at = activity.next_follow_up_at
        self._leads.save(lead)


class CrmAutoActivityService:
    """Idempotent automatic CRM activities from sales/accounting events."""

    def __init__(self, activity_repo, settings_repo=None, lead_repo=None):
        self._activities = activity_repo
        self._settings = settings_repo
        self._leads = lead_repo

    def _order_trigger(self) -> str:
        if self._settings:
            return self._settings.get().order_trigger_status or "Confirmed"
        return "Confirmed"

    def record_source_event(
        self,
        *,
        event_type: str,
        source_module: str,
        source_type: str,
        source_id: str,
        customer_id: str = "",
        occurred_at=None,
        status: str = "",
        amount: float = 0.0,
        **kwargs,
    ) -> Optional[CrmActivity]:
        """Adapter used by Sales and Accounting application services."""
        if event_type == "source_reversed":
            return self.reverse_event(
                source_module=source_module,
                source_txn_type=source_type,
                source_txn_id=source_id,
                actor_id=kwargs.get("actor_id", ""),
                actor_name=kwargs.get("actor_name", ""),
            )
        type_key = {
            "quotation_confirmed": "quotation_sent",
        }.get(event_type, event_type)
        if type_key == "order_placed" and status and status != self._order_trigger():
            return None
        details = []
        if status:
            details.append(f"Status: {status}")
        if amount:
            details.append(f"Amount: {float(amount):.2f}")
        activity = self.record_event(
            type_key=type_key,
            source_module=source_module,
            source_txn_type=source_type,
            source_txn_id=source_id,
            customer_id=customer_id,
            party_name=kwargs.get("party_name", ""),
            assigned_user_id=kwargs.get("assigned_user_id", ""),
            assigned_user_name=kwargs.get("assigned_user_name", ""),
            notes="; ".join(details),
            branch=kwargs.get("branch", ""),
            actor_id=kwargs.get("actor_id", ""),
            actor_name=kwargs.get("actor_name", ""),
        )
        if activity is not None:
            # Re-post/update refreshes the one source-linked activity rather
            # than creating a duplicate, including after a prior reversal.
            activity.status = ActivityStatus.COMPLETED.value
            if details:
                activity.notes = "; ".join(details)
            if occurred_at is not None:
                if isinstance(occurred_at, date) and not isinstance(
                    occurred_at, datetime
                ):
                    occurred_at = datetime.combine(occurred_at, time.min)
                activity.activity_at = occurred_at
                activity.completed_at = occurred_at
            activity.updated_at = utc_now()
            activity = self._activities.save(activity)
        return activity

    def record_event(
        self,
        *,
        type_key: str,
        source_module: str,
        source_txn_type: str,
        source_txn_id: str,
        lead_id: str = "",
        enquiry_id: str = "",
        customer_id: str = "",
        party_name: str = "",
        assigned_user_id: str = "",
        assigned_user_name: str = "",
        notes: str = "",
        branch: str = "",
        actor_id: str = "",
        actor_name: str = "",
        activity_label: str = "",
    ) -> Optional[CrmActivity]:
        label = activity_label or AUTO_ACTIVITY_TYPE_KEYS.get(type_key, type_key)
        key = activity_type_key(label)
        existing = self._activities.find_by_source(
            source_module, source_txn_type, source_txn_id, key
        )
        if existing:
            return existing
        activity = CrmActivity(
            activity_type=label,
            activity_type_key=key,
            origin=ActivityOrigin.AUTOMATIC.value,
            status=ActivityStatus.COMPLETED.value,
            lead_id=lead_id or "",
            enquiry_id=enquiry_id or "",
            customer_id=customer_id or "",
            party_name=party_name or "",
            assigned_user_id=assigned_user_id or "",
            assigned_user_name=assigned_user_name or "",
            activity_at=utc_now(),
            completed_at=utc_now(),
            notes=notes or "",
            source_module=source_module,
            source_txn_type=source_txn_type,
            source_txn_id=source_txn_id,
            branch=branch or "",
        )
        activity.touch(actor_id=actor_id, actor_name=actor_name, creating=True)
        return self._activities.save(activity)

    def reverse_event(
        self,
        *,
        source_module: str,
        source_txn_type: str,
        source_txn_id: str,
        type_key: str = "",
        activity_label: str = "",
        actor_id: str = "",
        actor_name: str = "",
    ) -> Optional[CrmActivity]:
        label = activity_label or AUTO_ACTIVITY_TYPE_KEYS.get(type_key, type_key)
        key = activity_type_key(label) if label else ""
        if key:
            activity = self._activities.find_by_source(
                source_module, source_txn_type, source_txn_id, key
            )
            if activity:
                activity.status = ActivityStatus.REVERSED.value
                activity.touch(actor_id=actor_id, actor_name=actor_name)
                return self._activities.save(activity)
            return None
        # Reverse all auto activities for the source txn
        found = None
        for act in self._activities.list(limit=500):
            if (
                act.source_module == source_module
                and act.source_txn_type == source_txn_type
                and act.source_txn_id == source_txn_id
                and act.origin == ActivityOrigin.AUTOMATIC.value
            ):
                act.status = ActivityStatus.REVERSED.value
                act.touch(actor_id=actor_id, actor_name=actor_name)
                found = self._activities.save(act)
        return found

    def on_quotation_created(self, quotation_id: str, **kwargs) -> Optional[CrmActivity]:
        return self.record_event(
            type_key="quotation_created",
            source_module="sales",
            source_txn_type="quotation",
            source_txn_id=quotation_id,
            **kwargs,
        )

    def on_quotation_sent(self, quotation_id: str, **kwargs) -> Optional[CrmActivity]:
        return self.record_event(
            type_key="quotation_sent",
            source_module="sales",
            source_txn_type="quotation",
            source_txn_id=quotation_id,
            **kwargs,
        )

    def on_order_confirmed(
        self, sales_order_id: str, *, status: str = "", **kwargs
    ) -> Optional[CrmActivity]:
        trigger = self._order_trigger()
        if status and status != trigger:
            return None
        return self.record_event(
            type_key="order_placed",
            source_module="sales",
            source_txn_type="sales_order",
            source_txn_id=sales_order_id,
            **kwargs,
        )

    def on_invoice_posted(self, voucher_id: str, **kwargs) -> Optional[CrmActivity]:
        return self.record_event(
            type_key="invoice_created",
            source_module="finance",
            source_txn_type="sales_invoice",
            source_txn_id=voucher_id,
            **kwargs,
        )

    def on_receipt_posted(self, voucher_id: str, **kwargs) -> Optional[CrmActivity]:
        return self.record_event(
            type_key="payment_received",
            source_module="finance",
            source_txn_type="receipt",
            source_txn_id=voucher_id,
            **kwargs,
        )

    def on_receipt_voided(self, voucher_id: str, **kwargs) -> Optional[CrmActivity]:
        return self.reverse_event(
            source_module="finance",
            source_txn_type="receipt",
            source_txn_id=voucher_id,
            type_key="payment_received",
            **kwargs,
        )

    def on_order_cancelled(self, sales_order_id: str, **kwargs) -> Optional[CrmActivity]:
        return self.reverse_event(
            source_module="sales",
            source_txn_type="sales_order",
            source_txn_id=sales_order_id,
            type_key="order_placed",
            **kwargs,
        )
