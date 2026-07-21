from __future__ import annotations

from datetime import date
from typing import List, Optional
from uuid import uuid4

from vaybooks.bms.domain.projects.entities import ProjectTimeEntry
from vaybooks.bms.domain.projects.repository import (
    ProjectRepository,
    ProjectTimeEntryRepository,
)
from vaybooks.bms.domain.projects.services import ProjectDomainService
from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.domain.shared.enums import ProjectStatus
from vaybooks.bms.domain.workers.repository import WorkerRepository


class ProjectTimeAppService:
    def __init__(
        self,
        time_repo: ProjectTimeEntryRepository,
        project_repo: ProjectRepository,
        worker_repo: WorkerRepository,
    ):
        self._time_repo = time_repo
        self._project_repo = project_repo
        self._worker_repo = worker_repo
        self._domain = ProjectDomainService()

    def _get_project(self, project_id: str):
        project = self._project_repo.find_by_id(project_id)
        if not project:
            raise ValidationError("Project not found")
        return project

    def create_time_entries(
        self,
        project_id: str,
        activity_id: str,
        worker_rows: List[dict],
        work_date: date,
        notes: str = "",
    ) -> List[ProjectTimeEntry]:
        if not worker_rows:
            raise ValidationError("At least one worker row is required")
        project = self._get_project(project_id)
        if project.status == ProjectStatus.FINANCIALLY_CLOSED:
            raise ValidationError("Project is closed; time entries cannot be added")
        enriched_rows: List[dict] = []
        for row in worker_rows:
            worker_id = row.get("worker_id", "")
            worker = self._worker_repo.find_by_id(worker_id) if worker_id else None
            if worker_id and not worker:
                raise ValidationError("Worker not found")
            enriched_rows.append(
                {
                    **row,
                    "worker_name": row.get("worker_name")
                    or (worker.worker_name if worker else ""),
                    "worker_rate": row.get("worker_rate")
                    if row.get("worker_rate") is not None
                    else (worker.default_hourly_rate if worker else 0.0),
                }
            )
        entries = self._domain.build_time_entries(
            project=project,
            activity_id=activity_id,
            worker_rows=enriched_rows,
            work_date=work_date,
            notes=(notes or "").strip(),
            batch_id=uuid4().hex,
        )
        return self._time_repo.save_many(entries)

    def list_by_project(self, project_id: str) -> List[ProjectTimeEntry]:
        return self._time_repo.list_by_project(project_id)

    def list_by_activity(self, activity_id: str) -> List[ProjectTimeEntry]:
        return self._time_repo.list_by_activity(activity_id)

    def get_entry(self, entry_id: str) -> Optional[ProjectTimeEntry]:
        return self._time_repo.find_by_id(entry_id)

    def delete_time_entry(self, entry_id: str) -> None:
        if not self._time_repo.find_by_id(entry_id):
            raise ValidationError("Time entry not found")
        self._time_repo.delete(entry_id)
