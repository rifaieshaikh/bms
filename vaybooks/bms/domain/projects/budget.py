from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import ProjectBudgetStatus, ProjectCostCategory


@dataclass
class ProjectBudgetLine:
    project_id: str
    cost_category: ProjectCostCategory
    original_amount: float
    revised_amount: float
    boq_item_id: str = ""
    activity_id: str = ""
    notes: str = ""
    forecast_eac: float = 0.0
    forecast_etc: float = 0.0
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass
class ProjectBudgetHeader:
    """Per-project budget approval state (one logical budget per project)."""

    project_id: str
    status: ProjectBudgetStatus = ProjectBudgetStatus.DRAFT
    approved_at: Optional[datetime] = None
    approved_by: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass
class ProjectBudgetRevision:
    project_id: str
    reason: str
    revised_by: str = ""
    lines_snapshot: List[Dict[str, Any]] = field(default_factory=list)
    forecast_eac: float = 0.0
    forecast_etc: float = 0.0
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
