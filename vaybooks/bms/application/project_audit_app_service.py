"""Project audit / history trail (Wave 1 History tab)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from vaybooks.bms.domain.projects.access import ProjectAuditEntry


class ProjectAuditAppService:
    def __init__(self, audit_repo):
        self._repo = audit_repo

    def record(
        self,
        project_id: str,
        entity_type: str,
        entity_id: str,
        action: str,
        *,
        actor_id: str = "",
        actor_name: str = "",
        reason: str = "",
        before: Optional[Dict[str, Any]] = None,
        after: Optional[Dict[str, Any]] = None,
    ) -> ProjectAuditEntry:
        entry = ProjectAuditEntry(
            project_id=project_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor_id=(actor_id or "").strip(),
            actor_name=(actor_name or "").strip(),
            reason=(reason or "").strip(),
            before=before,
            after=after,
        )
        return self._repo.save(entry)

    def list_by_project(self, project_id: str, limit: int = 200) -> List[ProjectAuditEntry]:
        return self._repo.list_by_project(project_id, limit=limit)
