from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.projects.quality_config import (
    ProjectConfigSnapshot,
    ProjectHandover,
    ProjectHandoverItem,
    ProjectQualityIssue,
    ProjectWbsNode,
)
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import (
    ProjectArchetype,
    ProjectQualityIssueStatus,
    ProjectQualityIssueType,
    ProjectScaleProfile,
    ProjectWbsNodeType,
)
from vaybooks.bms.infrastructure.db.bson_utils import from_bson_date, to_bson_value


class MongoProjectQualityConfigRepository:
    def __init__(self, db: Database):
        self._issues = db.project_quality_issues
        self._handovers = db.project_handovers
        self._wbs = db.project_wbs_nodes
        self._snapshots = db.project_config_snapshots

    def _issue_to_doc(self, issue: ProjectQualityIssue) -> dict:
        return {
            "_id": issue.id,
            "project_id": issue.project_id,
            "title": issue.title,
            "issue_type": issue.issue_type.value,
            "status": issue.status.value,
            "activity_id": issue.activity_id,
            "location": issue.location,
            "description": issue.description,
            "cost_impact": float(issue.cost_impact or 0.0),
            "is_rework_cost": bool(issue.is_rework_cost),
            "raised_date": to_bson_value(issue.raised_date),
            "resolved_date": to_bson_value(issue.resolved_date),
            "created_at": issue.created_at,
            "updated_at": issue.updated_at,
        }

    def _issue_from_doc(self, doc: dict) -> ProjectQualityIssue:
        return ProjectQualityIssue(
            id=doc["_id"],
            project_id=doc["project_id"],
            title=doc.get("title", ""),
            issue_type=ProjectQualityIssueType(
                doc.get("issue_type", ProjectQualityIssueType.SNAG.value)
            ),
            status=ProjectQualityIssueStatus(
                doc.get("status", ProjectQualityIssueStatus.OPEN.value)
            ),
            activity_id=doc.get("activity_id", ""),
            location=doc.get("location", ""),
            description=doc.get("description", ""),
            cost_impact=float(doc.get("cost_impact") or 0.0),
            is_rework_cost=bool(doc.get("is_rework_cost", False)),
            raised_date=from_bson_date(doc.get("raised_date")),
            resolved_date=from_bson_date(doc.get("resolved_date")),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def _handover_item_to_doc(self, item: ProjectHandoverItem) -> dict:
        return {
            "id": item.id,
            "label": item.label,
            "completed": bool(item.completed),
            "document_id": item.document_id,
        }

    def _handover_item_from_doc(self, doc: dict) -> ProjectHandoverItem:
        return ProjectHandoverItem(
            id=doc.get("id", ""),
            label=doc.get("label", ""),
            completed=bool(doc.get("completed", False)),
            document_id=doc.get("document_id", ""),
        )

    def _handover_to_doc(self, handover: ProjectHandover) -> dict:
        return {
            "_id": handover.id,
            "project_id": handover.project_id,
            "checklist": [self._handover_item_to_doc(i) for i in handover.checklist],
            "completed_at": handover.completed_at,
            "completed_by": handover.completed_by,
            "notes": handover.notes,
            "created_at": handover.created_at,
            "updated_at": handover.updated_at,
        }

    def _handover_from_doc(self, doc: dict) -> ProjectHandover:
        return ProjectHandover(
            id=doc["_id"],
            project_id=doc["project_id"],
            checklist=[
                self._handover_item_from_doc(i) for i in doc.get("checklist", [])
            ],
            completed_at=doc.get("completed_at"),
            completed_by=doc.get("completed_by", ""),
            notes=doc.get("notes", ""),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def _wbs_to_doc(self, node: ProjectWbsNode) -> dict:
        return {
            "_id": node.id,
            "project_id": node.project_id,
            "name": node.name,
            "node_type": node.node_type.value,
            "code": node.code,
            "parent_id": node.parent_id,
            "manager": node.manager,
            "sort_order": int(node.sort_order or 0),
            "created_at": node.created_at,
            "updated_at": node.updated_at,
        }

    def _wbs_from_doc(self, doc: dict) -> ProjectWbsNode:
        return ProjectWbsNode(
            id=doc["_id"],
            project_id=doc["project_id"],
            name=doc.get("name", ""),
            node_type=ProjectWbsNodeType(
                doc.get("node_type", ProjectWbsNodeType.PHASE.value)
            ),
            code=doc.get("code", ""),
            parent_id=doc.get("parent_id"),
            manager=doc.get("manager", ""),
            sort_order=int(doc.get("sort_order") or 0),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def _snapshot_to_doc(self, snapshot: ProjectConfigSnapshot) -> dict:
        return {
            "_id": snapshot.id,
            "project_id": snapshot.project_id,
            "revision": int(snapshot.revision or 0),
            "archetype": snapshot.archetype.value,
            "scale": snapshot.scale.value,
            "modules": list(snapshot.modules or []),
            "workflow": dict(snapshot.workflow or {}),
            "phases_template": list(snapshot.phases_template or []),
            "published": bool(snapshot.published),
            "change_reason": snapshot.change_reason,
            "created_at": snapshot.created_at,
        }

    def _snapshot_from_doc(self, doc: dict) -> ProjectConfigSnapshot:
        return ProjectConfigSnapshot(
            id=doc["_id"],
            project_id=doc["project_id"],
            revision=int(doc.get("revision") or 0),
            archetype=ProjectArchetype(
                doc.get("archetype", ProjectArchetype.CUSTOM.value)
            ),
            scale=ProjectScaleProfile(
                doc.get("scale", ProjectScaleProfile.SMALL.value)
            ),
            modules=list(doc.get("modules") or []),
            workflow=dict(doc.get("workflow") or {}),
            phases_template=list(doc.get("phases_template") or []),
            published=bool(doc.get("published", True)),
            change_reason=doc.get("change_reason", ""),
            created_at=doc.get("created_at", datetime.utcnow()),
        )

    def save_quality_issue(self, issue: ProjectQualityIssue) -> ProjectQualityIssue:
        issue.updated_at = utc_now()
        self._issues.replace_one(
            {"_id": issue.id}, self._issue_to_doc(issue), upsert=True
        )
        return issue

    def find_quality_issue_by_id(
        self, issue_id: str
    ) -> Optional[ProjectQualityIssue]:
        doc = self._issues.find_one({"_id": issue_id})
        return self._issue_from_doc(doc) if doc else None

    def list_quality_issues_by_project(
        self, project_id: str
    ) -> List[ProjectQualityIssue]:
        docs = self._issues.find({"project_id": project_id}).sort("created_at", -1)
        return [self._issue_from_doc(d) for d in docs]

    def save_handover(self, handover: ProjectHandover) -> ProjectHandover:
        handover.updated_at = utc_now()
        self._handovers.replace_one(
            {"_id": handover.id}, self._handover_to_doc(handover), upsert=True
        )
        return handover

    def find_handover_by_project(self, project_id: str) -> Optional[ProjectHandover]:
        doc = self._handovers.find_one({"project_id": project_id})
        return self._handover_from_doc(doc) if doc else None

    def find_handover_by_id(self, handover_id: str) -> Optional[ProjectHandover]:
        doc = self._handovers.find_one({"_id": handover_id})
        return self._handover_from_doc(doc) if doc else None

    def save_wbs_node(self, node: ProjectWbsNode) -> ProjectWbsNode:
        node.updated_at = utc_now()
        self._wbs.replace_one({"_id": node.id}, self._wbs_to_doc(node), upsert=True)
        return node

    def find_wbs_node_by_id(self, node_id: str) -> Optional[ProjectWbsNode]:
        doc = self._wbs.find_one({"_id": node_id})
        return self._wbs_from_doc(doc) if doc else None

    def list_wbs_nodes_by_project(self, project_id: str) -> List[ProjectWbsNode]:
        docs = self._wbs.find({"project_id": project_id}).sort(
            [("sort_order", 1), ("name", 1)]
        )
        return [self._wbs_from_doc(d) for d in docs]

    def save_config_snapshot(
        self, snapshot: ProjectConfigSnapshot
    ) -> ProjectConfigSnapshot:
        self._snapshots.replace_one(
            {"_id": snapshot.id}, self._snapshot_to_doc(snapshot), upsert=True
        )
        return snapshot

    def find_config_snapshot_by_id(
        self, snapshot_id: str
    ) -> Optional[ProjectConfigSnapshot]:
        doc = self._snapshots.find_one({"_id": snapshot_id})
        return self._snapshot_from_doc(doc) if doc else None

    def list_config_snapshots_by_project(
        self, project_id: str
    ) -> List[ProjectConfigSnapshot]:
        docs = self._snapshots.find({"project_id": project_id}).sort("revision", -1)
        return [self._snapshot_from_doc(d) for d in docs]
