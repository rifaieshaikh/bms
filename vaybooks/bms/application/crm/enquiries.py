"""CRM enquiry application service."""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from vaybooks.bms.domain.crm.entities import CrmActivity, CrmAuditEntry, CrmEnquiry
from vaybooks.bms.domain.crm.enums import (
    ActivityOrigin,
    ActivityStatus,
    AUTO_ACTIVITY_TYPE_KEYS,
    EnquiryStatus,
    NotificationKind,
)
from vaybooks.bms.domain.crm.services import activity_type_key
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.exceptions import ValidationError


class CrmEnquiryAppService:
    def __init__(
        self,
        enquiry_repo,
        audit_repo=None,
        activity_repo=None,
        lead_repo=None,
        counter_repo=None,
        settings_repo=None,
        user_service=None,
        sales_service=None,
        notification_service=None,
    ):
        self._enquiries = enquiry_repo
        self._audit = audit_repo
        self._activities = activity_repo
        self._leads = lead_repo
        self._counters = counter_repo
        self._settings = settings_repo
        self._users = user_service
        self._sales = sales_service
        self._notifications = notification_service

    def set_sales_service(self, sales_service) -> None:
        self._sales = sales_service

    def _validate_status(self, status: str) -> None:
        if not self._settings or not status:
            return
        allowed = {
            item.get("label")
            for item in self._settings.get().enquiry_statuses
            if item.get("active", True)
        }
        if status not in allowed:
            raise ValidationError(f"Unknown or inactive enquiry status: {status}")

    def _validate_assignee(self, user_id: str) -> None:
        if not user_id or not self._users:
            return
        loader = getattr(self._users, "get_user", None)
        if callable(loader) and loader(user_id) is None:
            raise ValidationError("Assigned sales representative was not found")

    def _write_audit(self, **kwargs) -> None:
        if not self._audit:
            return
        self._audit.save(CrmAuditEntry(entity_type="crm_enquiry", **kwargs))

    def _next_number(self) -> str:
        if self._counters:
            try:
                return self._counters.next("crm_enquiry_number")
            except Exception:
                pass
        return f"ENQ-{utc_now().strftime('%Y%m%d%H%M%S')}"

    def create_enquiry(
        self,
        *,
        lead_id: str = "",
        customer_id: str = "",
        party_name: str = "",
        source: str = "",
        product_interest: str = "",
        description: str = "",
        expected_quantity: float = 0.0,
        estimated_value: float = 0.0,
        priority: str = "Medium",
        assigned_user_id: str = "",
        assigned_user_name: str = "",
        expected_decision_at=None,
        next_follow_up_at=None,
        notes: str = "",
        branch: str = "",
        actor_id: str = "",
        actor_name: str = "",
    ) -> CrmEnquiry:
        if not lead_id and not customer_id:
            raise ValidationError("Enquiry requires a lead or customer")
        self._validate_assignee(assigned_user_id)
        if lead_id and self._leads and not party_name:
            lead = self._leads.find_by_id(lead_id)
            if lead:
                party_name = lead.name
                if not assigned_user_id:
                    assigned_user_id = lead.assigned_user_id
                    assigned_user_name = lead.assigned_user_name
                if not customer_id:
                    customer_id = lead.customer_id
        enquiry = CrmEnquiry(
            enquiry_number=self._next_number(),
            lead_id=lead_id or "",
            customer_id=customer_id or "",
            party_name=(party_name or "").strip(),
            enquiry_date=utc_now(),
            source=(source or "").strip(),
            product_interest=(product_interest or "").strip(),
            description=(description or "").strip(),
            expected_quantity=float(expected_quantity or 0),
            estimated_value=float(estimated_value or 0),
            priority=priority or "Medium",
            assigned_user_id=assigned_user_id or "",
            assigned_user_name=assigned_user_name or "",
            expected_decision_at=expected_decision_at,
            next_follow_up_at=next_follow_up_at,
            status=EnquiryStatus.OPEN.value,
            notes=notes or "",
            branch=branch or "",
        )
        if assigned_user_id:
            enquiry.status = EnquiryStatus.ASSIGNED.value
        enquiry.touch(actor_id=actor_id, actor_name=actor_name, creating=True)
        saved = self._enquiries.save(enquiry)
        self._write_audit(
            entity_id=saved.id,
            action="create",
            actor_id=actor_id,
            actor_name=actor_name,
            after={"status": saved.status},
        )
        self._auto_enquiry_created(saved, actor_id=actor_id, actor_name=actor_name)
        if self._notifications and saved.assigned_user_id:
            prefs = self._notifications.get_preferences(saved.assigned_user_id)
            if prefs.enquiry_reassigned:
                self._notifications.create(
                    recipient_id=saved.assigned_user_id,
                    kind=NotificationKind.ENQUIRY_REASSIGNED,
                    title="Enquiry assigned",
                    message=saved.party_name or saved.enquiry_number,
                    ref_type="crm_enquiry",
                    ref_id=saved.id,
                    branch=saved.branch,
                )
        return saved

    def get_enquiry(self, enquiry_id: str) -> CrmEnquiry:
        enquiry = self._enquiries.find_by_id(enquiry_id)
        if not enquiry or enquiry.is_deleted:
            raise ValidationError("Enquiry not found")
        return enquiry

    def list_enquiries(self, **kwargs) -> List[CrmEnquiry]:
        return self._enquiries.list(**kwargs)

    def update_enquiry(
        self, enquiry_id: str, *, actor_id: str = "", actor_name: str = "", **fields
    ) -> CrmEnquiry:
        enquiry = self.get_enquiry(enquiry_id)
        allowed = {
            "source",
            "product_interest",
            "description",
            "expected_quantity",
            "estimated_value",
            "priority",
            "expected_decision_at",
            "next_follow_up_at",
            "notes",
            "party_name",
            "branch",
        }
        for key, value in fields.items():
            if key in allowed and value is not None:
                setattr(enquiry, key, value)
        enquiry.touch(actor_id=actor_id, actor_name=actor_name)
        return self._enquiries.save(enquiry)

    def assign_enquiry(
        self,
        enquiry_id: str,
        assigned_user_id: str,
        assigned_user_name: str = "",
        *,
        actor_id: str = "",
        actor_name: str = "",
    ) -> CrmEnquiry:
        enquiry = self.get_enquiry(enquiry_id)
        self._validate_assignee(assigned_user_id)
        before = {"assigned_user_id": enquiry.assigned_user_id}
        enquiry.assigned_user_id = assigned_user_id
        enquiry.assigned_user_name = assigned_user_name
        if enquiry.status == EnquiryStatus.OPEN.value:
            enquiry.status = EnquiryStatus.ASSIGNED.value
        enquiry.touch(actor_id=actor_id, actor_name=actor_name)
        saved = self._enquiries.save(enquiry)
        self._write_audit(
            entity_id=saved.id,
            action="assign",
            actor_id=actor_id,
            actor_name=actor_name,
            before=before,
            after={"assigned_user_id": saved.assigned_user_id},
        )
        if self._notifications and saved.assigned_user_id:
            prefs = self._notifications.get_preferences(saved.assigned_user_id)
            if prefs.enquiry_reassigned:
                self._notifications.create(
                    recipient_id=saved.assigned_user_id,
                    kind=NotificationKind.ENQUIRY_REASSIGNED,
                    title="Enquiry assigned",
                    message=saved.party_name or saved.enquiry_number,
                    ref_type="crm_enquiry",
                    ref_id=saved.id,
                    branch=saved.branch,
                )
        return saved

    def update_status(
        self,
        enquiry_id: str,
        status: str,
        *,
        lost_reason: str = "",
        actor_id: str = "",
        actor_name: str = "",
    ) -> CrmEnquiry:
        enquiry = self.get_enquiry(enquiry_id)
        self._validate_status(status)
        before = {"status": enquiry.status}
        enquiry.status = status
        if lost_reason:
            enquiry.lost_reason = lost_reason
        enquiry.touch(actor_id=actor_id, actor_name=actor_name)
        saved = self._enquiries.save(enquiry)
        self._write_audit(
            entity_id=saved.id,
            action="status_change",
            actor_id=actor_id,
            actor_name=actor_name,
            before=before,
            after={"status": saved.status},
            reason=lost_reason,
        )
        return saved

    def link_quotation(
        self, enquiry_id: str, quotation_id: str, *, actor_id: str = "", actor_name: str = ""
    ) -> CrmEnquiry:
        enquiry = self.get_enquiry(enquiry_id)
        enquiry.quotation_id = quotation_id
        if enquiry.status in {
            EnquiryStatus.OPEN.value,
            EnquiryStatus.ASSIGNED.value,
            EnquiryStatus.IN_PROGRESS.value,
            EnquiryStatus.QUOTATION_REQUIRED.value,
        }:
            enquiry.status = EnquiryStatus.QUOTATION_SENT.value
        enquiry.touch(actor_id=actor_id, actor_name=actor_name)
        return self._enquiries.save(enquiry)

    def link_sales_order(
        self, enquiry_id: str, sales_order_id: str, *, actor_id: str = "", actor_name: str = ""
    ) -> CrmEnquiry:
        enquiry = self.get_enquiry(enquiry_id)
        enquiry.sales_order_id = sales_order_id
        enquiry.status = EnquiryStatus.WON.value
        enquiry.touch(actor_id=actor_id, actor_name=actor_name)
        return self._enquiries.save(enquiry)

    def create_quotation_from_enquiry(
        self,
        enquiry_id: str,
        *,
        lines: list[dict],
        quotation_date: Optional[date] = None,
        valid_until: Optional[date] = None,
        notes: str = "",
        actor_id: str = "",
        actor_name: str = "",
    ):
        enquiry = self.get_enquiry(enquiry_id)
        if not self._sales:
            raise ValidationError("Sales service is not configured")
        if not enquiry.customer_id:
            raise ValidationError("Convert or link the lead to a customer first")
        quotation = self._sales.create_quotation(
            customer_id=enquiry.customer_id,
            quotation_date=quotation_date or date.today(),
            lines=lines,
            valid_until=valid_until,
            notes=notes or enquiry.notes,
        )
        self.link_quotation(
            enquiry.id,
            quotation.id,
            actor_id=actor_id,
            actor_name=actor_name,
        )
        return quotation

    def convert_to_order(
        self,
        enquiry_id: str,
        *,
        lines: Optional[list[dict]] = None,
        order_date: Optional[date] = None,
        expected_date: Optional[date] = None,
        actor_id: str = "",
        actor_name: str = "",
    ):
        enquiry = self.get_enquiry(enquiry_id)
        if not self._sales:
            raise ValidationError("Sales service is not configured")
        if enquiry.quotation_id:
            order = self._sales.convert_quotation_to_sales_order(
                enquiry.quotation_id,
                order_date=order_date,
                expected_date=expected_date,
            )
        else:
            if not enquiry.customer_id:
                raise ValidationError("Enquiry is not linked to a customer")
            if not lines:
                raise ValidationError("Order lines are required")
            order = self._sales.create_sales_order(
                customer_id=enquiry.customer_id,
                order_date=order_date or date.today(),
                expected_date=expected_date,
                lines=lines,
                notes=enquiry.notes,
            )
        self.link_sales_order(
            enquiry.id,
            order.id,
            actor_id=actor_id,
            actor_name=actor_name,
        )
        return order

    def close_enquiry(
        self, enquiry_id: str, *, actor_id: str = "", actor_name: str = ""
    ) -> CrmEnquiry:
        return self.update_status(
            enquiry_id, EnquiryStatus.CLOSED.value, actor_id=actor_id, actor_name=actor_name
        )

    def reopen_enquiry(
        self, enquiry_id: str, *, actor_id: str = "", actor_name: str = ""
    ) -> CrmEnquiry:
        return self.update_status(
            enquiry_id, EnquiryStatus.OPEN.value, actor_id=actor_id, actor_name=actor_name
        )

    def soft_delete(
        self, enquiry_id: str, *, actor_id: str = "", actor_name: str = ""
    ) -> CrmEnquiry:
        enquiry = self.get_enquiry(enquiry_id)
        enquiry.soft_delete(actor_id=actor_id, actor_name=actor_name)
        return self._enquiries.save(enquiry)

    def _auto_enquiry_created(
        self, enquiry: CrmEnquiry, *, actor_id: str = "", actor_name: str = ""
    ) -> None:
        if not self._activities:
            return
        label = AUTO_ACTIVITY_TYPE_KEYS["enquiry_created"]
        key = activity_type_key(label)
        existing = self._activities.find_by_source("crm", "enquiry", enquiry.id, key)
        if existing:
            return
        activity = CrmActivity(
            activity_type=label,
            activity_type_key=key,
            origin=ActivityOrigin.AUTOMATIC.value,
            status=ActivityStatus.COMPLETED.value,
            lead_id=enquiry.lead_id,
            enquiry_id=enquiry.id,
            customer_id=enquiry.customer_id,
            party_name=enquiry.party_name,
            assigned_user_id=enquiry.assigned_user_id,
            assigned_user_name=enquiry.assigned_user_name,
            activity_at=utc_now(),
            completed_at=utc_now(),
            source_module="crm",
            source_txn_type="enquiry",
            source_txn_id=enquiry.id,
            branch=enquiry.branch,
        )
        activity.touch(actor_id=actor_id, actor_name=actor_name, creating=True)
        self._activities.save(activity)
