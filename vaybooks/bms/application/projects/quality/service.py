from __future__ import annotations

from datetime import date
from typing import List, Optional
from uuid import uuid4

from vaybooks.bms.domain.projects.quality_config import (
    ProjectConfigSnapshot,
    ProjectHandover,
    ProjectHandoverItem,
    ProjectQualityIssue,
    ProjectWbsNode,
)
from vaybooks.bms.domain.shared.date_utils import today, utc_now
from vaybooks.bms.domain.shared.enums import (
    ProjectArchetype,
    ProjectQualityIssueStatus,
    ProjectQualityIssueType,
    ProjectStatus,
    ProjectScaleProfile,
    ProjectWbsNodeType,
)
from vaybooks.bms.domain.shared.exceptions import ValidationError


class ProjectQualityConfigAppService:
    def __init__(self, quality_repo, project_repo, project_service=None):
        self._repo = quality_repo
        self._project_repo = project_repo
        self._project_service = project_service

    def _get_project(self, project_id: str):
        project = self._project_repo.find_by_id(project_id)
        if not project:
            raise ValidationError("Project not found")
        return project

    def _maybe_enter_dlp(self, project_id: str, handover: ProjectHandover) -> None:
        if not handover.is_complete:
            return
        project = self._get_project(project_id)
        if int(getattr(project, "dlp_months", 0) or 0) <= 0:
            return
        if project.status == ProjectStatus.DLP:
            return
        if self._project_service and hasattr(self._project_service, "mark_dlp"):
            try:
                self._project_service.mark_dlp(project_id)
                return
            except ValidationError:
                # Fall through to direct status update when mark_dlp preconditions fail.
                pass
        if project.status in (
            ProjectStatus.ACTIVE,
            ProjectStatus.PHYSICALLY_COMPLETED,
        ):
            project.status = ProjectStatus.DLP
            project.updated_at = utc_now()
            self._project_repo.save(project)

    def create_quality_issue(
        self,
        project_id: str,
        title: str,
        *,
        issue_type=ProjectQualityIssueType.SNAG,
        activity_id: str = "",
        location: str = "",
        description: str = "",
        cost_impact: float = 0.0,
        is_rework_cost: Optional[bool] = None,
        raised_date: Optional[date] = None,
    ) -> ProjectQualityIssue:
        self._get_project(project_id)
        if not (title or "").strip():
            raise ValidationError("Quality issue title is required")
        if isinstance(issue_type, str):
            issue_type = ProjectQualityIssueType(issue_type)
        if is_rework_cost is None:
            is_rework_cost = issue_type == ProjectQualityIssueType.REWORK
        issue = ProjectQualityIssue(
            project_id=project_id,
            title=(title or "").strip(),
            issue_type=issue_type,
            activity_id=(activity_id or "").strip(),
            location=(location or "").strip(),
            description=(description or "").strip(),
            cost_impact=float(cost_impact or 0.0),
            is_rework_cost=bool(is_rework_cost),
            raised_date=raised_date or today(),
        )
        return self._repo.save_quality_issue(issue)

    def update_quality_issue(self, issue_id: str, **fields) -> ProjectQualityIssue:
        issue = self._repo.find_quality_issue_by_id(issue_id)
        if not issue:
            raise ValidationError("Quality issue not found")
        if "title" in fields:
            title = (fields["title"] or "").strip()
            if not title:
                raise ValidationError("Quality issue title is required")
            issue.title = title
        if "status" in fields:
            status = fields["status"]
            if isinstance(status, str):
                status = ProjectQualityIssueStatus(status)
            issue.status = status
            if status in (
                ProjectQualityIssueStatus.RESOLVED,
                ProjectQualityIssueStatus.CLOSED,
            ) and not issue.resolved_date:
                issue.resolved_date = today()
        if "description" in fields:
            issue.description = (fields["description"] or "").strip()
        if "location" in fields:
            issue.location = (fields["location"] or "").strip()
        if "cost_impact" in fields:
            issue.cost_impact = float(fields["cost_impact"] or 0.0)
        if "is_rework_cost" in fields:
            issue.is_rework_cost = bool(fields["is_rework_cost"])
        if "activity_id" in fields:
            issue.activity_id = (fields["activity_id"] or "").strip()
        issue.updated_at = utc_now()
        return self._repo.save_quality_issue(issue)

    def list_quality_issues(self, project_id: str) -> List[ProjectQualityIssue]:
        self._get_project(project_id)
        return self._repo.list_quality_issues_by_project(project_id)

    def get_or_create_handover(self, project_id: str) -> ProjectHandover:
        self._get_project(project_id)
        existing = self._repo.find_handover_by_project(project_id)
        if existing:
            return existing
        handover = ProjectHandover(project_id=project_id)
        return self._repo.save_handover(handover)

    def set_handover_checklist(
        self, project_id: str, items: List[dict]
    ) -> ProjectHandover:
        handover = self.get_or_create_handover(project_id)
        checklist: List[ProjectHandoverItem] = []
        for row in items or []:
            label = (row.get("label") or "").strip()
            if not label:
                continue
            checklist.append(
                ProjectHandoverItem(
                    label=label,
                    completed=bool(row.get("completed", False)),
                    document_id=(row.get("document_id") or "").strip(),
                    id=(row.get("id") or uuid4().hex),
                )
            )
        handover.checklist = checklist
        if handover.is_complete:
            handover.completed_at = handover.completed_at or utc_now()
        else:
            handover.completed_at = None
        handover.updated_at = utc_now()
        saved = self._repo.save_handover(handover)
        self._maybe_enter_dlp(project_id, saved)
        return saved

    def complete_handover_item(
        self, project_id: str, item_id: str, completed: bool = True, document_id: str = ""
    ) -> ProjectHandover:
        handover = self.get_or_create_handover(project_id)
        item = next((i for i in handover.checklist if i.id == item_id), None)
        if not item:
            raise ValidationError("Handover item not found")
        item.completed = bool(completed)
        if document_id:
            item.document_id = document_id
        if handover.is_complete:
            handover.completed_at = utc_now()
        else:
            handover.completed_at = None
        handover.updated_at = utc_now()
        saved = self._repo.save_handover(handover)
        self._maybe_enter_dlp(project_id, saved)
        return saved

    def add_wbs_node(
        self,
        project_id: str,
        name: str,
        node_type,
        *,
        code: str = "",
        parent_id: Optional[str] = None,
        manager: str = "",
        sort_order: int = 0,
    ) -> ProjectWbsNode:
        self._get_project(project_id)
        if not (name or "").strip():
            raise ValidationError("WBS node name is required")
        if isinstance(node_type, str):
            node_type = ProjectWbsNodeType(node_type)
        nodes = self._repo.list_wbs_nodes_by_project(project_id)
        by_id = {n.id: n for n in nodes}
        if parent_id:
            if parent_id not in by_id:
                raise ValidationError("Parent WBS node not found")
            # cycle check: walk ancestors
            seen = set()
            cursor = parent_id
            while cursor:
                if cursor in seen:
                    raise ValidationError("WBS parent creates a cycle")
                seen.add(cursor)
                parent = by_id.get(cursor)
                cursor = parent.parent_id if parent else None
        node = ProjectWbsNode(
            project_id=project_id,
            name=(name or "").strip(),
            node_type=node_type,
            code=(code or "").strip(),
            parent_id=parent_id,
            manager=(manager or "").strip(),
            sort_order=int(sort_order or 0),
        )
        # also reject if new node id somehow equals ancestor (impossible on create)
        return self._repo.save_wbs_node(node)

    def list_wbs_nodes(self, project_id: str) -> List[ProjectWbsNode]:
        self._get_project(project_id)
        return self._repo.list_wbs_nodes_by_project(project_id)

    def publish_config_snapshot(
        self,
        project_id: str,
        *,
        archetype=ProjectArchetype.CUSTOM,
        scale=ProjectScaleProfile.SMALL,
        modules: Optional[List[str]] = None,
        workflow: Optional[dict] = None,
        phases_template: Optional[List[str]] = None,
        change_reason: str = "",
    ) -> ProjectConfigSnapshot:
        self._get_project(project_id)
        if isinstance(archetype, str):
            archetype = ProjectArchetype(archetype)
        if isinstance(scale, str):
            scale = ProjectScaleProfile(scale)
        existing = self._repo.list_config_snapshots_by_project(project_id)
        revision = (max((s.revision for s in existing), default=0) + 1)
        snapshot = ProjectConfigSnapshot(
            project_id=project_id,
            revision=revision,
            archetype=archetype,
            scale=scale,
            modules=list(modules or []),
            workflow=dict(workflow or {}),
            phases_template=list(phases_template or []),
            published=True,
            change_reason=(change_reason or "").strip(),
        )
        return self._repo.save_config_snapshot(snapshot)

    def list_config_snapshots(self, project_id: str) -> List[ProjectConfigSnapshot]:
        self._get_project(project_id)
        return self._repo.list_config_snapshots_by_project(project_id)

    def compose_hybrid(
        self,
        project_id: str,
        base_snapshot_id: str,
        extra_phases: List[str],
        *,
        change_reason: str = "Hybrid compose",
    ) -> ProjectConfigSnapshot:
        base = self._repo.find_config_snapshot_by_id(base_snapshot_id)
        if not base or base.project_id != project_id:
            raise ValidationError("Base config snapshot not found")
        phases = list(base.phases_template or [])
        for phase in extra_phases or []:
            name = (phase or "").strip()
            if name and name not in phases:
                phases.append(name)
        return self.publish_config_snapshot(
            project_id,
            archetype=base.archetype,
            scale=base.scale,
            modules=list(base.modules or []),
            workflow=dict(base.workflow or {}),
            phases_template=phases,
            change_reason=change_reason,
        )
