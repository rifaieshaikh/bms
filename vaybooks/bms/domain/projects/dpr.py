"""Daily progress reports for project execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import ProjectDprStatus


@dataclass
class ProjectDprLine:
    activity_id: str
    quantity: float = 0.0
    hours: float = 0.0
    labour_count: int = 0
    notes: str = ""
    issues: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)


@dataclass
class ProjectDpr:
    project_id: str
    report_date: date
    weather: str = ""
    notes: str = ""
    lines: List[ProjectDprLine] = field(default_factory=list)
    photo_document_ids: List[str] = field(default_factory=list)
    status: ProjectDprStatus = ProjectDprStatus.DRAFT
    applied: bool = False
    idempotency_key: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
