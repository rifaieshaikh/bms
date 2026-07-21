from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import ProjectBoqItemType


@dataclass
class ProjectBoqItem:
    project_id: str
    code: str
    description: str
    item_type: ProjectBoqItemType = ProjectBoqItemType.ITEM
    parent_id: Optional[str] = None
    unit: str = "Nos"
    sort_order: int = 0
    estimated_qty: float = 0.0
    material_cost: float = 0.0
    labour_cost: float = 0.0
    equipment_cost: float = 0.0
    subcon_cost: float = 0.0
    overhead_cost: float = 0.0
    contingency_cost: float = 0.0
    selling_rate: float = 0.0
    hsn_sac: str = ""
    contracted_qty: float = 0.0
    contracted_rate: float = 0.0
    varied_qty: float = 0.0
    executed_qty: float = 0.0
    measured_qty: float = 0.0
    certified_qty: float = 0.0
    billed_qty: float = 0.0
    rate_override_reason: str = ""
    activity_id: Optional[str] = None
    phase_id: Optional[str] = None
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @property
    def estimated_cost(self) -> float:
        return (
            self.material_cost
            + self.labour_cost
            + self.equipment_cost
            + self.subcon_cost
            + self.overhead_cost
            + self.contingency_cost
        )

    @property
    def estimated_value(self) -> float:
        return self.estimated_qty * self.selling_rate

    @property
    def balance_qty(self) -> float:
        return self.contracted_qty + self.varied_qty - self.billed_qty
