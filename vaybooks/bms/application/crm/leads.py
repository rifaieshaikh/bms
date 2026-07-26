"""CRM lead application service."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from vaybooks.bms.domain.crm.entities import (
    CrmActivity,
    CrmAuditEntry,
    CrmLead,
    CrmNotification,
    LeadDuplicateMatch,
)
from vaybooks.bms.domain.crm.enums import (
    ActivityOrigin,
    ActivityStatus,
    AUTO_ACTIVITY_TYPE_KEYS,
    LeadStatus,
    NotificationKind,
)
from vaybooks.bms.domain.crm.services import (
    activity_type_key,
    normalize_email,
    normalize_gstin_optional,
    normalize_phone_optional,
    optional_float,
)
from vaybooks.bms.domain.parties.customers.entities import CustomerInput
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import PartyRegistrationType
from vaybooks.bms.domain.shared.exceptions import ValidationError


class CrmLeadAppService:
    def __init__(
        self,
        lead_repo,
        audit_repo=None,
        activity_repo=None,
        notification_repo=None,
        notification_service=None,
        customer_service=None,
        counter_repo=None,
        settings_repo=None,
        user_service=None,
        enquiry_repo=None,
    ):
        self._leads = lead_repo
        self._audit = audit_repo
        self._activities = activity_repo
        self._notifications = notification_repo
        self._notification_service = notification_service
        self._customers = customer_service
        self._counters = counter_repo
        self._settings = settings_repo
        self._users = user_service
        self._enquiries = enquiry_repo

    def _actor(self, actor_id: str = "", actor_name: str = "") -> Dict[str, str]:
        return {"actor_id": actor_id or "", "actor_name": actor_name or ""}

    def _write_audit(
        self,
        *,
        entity_id: str,
        action: str,
        actor_id: str = "",
        actor_name: str = "",
        reason: str = "",
        before: Optional[dict] = None,
        after: Optional[dict] = None,
        branch: str = "",
    ) -> None:
        if not self._audit:
            return
        self._audit.save(
            CrmAuditEntry(
                entity_type="crm_lead",
                entity_id=entity_id,
                action=action,
                actor_id=actor_id,
                actor_name=actor_name,
                reason=reason,
                before=before,
                after=after,
                branch=branch,
            )
        )

    def _apply_normalized(self, lead: CrmLead) -> None:
        lead.phone_normalized = normalize_phone_optional(lead.phone) if lead.phone else ""
        lead.email_normalized = normalize_email(lead.email)
        lead.gstin_normalized = (
            normalize_gstin_optional(lead.gstin) if lead.gstin else ""
        )

    def _next_lead_number(self) -> str:
        if self._counters:
            try:
                return self._counters.next("crm_lead_number")
            except Exception:
                pass
        return f"LD-{utc_now().strftime('%Y%m%d%H%M%S')}"

    def _validate_catalogs(
        self,
        *,
        source: str = "",
        status: str = "",
        assigned_user_id: str = "",
    ) -> None:
        if self._settings:
            settings = self._settings.get()
            sources = {
                item.get("label")
                for item in settings.lead_sources
                if item.get("active", True)
            }
            statuses = {
                item.get("label")
                for item in settings.lead_statuses
                if item.get("active", True)
            }
            if source and source not in sources:
                raise ValidationError(f"Unknown or inactive lead source: {source}")
            if status and status not in statuses:
                raise ValidationError(f"Unknown or inactive lead status: {status}")
        if assigned_user_id and self._users:
            loader = getattr(self._users, "get_user", None)
            if callable(loader) and loader(assigned_user_id) is None:
                raise ValidationError("Assigned sales representative was not found")

    def detect_duplicates(
        self,
        *,
        phone: str = "",
        email: str = "",
        gstin: str = "",
        name: str = "",
        exclude_lead_id: str = "",
    ) -> LeadDuplicateMatch:
        match = LeadDuplicateMatch()
        phone_n = normalize_phone_optional(phone) if phone else ""
        email_n = normalize_email(email)
        gstin_n = normalize_gstin_optional(gstin) if gstin else ""

        if phone_n:
            existing = self._leads.find_by_phone_normalized(phone_n)
            if existing and existing.id != exclude_lead_id:
                match.lead = existing
                match.match_fields.append("phone")
        if email_n and not match.lead:
            existing = self._leads.find_by_email_normalized(email_n)
            if existing and existing.id != exclude_lead_id:
                match.lead = existing
                match.match_fields.append("email")
        if gstin_n and not match.lead:
            existing = self._leads.find_by_gstin_normalized(gstin_n)
            if existing and existing.id != exclude_lead_id:
                match.lead = existing
                match.match_fields.append("gstin")

        if self._customers:
            customer = None
            if phone_n:
                customer = self._customers.lookup_customer_by_phone(phone_n)
            if not customer and gstin_n and hasattr(self._customers, "_customer_repo"):
                customer = self._customers._customer_repo.find_by_gstin(gstin_n)
            if not customer:
                try:
                    candidates = self._customers.list_all_customers()
                except Exception:
                    candidates = []
                name_n = (name or "").strip().lower()
                for candidate in candidates:
                    candidate_email = normalize_email(
                        getattr(candidate, "email", "") or ""
                    )
                    candidate_name = (
                        getattr(candidate, "customer_name", "") or ""
                    ).strip().lower()
                    if email_n and candidate_email == email_n:
                        customer = candidate
                        match.match_fields.append("email")
                        break
                    if name_n and candidate_name == name_n:
                        customer = candidate
                        match.match_fields.append("name")
                        break
            if customer:
                match.customer_id = customer.id
                match.customer_name = customer.customer_name
                if "customer" not in match.match_fields:
                    match.match_fields.append("customer")
        return match

    def create_lead(
        self,
        *,
        name: str,
        phone: str = "",
        contact_person: str = "",
        alternate_phone: str = "",
        email: str = "",
        address_line1: str = "",
        address_line2: str = "",
        area: str = "",
        city: str = "",
        state_code: str = "",
        pincode: str = "",
        gstin: str = "",
        source: str = "",
        interested_products: str = "",
        estimated_value: float = 0.0,
        assigned_user_id: str = "",
        assigned_user_name: str = "",
        priority: str = "Medium",
        status: str = LeadStatus.NEW.value,
        next_follow_up_at=None,
        notes: str = "",
        branch: str = "",
        import_batch_id: str = "",
        import_row_fingerprint: str = "",
        actor_id: str = "",
        actor_name: str = "",
        allow_duplicate: bool = False,
    ) -> CrmLead:
        name = (name or "").strip()
        if not name:
            raise ValidationError("Lead name is required")
        self._validate_catalogs(
            source=(source or "").strip(),
            status=status or LeadStatus.NEW.value,
            assigned_user_id=assigned_user_id,
        )
        if not allow_duplicate:
            dup = self.detect_duplicates(
                phone=phone, email=email, gstin=gstin, name=name
            )
            if dup.lead:
                raise ValidationError(
                    f"Duplicate lead found ({', '.join(dup.match_fields)})"
                )

        lead = CrmLead(
            lead_number=self._next_lead_number(),
            name=name,
            phone=(phone or "").strip(),
            contact_person=(contact_person or "").strip(),
            alternate_phone=(alternate_phone or "").strip(),
            email=(email or "").strip(),
            address_line1=(address_line1 or "").strip(),
            address_line2=(address_line2 or "").strip(),
            area=(area or "").strip(),
            city=(city or "").strip(),
            state_code=(state_code or "").strip(),
            pincode=(pincode or "").strip(),
            gstin=(gstin or "").strip().upper(),
            source=(source or "").strip(),
            interested_products=(interested_products or "").strip(),
            estimated_value=optional_float(estimated_value),
            assigned_user_id=assigned_user_id or "",
            assigned_user_name=assigned_user_name or "",
            priority=priority or "Medium",
            status=status or LeadStatus.NEW.value,
            next_follow_up_at=next_follow_up_at,
            notes=notes or "",
            branch=branch or "",
            import_batch_id=import_batch_id or "",
            import_row_fingerprint=import_row_fingerprint or "",
        )
        self._apply_normalized(lead)
        lead.touch(actor_id=actor_id, actor_name=actor_name, creating=True)
        saved = self._leads.save(lead)
        self._write_audit(
            entity_id=saved.id,
            action="create",
            actor_id=actor_id,
            actor_name=actor_name,
            after={"status": saved.status, "name": saved.name},
            branch=saved.branch,
        )
        if saved.assigned_user_id:
            self._notify_assignment(saved, actor_id=actor_id, actor_name=actor_name)
        return saved

    def update_lead(self, lead_id: str, *, actor_id: str = "", actor_name: str = "", **fields) -> CrmLead:
        lead = self.get_lead(lead_id)
        before = {"status": lead.status, "assigned_user_id": lead.assigned_user_id}
        allowed = {
            "name",
            "phone",
            "contact_person",
            "alternate_phone",
            "email",
            "address_line1",
            "address_line2",
            "area",
            "city",
            "state_code",
            "pincode",
            "gstin",
            "source",
            "interested_products",
            "estimated_value",
            "priority",
            "next_follow_up_at",
            "notes",
            "branch",
        }
        for key, value in fields.items():
            if key in allowed and value is not None:
                setattr(lead, key, value)
        if "name" in fields and not (lead.name or "").strip():
            raise ValidationError("Lead name is required")
        self._validate_catalogs(source=lead.source, status=lead.status)
        self._apply_normalized(lead)
        lead.touch(actor_id=actor_id, actor_name=actor_name)
        saved = self._leads.save(lead)
        self._write_audit(
            entity_id=saved.id,
            action="update",
            actor_id=actor_id,
            actor_name=actor_name,
            before=before,
            after={"status": saved.status, "assigned_user_id": saved.assigned_user_id},
        )
        return saved

    def get_lead(self, lead_id: str) -> CrmLead:
        lead = self._leads.find_by_id(lead_id)
        if not lead or lead.is_deleted:
            raise ValidationError("Lead not found")
        return lead

    def list_leads(self, **kwargs) -> List[CrmLead]:
        return self._leads.list(**kwargs)

    def soft_delete_lead(self, lead_id: str, *, actor_id: str = "", actor_name: str = "") -> CrmLead:
        lead = self.get_lead(lead_id)
        lead.soft_delete(actor_id=actor_id, actor_name=actor_name)
        return self._leads.save(lead)

    def assign_lead(
        self,
        lead_id: str,
        assigned_user_id: str,
        assigned_user_name: str = "",
        *,
        actor_id: str = "",
        actor_name: str = "",
    ) -> CrmLead:
        lead = self.get_lead(lead_id)
        self._validate_catalogs(assigned_user_id=assigned_user_id)
        before = {
            "assigned_user_id": lead.assigned_user_id,
            "assigned_user_name": lead.assigned_user_name,
        }
        lead.assigned_user_id = assigned_user_id or ""
        lead.assigned_user_name = assigned_user_name or ""
        lead.touch(actor_id=actor_id, actor_name=actor_name)
        saved = self._leads.save(lead)
        self._write_audit(
            entity_id=saved.id,
            action="assign",
            actor_id=actor_id,
            actor_name=actor_name,
            before=before,
            after={
                "assigned_user_id": saved.assigned_user_id,
                "assigned_user_name": saved.assigned_user_name,
            },
        )
        self._record_auto_activity(
            lead=saved,
            type_key="lead_assigned",
            source_txn_id=f"{saved.id}:{saved.assigned_user_id}:{utc_now().strftime('%Y%m%d%H%M%S')}",
            actor_id=actor_id,
            actor_name=actor_name,
            notes=f"Assigned to {saved.assigned_user_name or saved.assigned_user_id}",
        )
        self._notify_assignment(saved, actor_id=actor_id, actor_name=actor_name)
        return saved

    def bulk_assign(
        self,
        lead_ids: List[str],
        assigned_user_id: str,
        assigned_user_name: str = "",
        *,
        actor_id: str = "",
        actor_name: str = "",
    ) -> List[CrmLead]:
        return [
            self.assign_lead(
                lid,
                assigned_user_id,
                assigned_user_name,
                actor_id=actor_id,
                actor_name=actor_name,
            )
            for lid in lead_ids
        ]

    def update_status(
        self,
        lead_id: str,
        status: str,
        *,
        actor_id: str = "",
        actor_name: str = "",
        reason: str = "",
    ) -> CrmLead:
        lead = self.get_lead(lead_id)
        self._validate_catalogs(status=status)
        before = {"status": lead.status}
        lead.status = status
        lead.touch(actor_id=actor_id, actor_name=actor_name)
        saved = self._leads.save(lead)
        self._write_audit(
            entity_id=saved.id,
            action="status_change",
            actor_id=actor_id,
            actor_name=actor_name,
            reason=reason,
            before=before,
            after={"status": saved.status},
        )
        return saved

    def bulk_update_status(
        self,
        lead_ids: List[str],
        status: str,
        *,
        actor_id: str = "",
        actor_name: str = "",
    ) -> List[CrmLead]:
        return [
            self.update_status(lid, status, actor_id=actor_id, actor_name=actor_name)
            for lid in lead_ids
        ]

    def mark_lost(
        self,
        lead_id: str,
        lost_reason: str,
        *,
        actor_id: str = "",
        actor_name: str = "",
    ) -> CrmLead:
        lead = self.get_lead(lead_id)
        before = {"status": lead.status}
        lead.status = LeadStatus.LOST.value
        lead.lost_reason = (lost_reason or "").strip()
        lead.lost_at = utc_now()
        lead.lost_by_id = actor_id
        lead.lost_by_name = actor_name
        lead.touch(actor_id=actor_id, actor_name=actor_name)
        saved = self._leads.save(lead)
        self._write_audit(
            entity_id=saved.id,
            action="lost",
            actor_id=actor_id,
            actor_name=actor_name,
            reason=lost_reason,
            before=before,
            after={"status": saved.status, "lost_reason": saved.lost_reason},
        )
        self._record_auto_activity(
            lead=saved,
            type_key="lead_lost",
            source_txn_id=saved.id,
            actor_id=actor_id,
            actor_name=actor_name,
            notes=lost_reason,
        )
        return saved

    def reopen_lead(
        self,
        lead_id: str,
        *,
        status: str = LeadStatus.FOLLOW_UP_REQUIRED.value,
        actor_id: str = "",
        actor_name: str = "",
    ) -> CrmLead:
        lead = self.get_lead(lead_id)
        before = {"status": lead.status}
        lead.status = status or LeadStatus.FOLLOW_UP_REQUIRED.value
        lead.lost_reason = ""
        lead.lost_at = None
        lead.touch(actor_id=actor_id, actor_name=actor_name)
        saved = self._leads.save(lead)
        self._write_audit(
            entity_id=saved.id,
            action="reopen",
            actor_id=actor_id,
            actor_name=actor_name,
            before=before,
            after={"status": saved.status},
        )
        return saved

    def link_to_customer(
        self,
        lead_id: str,
        customer_id: str,
        *,
        actor_id: str = "",
        actor_name: str = "",
    ) -> CrmLead:
        if not self._customers:
            raise ValidationError("Customer service not configured")
        lead = self.get_lead(lead_id)
        customer = self._customers.get_customer_detail(customer_id)
        if not customer:
            raise ValidationError("Customer not found")
        return self._finalize_conversion(
            lead,
            customer.id,
            customer.customer_name,
            actor_id=actor_id,
            actor_name=actor_name,
            action="link_customer",
        )

    def convert_to_customer(
        self,
        lead_id: str,
        *,
        actor_id: str = "",
        actor_name: str = "",
        force_new: bool = False,
    ) -> CrmLead:
        """Create or link customer then mark lead converted (compensating-safe)."""
        if not self._customers:
            raise ValidationError("Customer service not configured")
        lead = self.get_lead(lead_id)
        if lead.status == LeadStatus.CONVERTED.value and lead.customer_id:
            return lead

        customer = None
        if not force_new:
            dup = self.detect_duplicates(
                phone=lead.phone,
                email=lead.email,
                gstin=lead.gstin,
                name=lead.name,
                exclude_lead_id=lead.id,
            )
            if dup.customer_id:
                customer = self._customers.get_customer_detail(dup.customer_id)

        created_customer_id = ""
        try:
            if not customer:
                customer_input = CustomerInput(
                    customer_name=lead.name,
                    phone_number=lead.phone_normalized or lead.phone or "0000000000",
                    alternate_phone_number=lead.alternate_phone or None,
                    email=lead.email,
                    contact_person=lead.contact_person,
                    address_line1=lead.address_line1,
                    address_line2=lead.address_line2,
                    city=lead.city,
                    state_code=lead.state_code,
                    pincode=lead.pincode,
                    gstin=lead.gstin,
                    notes=lead.notes,
                    registration_type=PartyRegistrationType.UNREGISTERED,
                )
                # Phone required by party validation â€” use placeholder only if empty after normalize fails
                if not lead.phone and not lead.phone_normalized:
                    raise ValidationError("Phone number is required to convert lead")
                customer = self._customers.create_customer(customer_input)
                created_customer_id = customer.id

            # Assign CRM owner onto customer when empty
            if not getattr(customer, "assigned_user_id", ""):
                customer.assigned_user_id = lead.assigned_user_id
                customer.assigned_user_name = lead.assigned_user_name
                customer.updated_at = utc_now()
                if hasattr(self._customers, "_customer_repo"):
                    self._customers._customer_repo.save(customer)

            return self._finalize_conversion(
                lead,
                customer.id,
                customer.customer_name,
                actor_id=actor_id,
                actor_name=actor_name,
                action="convert",
            )
        except Exception:
            # Compensating: if we created a customer but failed to convert, soft-note via re-raise
            # (customers have no soft-delete; leave orphan only if conversion after create fails â€”
            # re-raise after attempting nothing destructive beyond create).
            raise

    def _finalize_conversion(
        self,
        lead: CrmLead,
        customer_id: str,
        customer_name: str,
        *,
        actor_id: str,
        actor_name: str,
        action: str,
    ) -> CrmLead:
        before = {"status": lead.status, "customer_id": lead.customer_id}
        lead.customer_id = customer_id
        lead.customer_name = customer_name
        lead.status = LeadStatus.CONVERTED.value
        lead.converted_at = utc_now()
        lead.converted_by_id = actor_id
        lead.converted_by_name = actor_name
        lead.touch(actor_id=actor_id, actor_name=actor_name)
        saved = self._leads.save(lead)
        if self._enquiries:
            for enquiry in self._enquiries.list(lead_id=saved.id, limit=1000):
                enquiry.customer_id = customer_id
                enquiry.party_name = enquiry.party_name or customer_name
                enquiry.touch(actor_id=actor_id, actor_name=actor_name)
                self._enquiries.save(enquiry)
        if self._activities:
            for activity in self._activities.list(lead_id=saved.id, limit=1000):
                if not activity.customer_id:
                    activity.customer_id = customer_id
                    activity.touch(actor_id=actor_id, actor_name=actor_name)
                    self._activities.save(activity)
        self._write_audit(
            entity_id=saved.id,
            action=action,
            actor_id=actor_id,
            actor_name=actor_name,
            before=before,
            after={
                "status": saved.status,
                "customer_id": saved.customer_id,
                "customer_name": saved.customer_name,
            },
        )
        self._record_auto_activity(
            lead=saved,
            type_key="lead_converted",
            source_txn_id=saved.id,
            actor_id=actor_id,
            actor_name=actor_name,
            notes=f"Linked to customer {customer_name}",
        )
        return saved

    def _record_auto_activity(
        self,
        *,
        lead: CrmLead,
        type_key: str,
        source_txn_id: str,
        actor_id: str = "",
        actor_name: str = "",
        notes: str = "",
    ) -> None:
        if not self._activities:
            return
        label = AUTO_ACTIVITY_TYPE_KEYS.get(type_key, type_key)
        key = activity_type_key(label)
        existing = self._activities.find_by_source("crm", "lead", source_txn_id, key)
        if existing:
            return
        activity = CrmActivity(
            activity_type=label,
            activity_type_key=key,
            origin=ActivityOrigin.AUTOMATIC.value,
            status=ActivityStatus.COMPLETED.value,
            lead_id=lead.id,
            customer_id=lead.customer_id,
            party_name=lead.name,
            assigned_user_id=lead.assigned_user_id,
            assigned_user_name=lead.assigned_user_name,
            activity_at=utc_now(),
            completed_at=utc_now(),
            notes=notes,
            source_module="crm",
            source_txn_type="lead",
            source_txn_id=source_txn_id,
            branch=lead.branch,
        )
        activity.touch(actor_id=actor_id, actor_name=actor_name, creating=True)
        self._activities.save(activity)
        lead.last_activity_at = utc_now()
        self._leads.save(lead)

    def _notify_assignment(
        self, lead: CrmLead, *, actor_id: str = "", actor_name: str = ""
    ) -> None:
        if not lead.assigned_user_id:
            return
        if self._notification_service:
            prefs = self._notification_service.get_preferences(lead.assigned_user_id)
            if not prefs.lead_assigned:
                return
            self._notification_service.create(
                recipient_id=lead.assigned_user_id,
                kind=NotificationKind.LEAD_ASSIGNED,
                title="Lead assigned",
                message=f"Lead '{lead.name}' was assigned to you",
                ref_type="crm_lead",
                ref_id=lead.id,
                branch=lead.branch,
            )
            return
        if not self._notifications:
            return
        dedupe = CrmNotification.build_dedupe_key(
            lead.assigned_user_id,
            NotificationKind.LEAD_ASSIGNED,
            "crm_lead",
            lead.id,
        )
        if self._notifications.find_by_dedupe_key(dedupe):
            return
        self._notifications.save(
            CrmNotification(
                recipient_id=lead.assigned_user_id,
                kind=NotificationKind.LEAD_ASSIGNED.value,
                title="Lead assigned",
                message=f"Lead '{lead.name}' was assigned to you",
                ref_type="crm_lead",
                ref_id=lead.id,
                dedupe_key=dedupe,
                branch=lead.branch,
            )
        )

    def find_by_import_fingerprint(
        self, batch_id: str, fingerprint: str
    ) -> Optional[CrmLead]:
        return self._leads.find_by_import_fingerprint(batch_id, fingerprint)

    def upsert_from_import_row(
        self,
        row: Dict[str, Any],
        *,
        policy: str,
        batch_id: str,
        fingerprint: str,
        actor_id: str = "",
        actor_name: str = "",
        branch: str = "",
    ) -> Dict[str, Any]:
        """Import one mapped row. Returns outcome dict for batch tracking."""
        from vaybooks.bms.domain.crm.enums import LeadImportDuplicatePolicy

        existing = self.find_by_import_fingerprint(batch_id, fingerprint)
        if existing:
            return {"outcome": "skipped", "lead_id": existing.id, "reason": "fingerprint"}

        phone = (row.get("phone") or row.get("phone_number") or "").strip()
        email = (row.get("email") or "").strip()
        gstin = (row.get("gstin") or "").strip()
        name = (row.get("name") or row.get("lead_name") or "").strip()
        dup = self.detect_duplicates(
            phone=phone, email=email, gstin=gstin, name=name
        )

        policy_val = policy
        if isinstance(policy, LeadImportDuplicatePolicy):
            policy_val = policy.value

        if dup.lead:
            if policy_val in (LeadImportDuplicatePolicy.SKIP.value, "skip"):
                return {"outcome": "skipped", "lead_id": dup.lead.id, "reason": "duplicate"}
            if policy_val in (LeadImportDuplicatePolicy.UPDATE.value, "update"):
                updated = self.update_lead(
                    dup.lead.id,
                    actor_id=actor_id,
                    actor_name=actor_name,
                    name=name or dup.lead.name,
                    phone=phone or dup.lead.phone,
                    email=email or dup.lead.email,
                    gstin=gstin or dup.lead.gstin,
                    source=row.get("source") or dup.lead.source,
                    notes=row.get("notes") or dup.lead.notes,
                    city=row.get("city") or dup.lead.city,
                    area=row.get("area") or dup.lead.area,
                )
                updated.import_batch_id = batch_id
                updated.import_row_fingerprint = fingerprint
                self._leads.save(updated)
                return {"outcome": "updated", "lead_id": updated.id}
            if policy_val in (
                LeadImportDuplicatePolicy.IMPORT_AS_SEPARATE.value,
                "import_as_separate",
            ):
                pass  # fall through to create with allow_duplicate
            elif policy_val in (
                LeadImportDuplicatePolicy.LINK_TO_CUSTOMER.value,
                "link_to_customer",
            ):
                if dup.customer_id:
                    lead = self.create_lead(
                        name=name,
                        phone=phone,
                        email=email,
                        gstin=gstin,
                        source=row.get("source") or "Imported",
                        notes=row.get("notes") or "",
                        city=row.get("city") or "",
                        area=row.get("area") or "",
                        contact_person=row.get("contact_person") or "",
                        address_line1=row.get("address_line1") or "",
                        state_code=row.get("state_code") or "",
                        pincode=row.get("pincode") or "",
                        interested_products=row.get("interested_products") or "",
                        estimated_value=optional_float(row.get("estimated_value")),
                        status=row.get("status") or LeadStatus.NEW.value,
                        branch=branch,
                        import_batch_id=batch_id,
                        import_row_fingerprint=fingerprint,
                        actor_id=actor_id,
                        actor_name=actor_name,
                        allow_duplicate=True,
                    )
                    self.link_to_customer(
                        lead.id, dup.customer_id, actor_id=actor_id, actor_name=actor_name
                    )
                    return {"outcome": "linked", "lead_id": lead.id, "customer_id": dup.customer_id}
                return {"outcome": "failed", "reason": "no_customer_match"}
            else:
                return {"outcome": "failed", "reason": "duplicate", "lead_id": dup.lead.id}

        if dup.customer_id and policy_val in (
            LeadImportDuplicatePolicy.LINK_TO_CUSTOMER.value,
            "link_to_customer",
        ):
            lead = self.create_lead(
                name=name,
                phone=phone,
                email=email,
                gstin=gstin,
                source=row.get("source") or "Imported",
                notes=row.get("notes") or "",
                city=row.get("city") or "",
                area=row.get("area") or "",
                contact_person=row.get("contact_person") or "",
                address_line1=row.get("address_line1") or "",
                state_code=row.get("state_code") or "",
                pincode=row.get("pincode") or "",
                interested_products=row.get("interested_products") or "",
                estimated_value=optional_float(row.get("estimated_value")),
                branch=branch,
                import_batch_id=batch_id,
                import_row_fingerprint=fingerprint,
                actor_id=actor_id,
                actor_name=actor_name,
                allow_duplicate=True,
            )
            self.link_to_customer(
                lead.id, dup.customer_id, actor_id=actor_id, actor_name=actor_name
            )
            return {"outcome": "linked", "lead_id": lead.id, "customer_id": dup.customer_id}

        lead = self.create_lead(
            name=name,
            phone=phone,
            email=email,
            gstin=gstin,
            source=row.get("source") or "Imported",
            notes=row.get("notes") or "",
            city=row.get("city") or "",
            area=row.get("area") or "",
            contact_person=row.get("contact_person") or "",
            address_line1=row.get("address_line1") or "",
            alternate_phone=row.get("alternate_phone") or row.get("alternate_phone_number") or "",
            state_code=row.get("state_code") or "",
            pincode=row.get("pincode") or "",
            interested_products=row.get("interested_products") or "",
            estimated_value=optional_float(row.get("estimated_value")),
            status=row.get("status") or LeadStatus.NEW.value,
            priority=row.get("priority") or "Medium",
            branch=branch,
            import_batch_id=batch_id,
            import_row_fingerprint=fingerprint,
            actor_id=actor_id,
            actor_name=actor_name,
            allow_duplicate=policy_val
            in (LeadImportDuplicatePolicy.IMPORT_AS_SEPARATE.value, "import_as_separate"),
        )
        return {"outcome": "created", "lead_id": lead.id}
