from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import ProjectMeasurementStatus, ProjectRABillStatus


@dataclass
class ProjectMeasurement:
    project_id: str
    boq_item_id: str
    measurement_date: date
    location: str = ""
    dimensions: str = ""
    quantity: float = 0.0
    cumulative_quantity: float = 0.0
    status: ProjectMeasurementStatus = ProjectMeasurementStatus.DRAFT
    override_qty_cap: bool = False
    override_reason: str = ""
    ra_bill_id: str = ""
    notes: str = ""
    verified_by: str = ""
    certified_by: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass
class ProjectRABillLine:
    boq_item_id: str
    description: str = ""
    unit: str = ""
    previous_qty: float = 0.0
    current_claimed_qty: float = 0.0
    cumulative_claimed_qty: float = 0.0
    current_certified_qty: float = 0.0
    cumulative_certified_qty: float = 0.0
    rate: float = 0.0
    measurement_ids: List[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid4().hex)

    @property
    def claimed_value(self) -> float:
        return self.current_claimed_qty * self.rate

    @property
    def certified_value(self) -> float:
        return self.current_certified_qty * self.rate


@dataclass
class ProjectRABill:
    project_id: str
    ra_number: str
    ra_date: date
    status: ProjectRABillStatus = ProjectRABillStatus.DRAFT
    lines: List[ProjectRABillLine] = field(default_factory=list)
    advance_recovery: float = 0.0
    retention_pct: float = 0.0
    retention_amount_claimed: float = 0.0
    retention_amount_certified: float = 0.0
    tds_amount: float = 0.0
    other_deductions: float = 0.0
    description: str = ""
    work_order_id: str = ""
    invoice_voucher_id: str = ""
    claimed_by: str = ""
    certified_by: str = ""
    certified_at: Optional[datetime] = None
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @property
    def gross_claimed(self) -> float:
        return sum(line.claimed_value for line in self.lines)

    @property
    def gross_certified(self) -> float:
        return sum(line.certified_value for line in self.lines)

    @property
    def net_claimed(self) -> float:
        return (
            self.gross_claimed
            - self.advance_recovery
            - self.retention_amount_claimed
            - self.tds_amount
            - self.other_deductions
        )

    @property
    def net_certified(self) -> float:
        return (
            self.gross_certified
            - self.advance_recovery
            - self.retention_amount_certified
            - self.tds_amount
            - self.other_deductions
        )
