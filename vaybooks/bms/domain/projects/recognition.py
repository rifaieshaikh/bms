"""WIP / revenue recognition and project reconciliation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import (
    ProjectRecognitionMethod,
    ProjectRecognitionStatus,
    ProjectReconcileStatus,
)


@dataclass
class ProjectRecognitionEntry:
    project_id: str
    period_end: date
    method: ProjectRecognitionMethod
    percent_complete: float = 0.0
    total_cost: float = 0.0
    billed_to_date: float = 0.0
    prior_recognised: float = 0.0
    current_recognised: float = 0.0
    wip_adjustment: float = 0.0
    unbilled_revenue: float = 0.0
    deferred_revenue: float = 0.0
    status: ProjectRecognitionStatus = ProjectRecognitionStatus.DRAFT
    voucher_id: str = ""
    journal_stub: Optional[Dict[str, Any]] = None
    notes: str = ""
    idempotency_key: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass
class ProjectReconcileException:
    category: str
    description: str
    amount: float = 0.0
    source_ref: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)


@dataclass
class ProjectReconciliation:
    project_id: str
    as_of: date
    project_subledger: float = 0.0
    gl_balance: float = 0.0
    ar_balance: float = 0.0
    ap_balance: float = 0.0
    exceptions: List[ProjectReconcileException] = field(default_factory=list)
    status: ProjectReconcileStatus = ProjectReconcileStatus.DRAFT
    signed_off_by: str = ""
    signed_off_at: datetime | None = None
    notes: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
