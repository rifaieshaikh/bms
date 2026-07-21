"""Subcontract work orders and settlement."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import ProjectSubcontractStatus


@dataclass
class ProjectSubcontractLine:
    description: str
    quantity: float
    rate: float
    unit: str = "Nos"
    boq_item_id: str = ""
    measured_qty: float = 0.0
    certified_qty: float = 0.0
    settled_qty: float = 0.0
    id: str = field(default_factory=lambda: uuid4().hex)

    @property
    def amount(self) -> float:
        return self.quantity * self.rate


@dataclass
class ProjectSubcontractOrder:
    project_id: str
    order_number: str
    vendor_id: str
    vendor_name: str
    order_date: date
    description: str = ""
    retention_pct: float = 0.0
    lines: List[ProjectSubcontractLine] = field(default_factory=list)
    status: ProjectSubcontractStatus = ProjectSubcontractStatus.DRAFT
    notes: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @property
    def contract_value(self) -> float:
        return sum(line.amount for line in self.lines)
