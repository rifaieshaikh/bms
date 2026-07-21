"""Daily progress report application service."""

from __future__ import annotations

from datetime import date
from typing import List, Optional
from uuid import uuid4

from vaybooks.bms.domain.projects.dpr import ProjectDpr, ProjectDprLine
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import ProjectActivityStatus, ProjectDprStatus
from vaybooks.bms.domain.shared.exceptions import ValidationError


class ProjectDprAppService:
    def __init__(self, dpr_repo, project_repo):
        self._dpr_repo = dpr_repo
        self._project_repo = project_repo

    def _get_project(self, project_id: str):
        project = self._project_repo.find_by_id(project_id)
        if not project:
            raise ValidationError("Project not found")
        return project

    def create_dpr(
        self,
        project_id: str,
        report_date: date,
        *,
        weather: str = "",
        notes: str = "",
        lines: Optional[List[dict]] = None,
        photo_document_ids: Optional[List[str]] = None,
    ) -> ProjectDpr:
        self._get_project(project_id)
        dpr_lines = [
            ProjectDprLine(
                activity_id=row.get("activity_id", ""),
                quantity=float(row.get("quantity") or 0),
                hours=float(row.get("hours") or 0),
                labour_count=int(row.get("labour_count") or 0),
                notes=(row.get("notes") or "").strip(),
                issues=(row.get("issues") or "").strip(),
            )
            for row in (lines or [])
            if row.get("activity_id")
        ]
        photos = [
            str(doc_id).strip()
            for doc_id in (photo_document_ids or [])
            if str(doc_id).strip()
        ]
        dpr = ProjectDpr(
            project_id=project_id,
            report_date=report_date,
            weather=(weather or "").strip(),
            notes=(notes or "").strip(),
            lines=dpr_lines,
            photo_document_ids=photos,
            idempotency_key=f"{project_id}:{report_date.isoformat()}:{uuid4().hex[:8]}",
        )
        return self._dpr_repo.save(dpr)

    def list_dprs(self, project_id: str) -> List[ProjectDpr]:
        self._get_project(project_id)
        return self._dpr_repo.list_by_project(project_id)

    def submit(self, dpr_id: str) -> ProjectDpr:
        dpr = self._dpr_repo.find_by_id(dpr_id)
        if not dpr:
            raise ValidationError("DPR not found")
        dpr.status = ProjectDprStatus.SUBMITTED
        dpr.updated_at = utc_now()
        return self._dpr_repo.save(dpr)

    def approve_and_apply(self, dpr_id: str) -> ProjectDpr:
        dpr = self._dpr_repo.find_by_id(dpr_id)
        if not dpr:
            raise ValidationError("DPR not found")
        if dpr.applied:
            return dpr
        project = self._get_project(dpr.project_id)
        by_id = {a.id: a for a in project.activities}
        for line in dpr.lines:
            activity = by_id.get(line.activity_id)
            if not activity:
                continue
            if line.quantity > 0 and activity.progress_method == "quantity":
                activity.percent_complete = min(
                    100.0, float(activity.percent_complete or 0) + float(line.quantity)
                )
            elif line.hours > 0:
                planned = float(activity.planned_hours or 0) or 1.0
                activity.percent_complete = min(
                    100.0,
                    float(activity.percent_complete or 0)
                    + (float(line.hours) / planned) * 100.0,
                )
            else:
                activity.percent_complete = min(
                    100.0, max(float(activity.percent_complete or 0), 1.0)
                )
            if activity.percent_complete >= 100:
                activity.status = ProjectActivityStatus.COMPLETED
                activity.current_status = "Completed"
            elif activity.percent_complete > 0:
                activity.status = ProjectActivityStatus.IN_PROGRESS
        project.updated_at = utc_now()
        self._project_repo.save(project)
        dpr.status = ProjectDprStatus.APPROVED
        dpr.applied = True
        dpr.updated_at = utc_now()
        return self._dpr_repo.save(dpr)
