"""Users, memberships, permissions, and line-level allocation dimensions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import ProjectAppRole, ProjectCostCategory


# Roles that may see internal cost / margin (AC-013).
_COST_VIEWERS = {
    ProjectAppRole.OWNER,
    ProjectAppRole.ESTIMATOR,
    ProjectAppRole.COMMERCIAL_APPROVER,
    ProjectAppRole.PROJECT_MANAGER,
    ProjectAppRole.ACCOUNTANT,
    ProjectAppRole.AUDITOR,
}

# Roles that may approve commercial documents.
_COMMERCIAL_APPROVERS = {
    ProjectAppRole.OWNER,
    ProjectAppRole.COMMERCIAL_APPROVER,
    ProjectAppRole.PROJECT_MANAGER,
}


@dataclass
class ProjectAllocation:
    """Line-level project dimensions (doc §28)."""

    project_id: str = ""
    site_id: str = ""
    wbs_node_id: str = ""
    boq_item_id: str = ""
    activity_id: str = ""
    cost_category: str = ""
    branch: str = ""
    department: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "site_id": self.site_id,
            "wbs_node_id": self.wbs_node_id,
            "boq_item_id": self.boq_item_id,
            "activity_id": self.activity_id,
            "cost_category": self.cost_category,
            "branch": self.branch,
            "department": self.department,
        }

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "ProjectAllocation":
        data = data or {}
        return cls(
            project_id=(data.get("project_id") or "").strip(),
            site_id=(data.get("site_id") or "").strip(),
            wbs_node_id=(data.get("wbs_node_id") or "").strip(),
            boq_item_id=(data.get("boq_item_id") or "").strip(),
            activity_id=(data.get("activity_id") or "").strip(),
            cost_category=(data.get("cost_category") or "").strip(),
            branch=(data.get("branch") or "").strip(),
            department=(data.get("department") or "").strip(),
        )


@dataclass
class AppUser:
    username: str
    display_name: str = ""
    global_roles: List[ProjectAppRole] = field(default_factory=list)
    active: bool = True
    password_hash: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @property
    def view_internal_cost(self) -> bool:
        return any(r in _COST_VIEWERS for r in self.global_roles)

    @property
    def can_commercial_approve(self) -> bool:
        return any(r in _COMMERCIAL_APPROVERS for r in self.global_roles)


@dataclass
class ProjectMembership:
    project_id: str
    user_id: str
    role: ProjectAppRole
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)


@dataclass
class ProjectAuditEntry:
    project_id: str
    entity_type: str
    entity_id: str
    action: str
    actor_id: str = ""
    actor_name: str = ""
    reason: str = ""
    before: Optional[Dict[str, Any]] = None
    after: Optional[Dict[str, Any]] = None
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)


def normalize_cost_category(value: str | ProjectCostCategory | None) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, ProjectCostCategory):
        return value.value
    return str(value).strip()
