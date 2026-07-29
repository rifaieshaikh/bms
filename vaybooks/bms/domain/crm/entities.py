"""CRM domain entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from vaybooks.bms.domain.crm.enums import (
    ActivityOrigin,
    ActivityStatus,
    CRM_SETTINGS_ID,
    DEFAULT_ACTIVITY_OUTCOMES,
    DEFAULT_ACTIVITY_TYPES,
    DEFAULT_ENQUIRY_STATUSES,
    DEFAULT_LEAD_SOURCES,
    DEFAULT_LEAD_STATUSES,
    DEFAULT_LOST_REASONS,
    DEFAULT_OUTCOME_REQUIRED_TYPES,
    EnquiryStatus,
    ImportBatchStatus,
    LeadPriority,
    LeadStatus,
    NotificationKind,
)
from vaybooks.bms.domain.shared.date_utils import utc_now


def _catalog_items(labels: tuple[str, ...] | list[str], *, system: bool = True) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for i, label in enumerate(labels):
        items.append(
            {
                "key": label.strip().lower().replace(" ", "_").replace("/", "_"),
                "label": label,
                "active": True,
                "system": system,
                "sort_order": i,
            }
        )
    return items


@dataclass
class CrmActorStamp:
    """Created/updated actor metadata shared by CRM records."""

    created_by_id: str = ""
    created_by_name: str = ""
    updated_by_id: str = ""
    updated_by_name: str = ""
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def touch(
        self,
        *,
        actor_id: str = "",
        actor_name: str = "",
        creating: bool = False,
    ) -> None:
        now = utc_now()
        if creating:
            self.created_at = now
            self.created_by_id = actor_id or self.created_by_id
            self.created_by_name = actor_name or self.created_by_name
        self.updated_at = now
        if actor_id:
            self.updated_by_id = actor_id
        if actor_name:
            self.updated_by_name = actor_name


@dataclass
class CrmLead:
    name: str
    phone: str = ""
    lead_number: str = ""
    contact_person: str = ""
    alternate_phone: str = ""
    email: str = ""
    address_line1: str = ""
    address_line2: str = ""
    area: str = ""
    city: str = ""
    state_code: str = ""
    pincode: str = ""
    gstin: str = ""
    source: str = ""
    interested_products: str = ""
    estimated_value: float = 0.0
    assigned_user_id: str = ""
    assigned_user_name: str = ""
    priority: str = LeadPriority.MEDIUM.value
    status: str = LeadStatus.NEW.value
    next_follow_up_at: Optional[datetime] = None
    notes: str = ""
    last_activity_at: Optional[datetime] = None
    phone_normalized: str = ""
    email_normalized: str = ""
    gstin_normalized: str = ""
    customer_id: str = ""
    customer_name: str = ""
    converted_at: Optional[datetime] = None
    converted_by_id: str = ""
    converted_by_name: str = ""
    lost_reason: str = ""
    lost_at: Optional[datetime] = None
    lost_by_id: str = ""
    lost_by_name: str = ""
    import_batch_id: str = ""
    import_row_fingerprint: str = ""
    branch: str = ""
    location_id: str = ""
    location_name: str = ""
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    created_by_id: str = ""
    created_by_name: str = ""
    updated_by_id: str = ""
    updated_by_name: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def soft_delete(self, *, actor_id: str = "", actor_name: str = "") -> None:
        self.is_deleted = True
        self.deleted_at = utc_now()
        self.touch(actor_id=actor_id, actor_name=actor_name)

    def touch(self, *, actor_id: str = "", actor_name: str = "", creating: bool = False) -> None:
        now = utc_now()
        if creating:
            self.created_at = now
            if actor_id:
                self.created_by_id = actor_id
            if actor_name:
                self.created_by_name = actor_name
        self.updated_at = now
        if actor_id:
            self.updated_by_id = actor_id
        if actor_name:
            self.updated_by_name = actor_name


@dataclass
class CrmEnquiry:
    enquiry_number: str = ""
    lead_id: str = ""
    customer_id: str = ""
    party_name: str = ""
    enquiry_date: Optional[datetime] = None
    source: str = ""
    product_interest: str = ""
    description: str = ""
    expected_quantity: float = 0.0
    estimated_value: float = 0.0
    priority: str = LeadPriority.MEDIUM.value
    assigned_user_id: str = ""
    assigned_user_name: str = ""
    expected_decision_at: Optional[datetime] = None
    next_follow_up_at: Optional[datetime] = None
    status: str = EnquiryStatus.OPEN.value
    lost_reason: str = ""
    notes: str = ""
    attachment_ids: List[str] = field(default_factory=list)
    quotation_id: str = ""
    sales_order_id: str = ""
    branch: str = ""
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    created_by_id: str = ""
    created_by_name: str = ""
    updated_by_id: str = ""
    updated_by_name: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def soft_delete(self, *, actor_id: str = "", actor_name: str = "") -> None:
        self.is_deleted = True
        self.deleted_at = utc_now()
        self.touch(actor_id=actor_id, actor_name=actor_name)

    def touch(self, *, actor_id: str = "", actor_name: str = "", creating: bool = False) -> None:
        now = utc_now()
        if creating:
            self.created_at = now
            if actor_id:
                self.created_by_id = actor_id
            if actor_name:
                self.created_by_name = actor_name
        self.updated_at = now
        if actor_id:
            self.updated_by_id = actor_id
        if actor_name:
            self.updated_by_name = actor_name


@dataclass
class CrmActivity:
    activity_type: str
    activity_type_key: str = ""
    origin: str = ActivityOrigin.MANUAL.value
    status: str = ActivityStatus.SCHEDULED.value
    lead_id: str = ""
    enquiry_id: str = ""
    customer_id: str = ""
    party_name: str = ""
    assigned_user_id: str = ""
    assigned_user_name: str = ""
    activity_at: Optional[datetime] = None
    scheduled_at: Optional[datetime] = None
    due_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    outcome: str = ""
    notes: str = ""
    next_action: str = ""
    next_follow_up_at: Optional[datetime] = None
    location: str = ""
    location_id: str = ""
    location_name: str = ""
    priority: str = LeadPriority.MEDIUM.value
    attachment_ids: List[str] = field(default_factory=list)
    # Automatic activity source identity (idempotency)
    source_module: str = ""
    source_txn_type: str = ""
    source_txn_id: str = ""
    promised_amount: float = 0.0
    promised_date: Optional[datetime] = None
    cancel_reason: str = ""
    branch: str = ""
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    created_by_id: str = ""
    created_by_name: str = ""
    updated_by_id: str = ""
    updated_by_name: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def soft_delete(self, *, actor_id: str = "", actor_name: str = "") -> None:
        self.is_deleted = True
        self.deleted_at = utc_now()
        self.touch(actor_id=actor_id, actor_name=actor_name)

    def touch(self, *, actor_id: str = "", actor_name: str = "", creating: bool = False) -> None:
        now = utc_now()
        if creating:
            self.created_at = now
            if actor_id:
                self.created_by_id = actor_id
            if actor_name:
                self.created_by_name = actor_name
        self.updated_at = now
        if actor_id:
            self.updated_by_id = actor_id
        if actor_name:
            self.updated_by_name = actor_name

    @property
    def is_automatic(self) -> bool:
        return self.origin == ActivityOrigin.AUTOMATIC.value


@dataclass
class CrmAuditEntry:
    entity_type: str
    entity_id: str
    action: str
    actor_id: str = ""
    actor_name: str = ""
    reason: str = ""
    before: Optional[Dict[str, Any]] = None
    after: Optional[Dict[str, Any]] = None
    branch: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)


@dataclass
class CrmNotification:
    recipient_id: str
    kind: str
    title: str
    message: str = ""
    ref_type: str = ""
    ref_id: str = ""
    state: str = "open"
    read_at: Optional[datetime] = None
    dedupe_key: str = ""
    branch: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)

    @staticmethod
    def build_dedupe_key(
        recipient_id: str,
        kind: str | NotificationKind,
        ref_type: str,
        ref_id: str,
        state: str = "open",
    ) -> str:
        kind_val = kind.value if isinstance(kind, NotificationKind) else str(kind)
        return f"{recipient_id}|{kind_val}|{ref_type}|{ref_id}|{state}"


@dataclass
class CrmNotificationPreferences:
    user_id: str
    activity_due_today: bool = True
    upcoming_visits: bool = True
    overdue_follow_ups: bool = True
    lead_assigned: bool = True
    enquiry_reassigned: bool = True
    payment_promises: bool = True
    high_priority_idle: bool = True
    payment_reminder_due: bool = True
    id: str = field(default_factory=lambda: uuid4().hex)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass
class CrmImportBatch:
    entity_type: str = "leads"
    source_filename: str = ""
    file_hash: str = ""
    imported_by_id: str = ""
    imported_by_name: str = ""
    status: str = ImportBatchStatus.RUNNING.value
    total_rows: int = 0
    created_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    linked_count: int = 0
    row_outcomes: List[Dict[str, Any]] = field(default_factory=list)
    error_summary: str = ""
    branch: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    completed_at: Optional[datetime] = None


@dataclass
class CrmSettings:
    """Single-document CRM configuration catalog and defaults."""

    lead_sources: List[Dict[str, Any]] = field(
        default_factory=lambda: _catalog_items(DEFAULT_LEAD_SOURCES)
    )
    lead_statuses: List[Dict[str, Any]] = field(
        default_factory=lambda: _catalog_items(DEFAULT_LEAD_STATUSES)
    )
    enquiry_statuses: List[Dict[str, Any]] = field(
        default_factory=lambda: _catalog_items(DEFAULT_ENQUIRY_STATUSES)
    )
    activity_types: List[Dict[str, Any]] = field(default_factory=list)
    activity_outcomes: List[Dict[str, Any]] = field(
        default_factory=lambda: _catalog_items(DEFAULT_ACTIVITY_OUTCOMES)
    )
    lost_reasons: List[Dict[str, Any]] = field(
        default_factory=lambda: _catalog_items(DEFAULT_LOST_REASONS)
    )
    default_inactivity_days: int = 30
    default_follow_up_days: int = 3
    order_trigger_status: str = "Confirmed"
    payment_trigger: str = "receipt_create"
    business_display_name: str = ""
    payment_reminder_template: str = (
        "Hello {customer_name}, this is a payment reminder from {business_name}. "
        "Your total outstanding across all pending invoices is Rs.{outstanding_amount}. "
        "Please contact us to arrange payment. Thank you."
    )
    payment_reminder_due_offsets_days: List[int] = field(default_factory=lambda: [0, 3, 7])
    id: str = CRM_SETTINGS_ID
    updated_at: datetime = field(default_factory=utc_now)
    updated_by_id: str = ""
    updated_by_name: str = ""

    def __post_init__(self) -> None:
        if not self.activity_types:
            items = _catalog_items(DEFAULT_ACTIVITY_TYPES)
            required = {t.lower() for t in DEFAULT_OUTCOME_REQUIRED_TYPES}
            for item in items:
                item["outcome_required"] = item["label"].lower() in required
                item["automatic"] = item["label"] in {
                    "Enquiry Created",
                    "Quotation Created",
                    "Quotation Sent",
                    "Order Placed",
                    "Invoice Created",
                    "Payment Received",
                    "Lead Assigned",
                    "Lead Converted",
                    "Lead Lost",
                }
            self.activity_types = items

    def outcome_required_for(self, activity_type: str) -> bool:
        label = (activity_type or "").strip().lower()
        for item in self.activity_types:
            if not item.get("active", True):
                continue
            if (item.get("label") or "").strip().lower() == label:
                return bool(item.get("outcome_required", False))
        return label in {t.lower() for t in DEFAULT_OUTCOME_REQUIRED_TYPES}


@dataclass
class LeadDuplicateMatch:
    lead: Optional[CrmLead] = None
    customer_id: str = ""
    customer_name: str = ""
    match_fields: List[str] = field(default_factory=list)
