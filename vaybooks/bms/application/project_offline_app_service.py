"""Offline draft queue for mobile site capture (AC-015)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import uuid4

from vaybooks.bms.domain.projects.offline import ProjectOfflineDraft
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.exceptions import ValidationError

_VALID_SECTIONS = frozenset(
    {
        "Today",
        "Progress",
        "Material",
        "Measurement",
        "Expense",
        "Photos",
        "Approval",
    }
)


class InMemoryOfflineDraftRepository:
    def __init__(self):
        self._store: Dict[str, ProjectOfflineDraft] = {}

    def save(self, draft: ProjectOfflineDraft) -> ProjectOfflineDraft:
        draft.updated_at = utc_now()
        self._store[draft.id] = draft
        return draft

    def find_by_id(self, draft_id: str) -> Optional[ProjectOfflineDraft]:
        return self._store.get(draft_id)

    def list_by_project(self, project_id: str) -> List[ProjectOfflineDraft]:
        return [d for d in self._store.values() if d.project_id == project_id]


class ProjectOfflineAppService:
    def __init__(self, draft_repo=None, project_repo=None):
        self._repo = draft_repo or InMemoryOfflineDraftRepository()
        self._project_repo = project_repo

    def _ensure_project(self, project_id: str) -> None:
        if not self._project_repo:
            return
        if not self._project_repo.find_by_id(project_id):
            raise ValidationError("Project not found")

    def save_draft(
        self,
        project_id: str,
        section: str,
        payload: Optional[Dict[str, Any]] = None,
        *,
        device_id: str = "",
        created_by: str = "",
        draft_id: str = "",
    ) -> ProjectOfflineDraft:
        self._ensure_project(project_id)
        section = (section or "").strip()
        if section not in _VALID_SECTIONS:
            raise ValidationError(
                f"Invalid section; expected one of {sorted(_VALID_SECTIONS)}"
            )
        existing = None
        if draft_id:
            existing = self._repo.find_by_id(draft_id)
            if existing and existing.synced:
                raise ValidationError("Synced drafts cannot be edited")
        draft = existing or ProjectOfflineDraft(
            project_id=project_id,
            section=section,
            id=draft_id or uuid4().hex,
        )
        draft.project_id = project_id
        draft.section = section
        draft.payload = dict(payload or {})
        draft.device_id = (device_id or "").strip()
        draft.created_by = (created_by or "").strip() or draft.created_by
        draft.synced = False
        draft.synced_at = None
        return self._repo.save(draft)

    def list_drafts(
        self, project_id: str, *, pending_only: bool = False
    ) -> List[ProjectOfflineDraft]:
        self._ensure_project(project_id)
        drafts = self._repo.list_by_project(project_id)
        if pending_only:
            return [d for d in drafts if not d.synced]
        return drafts

    def sync_draft(self, draft_id: str) -> ProjectOfflineDraft:
        draft = self._repo.find_by_id(draft_id)
        if not draft:
            raise ValidationError("Draft not found")
        if draft.synced:
            return draft
        draft.synced = True
        draft.synced_at = utc_now()
        return self._repo.save(draft)
