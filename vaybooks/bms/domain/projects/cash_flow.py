"""Project cash-flow planning domain."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now


@dataclass
class ProjectCashFlowPlan:
    project_id: str
    period_start: date
    period_end: date
    cash_in_planned: float = 0.0
    cash_out_planned: float = 0.0
    notes: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
