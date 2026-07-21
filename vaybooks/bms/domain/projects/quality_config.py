"""Quality issues, handover, WBS nodes, and project configuration snapshots."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import (
    ProjectArchetype,
    ProjectQualityIssueStatus,
    ProjectQualityIssueType,
    ProjectScaleProfile,
    ProjectWbsNodeType,
)


@dataclass
class ProjectQualityIssue:
    project_id: str
    title: str
    issue_type: ProjectQualityIssueType = ProjectQualityIssueType.SNAG
    status: ProjectQualityIssueStatus = ProjectQualityIssueStatus.OPEN
    activity_id: str = ""
    location: str = ""
    description: str = ""
    cost_impact: float = 0.0
    is_rework_cost: bool = False
    raised_date: Optional[date] = None
    resolved_date: Optional[date] = None
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass
class ProjectHandoverItem:
    label: str
    completed: bool = False
    document_id: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)


@dataclass
class ProjectHandover:
    project_id: str
    checklist: List[ProjectHandoverItem] = field(default_factory=list)
    completed_at: Optional[datetime] = None
    completed_by: str = ""
    notes: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @property
    def is_complete(self) -> bool:
        return bool(self.checklist) and all(item.completed for item in self.checklist)


@dataclass
class ProjectWbsNode:
    project_id: str
    name: str
    node_type: ProjectWbsNodeType
    code: str = ""
    parent_id: Optional[str] = None
    manager: str = ""
    sort_order: int = 0
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass
class ProjectConfigSnapshot:
    project_id: str
    revision: int
    archetype: ProjectArchetype = ProjectArchetype.CUSTOM
    scale: ProjectScaleProfile = ProjectScaleProfile.SMALL
    modules: List[str] = field(default_factory=list)
    workflow: Dict[str, Any] = field(default_factory=dict)
    phases_template: List[str] = field(default_factory=list)
    published: bool = True
    change_reason: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
