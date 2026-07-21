from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import (
    PlaceOfSupplyMode,
    ProjectActivityStatus,
    ProjectBillingMode,
    ProjectDocumentCategory,
    ProjectExpenseSource,
    ProjectPartyRole,
    ProjectQuotationStatus,
    ProjectStatus,
)


@dataclass
class ProjectTemplatePhase:
    name: str
    sort_order: int = 0
    id: str = field(default_factory=lambda: uuid4().hex)


@dataclass
class ProjectTemplateActivity:
    name: str
    sort_order: int = 0
    parent_activity_id: Optional[str] = None
    default_hourly_rate: float = 0.0
    id: str = field(default_factory=lambda: uuid4().hex)


@dataclass
class ProjectTemplate:
    name: str
    description: str = ""
    phases_enabled: bool = True
    max_activity_depth: int = 3
    billing_mode: ProjectBillingMode = ProjectBillingMode.FIXED
    retention_pct: float = 0.0
    place_of_supply_mode: PlaceOfSupplyMode = PlaceOfSupplyMode.SITE_STATE
    default_hourly_rate: float = 0.0
    phases: List[ProjectTemplatePhase] = field(default_factory=list)
    activities: List[ProjectTemplateActivity] = field(default_factory=list)
    is_system: bool = False
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass
class ProjectParty:
    party_id: str
    party_name: str
    role: ProjectPartyRole = ProjectPartyRole.CUSTOMER
    is_primary: bool = False
    id: str = field(default_factory=lambda: uuid4().hex)


@dataclass
class ProjectPhase:
    name: str
    sort_order: int = 0
    id: str = field(default_factory=lambda: uuid4().hex)


@dataclass
class ProjectActivity:
    name: str
    sort_order: int = 0
    parent_activity_id: Optional[str] = None
    phase_id: Optional[str] = None
    status: ProjectActivityStatus = ProjectActivityStatus.PENDING
    activity_config_id: str = ""
    activity_category: str = ""
    current_status: str = "Created"
    amount: float = 0.0
    default_hourly_rate: float = 0.0
    planned_hours: float = 0.0
    planned_cost: float = 0.0
    planned_revenue_amount: float = 0.0
    planned_revenue_pct: float = 0.0
    planned_start: Optional[date] = None
    planned_end: Optional[date] = None
    percent_complete: float = 0.0
    weightage: float = 0.0
    boq_item_ids: List[str] = field(default_factory=list)
    predecessor_ids: List[str] = field(default_factory=list)
    blocked: bool = False
    block_reason: str = ""
    completion_submitted: bool = False
    progress_method: str = "percent"
    wbs_node_id: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)


@dataclass
class Project:
    project_number: str
    name: str
    customer_id: str
    customer_name: str
    contract_value: float = 0.0
    original_contract_value: float = 0.0
    revised_contract_value: float = 0.0
    contract_approved: bool = False
    advance_terms: str = ""
    dlp_months: int = 0
    project_manager: str = ""
    consultant_name: str = ""
    owner_name: str = ""
    hard_budget_check: bool = False
    physically_completed_at: Optional[datetime] = None
    status: ProjectStatus = ProjectStatus.DRAFT
    template_id: Optional[str] = None
    site_address: str = ""
    site_state_code: str = ""
    notes: str = ""
    start_date: Optional[date] = None
    expected_end_date: Optional[date] = None
    phases_enabled: bool = True
    max_activity_depth: int = 3
    billing_mode: ProjectBillingMode = ProjectBillingMode.FIXED
    retention_pct: float = 0.0
    place_of_supply_mode: PlaceOfSupplyMode = PlaceOfSupplyMode.SITE_STATE
    default_hourly_rate: float = 0.0
    parties: List[ProjectParty] = field(default_factory=list)
    phases: List[ProjectPhase] = field(default_factory=list)
    activities: List[ProjectActivity] = field(default_factory=list)
    closed_at: Optional[datetime] = None
    closed_by: str = ""
    period_locked: bool = False
    advance_gst_policy: str = ""
    overhead_allocation_pct: float = 0.0
    currency_code: str = "INR"
    final_snapshot: Optional[Dict[str, Any]] = None
    enquiry_id: str = ""
    archetype: str = "Custom"
    scale_profile: str = "Small"
    reopen_reason: str = ""
    reopened_at: Optional[datetime] = None
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass
class ProjectDocument:
    project_id: str
    category: ProjectDocumentCategory
    name: str
    content_type: str = "application/octet-stream"
    data: bytes = b""
    size_bytes: int = 0
    uploaded_by: str = ""
    source_ref_type: str = ""
    source_ref_id: str = ""
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    id: str = field(default_factory=lambda: uuid4().hex)
    uploaded_at: datetime = field(default_factory=utc_now)


@dataclass
class ProjectTimeEntry:
    project_id: str
    activity_id: str
    worker_id: str
    worker_name: str
    work_date: date
    duration_minutes: int
    hourly_rate: float
    labour_cost: float
    notes: str = ""
    batch_id: str = ""
    zero_cost_override: bool = False
    wbs_node_id: str = ""
    site_id: str = ""
    boq_item_id: str = ""
    cost_category: str = "Labour"
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass
class ProjectExpense:
    project_id: str
    expense_date: date
    expense_name: str
    expense_source: ProjectExpenseSource
    amount: float
    activity_id: Optional[str] = None
    boq_item_id: str = ""
    vendor_id: str = ""
    vendor_name: str = ""
    notes: str = ""
    purchase_voucher_id: str = ""
    wbs_node_id: str = ""
    site_id: str = ""
    cost_category: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass
class ProjectQuotationLine:
    description: str
    quantity: float = 1.0
    rate: float = 0.0
    discount_pct: float = 0.0
    hsn_sac: str = ""
    activity_id: Optional[str] = None
    boq_item_id: Optional[str] = None
    id: str = field(default_factory=lambda: uuid4().hex)

    @property
    def line_total(self) -> float:
        gross = self.quantity * self.rate
        return gross * (1 - self.discount_pct / 100.0)


@dataclass
class ProjectQuotation:
    project_id: str
    quotation_number: str
    quotation_date: date
    status: ProjectQuotationStatus = ProjectQuotationStatus.DRAFT
    customer_id: str = ""
    customer_name: str = ""
    lines: List[ProjectQuotationLine] = field(default_factory=list)
    notes: str = ""
    revision_no: int = 1
    root_id: str = ""
    supersedes_id: str = ""
    approved_by: str = ""
    approved_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    valid_until: Optional[date] = None
    confirmation_date: Optional[date] = None
    confirmation_note: str = ""
    confirmation_evidence: str = ""
    submitted_by: str = ""
    created_by: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @property
    def subtotal(self) -> float:
        return sum(line.line_total for line in self.lines)


@dataclass
class ProjectWorkOrder:
    project_id: str
    wo_number: str
    wo_date: date
    description: str = ""
    quotation_id: str = ""
    status: str = "Draft"
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)


@dataclass
class ProjectCostTransfer:
    from_project_id: str
    to_project_id: str
    amount: float
    reason: str
    from_activity_id: str = ""
    to_activity_id: str = ""
    transferred_by: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)


@dataclass
class ProjectWriteOff:
    project_id: str
    party_id: str
    amount: float
    reason: str
    voucher_id: str = ""
    written_off_by: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)


@dataclass
class ProjectProforma:
    project_id: str
    proforma_number: str
    proforma_date: date
    amount: float
    description: str = ""
    status: str = "Draft"
    lines: List[ProjectQuotationLine] = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)


@dataclass
class ProjectVariation:
    project_id: str
    variation_number: str
    variation_date: date
    old_contract_value: float
    new_contract_value: float
    reason: str
    approved_by: str = ""
    approved_at: Optional[datetime] = None
    status: str = "Draft"
    change_class: str = "Scope"
    customer_sent: bool = False
    customer_approved: bool = False
    boq_impacts: List[Dict[str, Any]] = field(default_factory=list)
    cost_impact: float = 0.0
    margin_impact: float = 0.0
    executed: bool = True
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)


@dataclass
class ProjectRetentionEntry:
    project_id: str
    invoice_voucher_id: str
    invoice_number: str
    withheld_amount: float
    released_amount: float = 0.0
    release_voucher_id: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
