"""Procurement and site materials for projects."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import (
    ProjectMaterialOwnership,
    ProjectMaterialRequestStatus,
    ProjectRfqStatus,
    ProjectStockMovementType,
)


@dataclass
class ProjectMaterialRequestLine:
    description: str
    quantity: float
    unit: str = "Nos"
    activity_id: str = ""
    boq_item_id: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)


@dataclass
class ProjectMaterialRequest:
    project_id: str
    request_number: str
    need_by: Optional[date] = None
    lines: List[ProjectMaterialRequestLine] = field(default_factory=list)
    status: ProjectMaterialRequestStatus = ProjectMaterialRequestStatus.DRAFT
    notes: str = ""
    po_id: str = ""
    invoice_party: str = "Contractor"
    principal_agent: str = "Principal"
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass
class ProjectRfqQuote:
    vendor_id: str
    vendor_name: str
    unit_price: float
    lead_time_days: int = 0
    notes: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)


@dataclass
class ProjectRfq:
    project_id: str
    rfq_number: str
    description: str
    quantity: float = 1.0
    unit: str = "Nos"
    material_request_id: str = ""
    quotes: List[ProjectRfqQuote] = field(default_factory=list)
    awarded_quote_id: str = ""
    po_id: str = ""
    status: ProjectRfqStatus = ProjectRfqStatus.DRAFT
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass
class ProjectSiteStockMovement:
    project_id: str
    movement_type: ProjectStockMovementType
    description: str
    quantity: float
    unit: str = "Nos"
    unit_cost: float = 0.0
    activity_id: str = ""
    boq_item_id: str = ""
    ownership: ProjectMaterialOwnership = ProjectMaterialOwnership.CONTRACTOR
    invoice_party: str = "Contractor"
    principal_agent: str = "Principal"
    source_ref_type: str = ""
    source_ref_id: str = ""
    notes: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
