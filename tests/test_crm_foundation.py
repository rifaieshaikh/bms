"""Focused CRM domain/service/migration/WhatsApp/idempotency tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

import pytest

from vaybooks.bms.application.crm.activities import (
    CrmActivityAppService,
    CrmAutoActivityService,
)
from vaybooks.bms.application.crm.enquiries import CrmEnquiryAppService
from vaybooks.bms.application.crm.leads import CrmLeadAppService
from vaybooks.bms.application.crm.payment_reminder import CrmPaymentReminderService
from vaybooks.bms.application.crm.reports import CrmReportService
from vaybooks.bms.application.crm.settings import CrmSettingsAppService
from vaybooks.bms.application.migration.schemas import (
    DuplicatePolicy,
    ImportEntityType,
    fields_for,
)
from vaybooks.bms.application.migration.templates import template_csv
from vaybooks.bms.application.migration.validators import validate_mapped_rows
from vaybooks.bms.domain.crm.access import CrmAccessPolicy
from vaybooks.bms.domain.crm.entities import (
    CrmActivity,
    CrmAuditEntry,
    CrmEnquiry,
    CrmImportBatch,
    CrmLead,
    CrmNotification,
    CrmSettings,
)
from vaybooks.bms.domain.crm.enums import (
    CRM_REPORT_DEFINITIONS,
    ActivityStatus,
    CrmRole,
    LeadStatus,
)
from vaybooks.bms.domain.crm.services import (
    build_whatsapp_click_to_chat_url,
    file_bytes_hash,
    format_invoice_refs,
    lead_row_fingerprint,
    normalize_phone_for_whatsapp,
    render_payment_reminder_message,
)
from vaybooks.bms.domain.projects.access import AppUser
from vaybooks.bms.domain.shared.exceptions import ValidationError


# --- in-memory fakes ---


class FakeLeadRepo:
    def __init__(self):
        self._store: Dict[str, CrmLead] = {}

    def save(self, lead: CrmLead) -> CrmLead:
        self._store[lead.id] = lead
        return lead

    def find_by_id(self, lead_id: str) -> Optional[CrmLead]:
        return self._store.get(lead_id)

    def find_by_phone_normalized(self, phone: str) -> Optional[CrmLead]:
        for lead in self._store.values():
            if not lead.is_deleted and lead.phone_normalized == phone:
                return lead
        return None

    def find_by_email_normalized(self, email: str) -> Optional[CrmLead]:
        for lead in self._store.values():
            if not lead.is_deleted and lead.email_normalized == email:
                return lead
        return None

    def find_by_gstin_normalized(self, gstin: str) -> Optional[CrmLead]:
        for lead in self._store.values():
            if not lead.is_deleted and lead.gstin_normalized == gstin:
                return lead
        return None

    def find_by_import_fingerprint(
        self, batch_id: str, fingerprint: str
    ) -> Optional[CrmLead]:
        for lead in self._store.values():
            if lead.is_deleted:
                continue
            if lead.import_row_fingerprint == fingerprint:
                if not batch_id or lead.import_batch_id == batch_id:
                    return lead
        return None

    def list(self, **kwargs) -> List[CrmLead]:
        items = [l for l in self._store.values() if not l.is_deleted]
        status = kwargs.get("status")
        if status:
            items = [l for l in items if l.status == status]
        assigned = kwargs.get("assigned_user_id")
        if assigned is not None:
            if assigned == "":
                items = [l for l in items if not l.assigned_user_id]
            else:
                items = [l for l in items if l.assigned_user_id == assigned]
        return items[: kwargs.get("limit", 500)]

    def list_duplicates_candidates(self) -> List[CrmLead]:
        return [l for l in self._store.values() if not l.is_deleted]


class FakeEnquiryRepo:
    def __init__(self):
        self._store: Dict[str, CrmEnquiry] = {}

    def save(self, enquiry: CrmEnquiry) -> CrmEnquiry:
        self._store[enquiry.id] = enquiry
        return enquiry

    def find_by_id(self, enquiry_id: str) -> Optional[CrmEnquiry]:
        return self._store.get(enquiry_id)

    def list(self, **kwargs) -> List[CrmEnquiry]:
        items = [e for e in self._store.values() if not e.is_deleted]
        if kwargs.get("lead_id"):
            items = [e for e in items if e.lead_id == kwargs["lead_id"]]
        return items


class FakeActivityRepo:
    def __init__(self):
        self._store: Dict[str, CrmActivity] = {}

    def save(self, activity: CrmActivity) -> CrmActivity:
        self._store[activity.id] = activity
        return activity

    def find_by_id(self, activity_id: str) -> Optional[CrmActivity]:
        return self._store.get(activity_id)

    def find_by_source(
        self,
        source_module: str,
        source_txn_type: str,
        source_txn_id: str,
        activity_type_key: str,
    ) -> Optional[CrmActivity]:
        for a in self._store.values():
            if (
                a.source_module == source_module
                and a.source_txn_type == source_txn_type
                and a.source_txn_id == source_txn_id
                and a.activity_type_key == activity_type_key
            ):
                return a
        return None

    def list(self, **kwargs) -> List[CrmActivity]:
        return list(self._store.values())[: kwargs.get("limit", 500)]

    def list_timeline(self, **kwargs) -> List[CrmActivity]:
        return self.list(**kwargs)


class FakeAuditRepo:
    def __init__(self):
        self.entries: List[CrmAuditEntry] = []

    def save(self, entry: CrmAuditEntry) -> CrmAuditEntry:
        self.entries.append(entry)
        return entry

    def list_for_entity(self, entity_type: str, entity_id: str, *, limit: int = 200):
        return [
            e
            for e in self.entries
            if e.entity_type == entity_type and e.entity_id == entity_id
        ][:limit]


class FakeSettingsRepo:
    def __init__(self):
        self._settings = CrmSettings()

    def get(self) -> CrmSettings:
        return self._settings

    def save(self, settings: CrmSettings) -> CrmSettings:
        self._settings = settings
        return settings


class FakeNotificationRepo:
    def __init__(self):
        self._store: Dict[str, CrmNotification] = {}

    def save(self, notification: CrmNotification) -> CrmNotification:
        self._store[notification.id] = notification
        return notification

    def find_by_dedupe_key(self, dedupe_key: str) -> Optional[CrmNotification]:
        for n in self._store.values():
            if n.dedupe_key == dedupe_key:
                return n
        return None

    def list_for_recipient(self, recipient_id: str, *, unread_only=False, limit=100):
        return [
            n for n in self._store.values() if n.recipient_id == recipient_id
        ][:limit]


class FakeImportBatchRepo:
    def __init__(self):
        self._store: Dict[str, CrmImportBatch] = {}

    def save(self, batch: CrmImportBatch) -> CrmImportBatch:
        self._store[batch.id] = batch
        return batch

    def find_by_id(self, batch_id: str) -> Optional[CrmImportBatch]:
        return self._store.get(batch_id)

    def find_by_file_hash(self, file_hash: str) -> Optional[CrmImportBatch]:
        for b in self._store.values():
            if b.file_hash == file_hash:
                return b
        return None

    def list_recent(self, *, limit: int = 50):
        return list(self._store.values())[:limit]


@dataclass
class FakeCustomer:
    customer_name: str
    phone_number: str
    id: str = field(default_factory=lambda: uuid4().hex)
    email: str = ""
    gstin: str = ""
    assigned_user_id: str = ""
    assigned_user_name: str = ""


class FakeCustomerService:
    def __init__(self):
        self._by_id: Dict[str, FakeCustomer] = {}
        self._by_phone: Dict[str, FakeCustomer] = {}

    def create_customer(self, customer_input) -> FakeCustomer:
        c = FakeCustomer(
            customer_name=customer_input.customer_name,
            phone_number=customer_input.phone_number,
            email=getattr(customer_input, "email", ""),
            gstin=getattr(customer_input, "gstin", ""),
        )
        self._by_id[c.id] = c
        self._by_phone[c.phone_number] = c
        return c

    def get_customer_detail(self, customer_id: str):
        return self._by_id.get(customer_id)

    def lookup_customer_by_phone(self, phone: str):
        return self._by_phone.get(phone)

    def list_all_customers(self):
        return list(self._by_id.values())


@pytest.fixture
def lead_svc():
    leads = FakeLeadRepo()
    activities = FakeActivityRepo()
    audits = FakeAuditRepo()
    notifications = FakeNotificationRepo()
    customers = FakeCustomerService()
    settings = FakeSettingsRepo()
    svc = CrmLeadAppService(
        leads,
        audit_repo=audits,
        activity_repo=activities,
        notification_repo=notifications,
        customer_service=customers,
        settings_repo=settings,
    )
    return svc, leads, activities, audits, customers


# --- domain / access ---


def test_crm_role_on_app_user_backward_compatible():
    user = AppUser(username="rep1", display_name="Rep")
    assert user.crm_roles == []
    user.crm_roles = [CrmRole.SALES_REPRESENTATIVE]
    assert user.has_crm_role(CrmRole.SALES_REPRESENTATIVE)
    policy = CrmAccessPolicy(user)
    assert policy.is_rep()
    assert not policy.is_admin()
    assert policy.scoped_assigned_user_id() == user.id


def test_settings_defaults_seeded():
    settings = CrmSettings()
    assert settings.order_trigger_status == "Confirmed"
    assert any(i["label"] == "Walk-in" for i in settings.lead_sources)
    assert settings.outcome_required_for("Called")
    assert not settings.outcome_required_for("Note")


# --- leads ---


def test_create_lead_and_duplicate_detection(lead_svc):
    svc, *_ = lead_svc
    lead = svc.create_lead(name="Acme", phone="9876543210", source="Walk-in")
    assert lead.status == LeadStatus.NEW.value
    assert lead.phone_normalized == "9876543210"
    with pytest.raises(ValidationError, match="Duplicate"):
        svc.create_lead(name="Acme 2", phone="9876543210")


def test_assign_status_lost_reopen(lead_svc):
    svc, _, activities, audits, _ = lead_svc
    lead = svc.create_lead(name="Beta", phone="9876543211")
    assigned = svc.assign_lead(lead.id, "u1", "Alice", actor_id="mgr", actor_name="Mgr")
    assert assigned.assigned_user_id == "u1"
    assert any(a.action == "assign" for a in audits.entries)
    lost = svc.mark_lost(lead.id, "Price", actor_id="mgr")
    assert lost.status == LeadStatus.LOST.value
    reopened = svc.reopen_lead(lead.id)
    assert reopened.status == LeadStatus.FOLLOW_UP_REQUIRED.value
    assert any(a.activity_type == "Lead Lost" for a in activities._store.values())


def test_convert_and_link_customer(lead_svc):
    svc, _, _, _, customers = lead_svc
    lead = svc.create_lead(name="Gamma Traders", phone="9876543212", city="Chennai")
    converted = svc.convert_to_customer(lead.id, actor_id="u1", actor_name="Rep")
    assert converted.status == LeadStatus.CONVERTED.value
    assert converted.customer_id
    assert customers.get_customer_detail(converted.customer_id)

    lead2 = svc.create_lead(
        name="Other", phone="9876543213", allow_duplicate=True
    )
    linked = svc.link_to_customer(
        lead2.id, converted.customer_id, actor_id="u1", actor_name="Rep"
    )
    assert linked.customer_id == converted.customer_id
    assert linked.status == LeadStatus.CONVERTED.value


# --- enquiries / activities ---


def test_enquiry_lifecycle_and_manual_activity_outcome():
    leads = FakeLeadRepo()
    enquiries = FakeEnquiryRepo()
    activities = FakeActivityRepo()
    settings = FakeSettingsRepo()
    lead_svc = CrmLeadAppService(leads)
    lead = lead_svc.create_lead(name="Delta", phone="9876543214")
    enq_svc = CrmEnquiryAppService(
        enquiries, activity_repo=activities, lead_repo=leads
    )
    enquiry = enq_svc.create_enquiry(lead_id=lead.id, product_interest="Uniforms")
    assert enquiry.status in {"Open", "Assigned"}
    assert any(a.activity_type == "Enquiry Created" for a in activities._store.values())

    act_svc = CrmActivityAppService(activities, settings_repo=settings, lead_repo=leads)
    activity = act_svc.create_manual(
        activity_type="Called",
        lead_id=lead.id,
        enquiry_id=enquiry.id,
        assigned_user_id="u1",
    )
    with pytest.raises(ValidationError, match="Outcome"):
        act_svc.complete(activity.id)
    completed = act_svc.complete(activity.id, outcome="Interested")
    assert completed.status == ActivityStatus.COMPLETED.value


def test_auto_activity_idempotency_and_reversal():
    activities = FakeActivityRepo()
    settings = FakeSettingsRepo()
    auto = CrmAutoActivityService(activities, settings_repo=settings)
    first = auto.on_order_confirmed("so1", status="Confirmed", customer_id="c1")
    second = auto.on_order_confirmed("so1", status="Confirmed", customer_id="c1")
    assert first.id == second.id
    assert len(activities._store) == 1
    reversed_act = auto.on_order_cancelled("so1")
    assert reversed_act.status == ActivityStatus.REVERSED.value


# --- WhatsApp ---


def test_whatsapp_phone_normalization_and_url():
    assert normalize_phone_for_whatsapp("9876543210") == "919876543210"
    assert normalize_phone_for_whatsapp("+91 98765 43210") == "919876543210"
    msg = render_payment_reminder_message(
        "Hi {customer_name} from {business_name}: Rs.{outstanding_amount}",
        customer_name="Acme",
        business_name="VayBooks",
        outstanding_amount=1250.5,
    )
    assert "Acme" in msg and "1,250.50" in msg
    url = build_whatsapp_click_to_chat_url("9876543210", msg)
    assert url.startswith("https://wa.me/919876543210?text=")


def test_reminder_message_supports_multi_invoice_placeholders():
    msg = render_payment_reminder_message(
        "{customer_name}: Rs.{outstanding_amount} across {invoice_count} "
        "invoices ({invoice_refs}), oldest {oldest_due_date}",
        customer_name="Acme",
        business_name="VayBooks",
        outstanding_amount=2000,
        invoice_refs="INV-1 (Rs.1,200.00), INV-2 (Rs.800.00)",
        invoice_count=2,
        oldest_due_date="02-Jul-2026",
    )
    assert "across 2 invoices" in msg
    assert "INV-1 (Rs.1,200.00), INV-2 (Rs.800.00)" in msg
    assert "oldest 02-Jul-2026" in msg


def test_format_invoice_refs_caps_the_list():
    invoices = [
        {"reference": f"INV-{i}", "outstanding": 100.0 * i} for i in range(1, 6)
    ]
    refs = format_invoice_refs(invoices, limit=3)
    assert refs.startswith("INV-1 (Rs.100.00)")
    assert "INV-3" in refs and "INV-4" not in refs
    assert refs.endswith("+2 more")
    assert format_invoice_refs([]) == ""


def test_payment_reminder_preview_includes_open_invoices():
    from types import SimpleNamespace

    from vaybooks.bms.domain.parties.customers.entities import CustomerInput
    from vaybooks.bms.domain.shared.enums import VoucherType

    settings = FakeSettingsRepo()
    settings.get().payment_reminder_template = (
        "{customer_name} owes Rs.{outstanding_amount} on {invoice_count} "
        "invoice(s): {invoice_refs}. Oldest: {oldest_due_date}."
    )
    customers = FakeCustomerService()
    cust = customers.create_customer(
        CustomerInput(customer_name="Payee", phone_number="9876543215")
    )

    def _invoice(voucher_id, number, day, amount):
        return SimpleNamespace(
            id=voucher_id,
            voucher_type=VoucherType.SALES_INVOICE,
            description=f"Store invoice {number}",
            voucher_date=datetime(2026, 7, day),
            lines=[
                {
                    "description": "Sales invoice",
                    "credit_amount": amount,
                    "debit_amount": 0,
                    "account_id": "sales-acct",
                    "account_name": "Sales",
                },
                {
                    "description": "",
                    "debit_amount": amount,
                    "credit_amount": 0,
                    "account_id": "cust-acct",
                    "account_name": "Payee",
                },
            ],
        )

    class FakeAccounting:
        def get_customer_account(self, _customer_id):
            return SimpleNamespace(id="cust-acct")

        def list_vouchers_by_type(self, _voucher_type):
            return [
                _invoice("v2", "INV-2", 10, 800.0),
                _invoice("v1", "INV-1", 2, 1200.0),
            ]

        def customer_balances_by_customer(self):
            return {cust.id: 2000.0}

    svc = CrmPaymentReminderService(
        settings,
        customer_service=customers,
        accounting_service=FakeAccounting(),
    )
    preview = svc.preview(cust.id)
    assert preview.outstanding_amount == 2000.0
    assert preview.invoice_count == 2
    # Oldest invoice first, both listed with amounts
    assert preview.invoice_refs == "INV-1 (Rs.1,200.00), INV-2 (Rs.800.00)"
    assert preview.oldest_due_date == "02-Jul-2026"
    assert "on 2 invoice(s)" in preview.message
    assert "INV-1 (Rs.1,200.00)" in preview.message
    assert "Oldest: 02-Jul-2026" in preview.message
    assert len(preview.open_invoices) == 2


def test_payment_reminder_preview_and_schedule():
    settings = FakeSettingsRepo()
    activities = FakeActivityRepo()
    customers = FakeCustomerService()
    from vaybooks.bms.domain.parties.customers.entities import CustomerInput

    cust = customers.create_customer(
        CustomerInput(customer_name="Payee", phone_number="9876543215")
    )
    svc = CrmPaymentReminderService(
        settings, activity_repo=activities, customer_service=customers
    )
    preview = svc.preview(cust.id, outstanding_amount=500)
    assert "wa.me" in preview.whatsapp_url
    tasks = svc.schedule_reminder_tasks(
        customer_id=cust.id,
        customer_name=cust.customer_name,
        outstanding_amount=500,
        recipient_id="collector1",
        phone=cust.phone_number,
    )
    assert len(tasks) >= 1
    # Idempotent schedule
    again = svc.schedule_reminder_tasks(
        customer_id=cust.id,
        customer_name=cust.customer_name,
        outstanding_amount=500,
        recipient_id="collector1",
        phone=cust.phone_number,
    )
    assert len(activities._store) == len(again)


# --- reports / migration ---


def test_report_catalog_has_34_and_runs():
    assert len(CRM_REPORT_DEFINITIONS) == 34
    leads = FakeLeadRepo()
    lead_svc = CrmLeadAppService(leads)
    lead_svc.create_lead(name="R1", phone="9876543216", source="Website")
    reports = CrmReportService(leads)
    assert len(reports.list_reports()) == 34
    funnel = reports.run_report("lead_conversion_funnel")
    assert funnel.title == "Lead Conversion Funnel"
    assert not funnel.empty
    for rid, _, _ in CRM_REPORT_DEFINITIONS:
        result = reports.run_report(rid)
        assert result.report_id == rid


def test_leads_import_schema_template_and_fingerprint_idempotency(lead_svc):
    assert ImportEntityType.LEADS in {e for e in ImportEntityType}
    fields = fields_for(ImportEntityType.LEADS)
    assert any(f.key == "name" and f.required for f in fields)
    csv_text = template_csv(ImportEntityType.LEADS)
    assert "name" in csv_text and "phone" in csv_text

    rows = [
        {"_row": 1, "name": "Imp Lead", "phone": "9876543217", "email": "", "gstin": "", "source": "Imported"},
        {"_row": 2, "name": "Imp Lead", "phone": "9876543217", "email": "", "gstin": "", "source": "Imported"},
    ]
    preview = validate_mapped_rows(ImportEntityType.LEADS, rows)
    assert preview.valid_rows == 1
    assert any("Duplicate row" in i.message for i in preview.issues)

    svc, leads, _, _, _ = lead_svc
    fp = lead_row_fingerprint(rows[0])
    first = svc.upsert_from_import_row(
        rows[0], policy="skip", batch_id="b1", fingerprint=fp
    )
    second = svc.upsert_from_import_row(
        rows[0], policy="skip", batch_id="b1", fingerprint=fp
    )
    assert first["outcome"] == "created"
    assert second["outcome"] == "skipped"
    assert len(leads._store) == 1


def test_migration_018_module_importable():
    import importlib

    crm_mig = importlib.import_module(
        "vaybooks.bms.infrastructure.db.migrations.versions.018_crm_module"
    )
    assert callable(crm_mig.up)


def test_file_hash_stable():
    assert file_bytes_hash(b"abc") == file_bytes_hash(b"abc")
    assert file_bytes_hash(b"abc") != file_bytes_hash(b"abcd")


def test_settings_app_service_update():
    repo = FakeSettingsRepo()
    svc = CrmSettingsAppService(repo, audit_repo=FakeAuditRepo())
    updated = svc.update_settings(
        actor_id="a1",
        default_inactivity_days=45,
        order_trigger_status="Confirmed",
    )
    assert updated.default_inactivity_days == 45
