from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.projects.budget import (
    ProjectBudgetHeader,
    ProjectBudgetLine,
    ProjectBudgetRevision,
)
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import ProjectBudgetStatus, ProjectCostCategory


class MongoProjectBudgetRepository:
    def __init__(self, db: Database):
        self._lines = db.project_budget_lines
        self._revisions = db.project_budget_revisions
        self._headers = db.project_budget_headers

    def _line_to_doc(self, line: ProjectBudgetLine) -> dict:
        return {
            "_id": line.id,
            "project_id": line.project_id,
            "cost_category": line.cost_category.value,
            "original_amount": float(line.original_amount or 0.0),
            "revised_amount": float(line.revised_amount or 0.0),
            "boq_item_id": line.boq_item_id,
            "activity_id": line.activity_id,
            "notes": line.notes,
            "forecast_eac": float(line.forecast_eac or 0.0),
            "forecast_etc": float(line.forecast_etc or 0.0),
            "created_at": line.created_at,
            "updated_at": line.updated_at,
        }

    def _line_from_doc(self, doc: dict) -> ProjectBudgetLine:
        return ProjectBudgetLine(
            id=doc["_id"],
            project_id=doc["project_id"],
            cost_category=ProjectCostCategory(
                doc.get("cost_category", ProjectCostCategory.OTHER.value)
            ),
            original_amount=float(doc.get("original_amount") or 0.0),
            revised_amount=float(doc.get("revised_amount") or 0.0),
            boq_item_id=doc.get("boq_item_id", ""),
            activity_id=doc.get("activity_id", ""),
            notes=doc.get("notes", ""),
            forecast_eac=float(doc.get("forecast_eac") or 0.0),
            forecast_etc=float(doc.get("forecast_etc") or 0.0),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def _revision_to_doc(self, revision: ProjectBudgetRevision) -> dict:
        return {
            "_id": revision.id,
            "project_id": revision.project_id,
            "reason": revision.reason,
            "revised_by": revision.revised_by,
            "lines_snapshot": list(revision.lines_snapshot or []),
            "forecast_eac": float(revision.forecast_eac or 0.0),
            "forecast_etc": float(revision.forecast_etc or 0.0),
            "created_at": revision.created_at,
        }

    def _revision_from_doc(self, doc: dict) -> ProjectBudgetRevision:
        return ProjectBudgetRevision(
            id=doc["_id"],
            project_id=doc["project_id"],
            reason=doc.get("reason", ""),
            revised_by=doc.get("revised_by", ""),
            lines_snapshot=list(doc.get("lines_snapshot") or []),
            forecast_eac=float(doc.get("forecast_eac") or 0.0),
            forecast_etc=float(doc.get("forecast_etc") or 0.0),
            created_at=doc.get("created_at", datetime.utcnow()),
        )

    def _header_to_doc(self, header: ProjectBudgetHeader) -> dict:
        return {
            "_id": header.id,
            "project_id": header.project_id,
            "status": header.status.value,
            "approved_at": header.approved_at,
            "approved_by": header.approved_by,
            "created_at": header.created_at,
            "updated_at": header.updated_at,
        }

    def _header_from_doc(self, doc: dict) -> ProjectBudgetHeader:
        return ProjectBudgetHeader(
            id=doc["_id"],
            project_id=doc["project_id"],
            status=ProjectBudgetStatus(
                doc.get("status", ProjectBudgetStatus.DRAFT.value)
            ),
            approved_at=doc.get("approved_at"),
            approved_by=doc.get("approved_by", ""),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save_line(self, line: ProjectBudgetLine) -> ProjectBudgetLine:
        self._lines.replace_one({"_id": line.id}, self._line_to_doc(line), upsert=True)
        return line

    def save_lines(self, lines: List[ProjectBudgetLine]) -> List[ProjectBudgetLine]:
        for line in lines:
            self.save_line(line)
        return lines

    def find_line_by_id(self, line_id: str) -> Optional[ProjectBudgetLine]:
        doc = self._lines.find_one({"_id": line_id})
        return self._line_from_doc(doc) if doc else None

    def list_lines_by_project(self, project_id: str) -> List[ProjectBudgetLine]:
        docs = self._lines.find({"project_id": project_id})
        return [self._line_from_doc(d) for d in docs]

    def save_revision(self, revision: ProjectBudgetRevision) -> ProjectBudgetRevision:
        self._revisions.replace_one(
            {"_id": revision.id}, self._revision_to_doc(revision), upsert=True
        )
        return revision

    def list_revisions_by_project(self, project_id: str) -> List[ProjectBudgetRevision]:
        docs = self._revisions.find({"project_id": project_id}).sort("created_at", -1)
        return [self._revision_from_doc(d) for d in docs]

    def save_header(self, header: ProjectBudgetHeader) -> ProjectBudgetHeader:
        header.updated_at = utc_now()
        self._headers.replace_one(
            {"_id": header.id}, self._header_to_doc(header), upsert=True
        )
        return header

    def find_header_by_project(self, project_id: str) -> Optional[ProjectBudgetHeader]:
        doc = self._headers.find_one({"project_id": project_id})
        return self._header_from_doc(doc) if doc else None
