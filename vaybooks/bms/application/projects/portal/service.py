"""Customer portal token create / validate (Wave 8)."""

from __future__ import annotations

from datetime import timedelta
from secrets import token_urlsafe
from typing import Dict, List, Optional

from vaybooks.bms.domain.projects.offline import ProjectPortalToken
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.exceptions import ValidationError

_VALID_SCOPES = frozenset({"quote", "measurement", "bill"})


class InMemoryPortalTokenRepository:
    def __init__(self):
        self._store: Dict[str, ProjectPortalToken] = {}

    def save(self, portal: ProjectPortalToken) -> ProjectPortalToken:
        self._store[portal.id] = portal
        self._store[portal.token] = portal
        return portal

    def find_by_token(self, token: str) -> Optional[ProjectPortalToken]:
        return self._store.get(token)

    def list_by_project(self, project_id: str) -> List[ProjectPortalToken]:
        seen = set()
        rows = []
        for item in self._store.values():
            if item.id in seen:
                continue
            if item.project_id == project_id:
                seen.add(item.id)
                rows.append(item)
        return rows


class ProjectPortalAppService:
    def __init__(self, token_repo=None, project_repo=None):
        self._repo = token_repo or InMemoryPortalTokenRepository()
        self._project_repo = project_repo

    def create_portal_token(
        self,
        project_id: str,
        scope: str = "quote",
        *,
        expires_in_days: int = 30,
        label: str = "",
    ) -> ProjectPortalToken:
        if self._project_repo and not self._project_repo.find_by_id(project_id):
            raise ValidationError("Project not found")
        scope = (scope or "quote").strip().lower()
        if scope not in _VALID_SCOPES:
            raise ValidationError(
                f"Invalid scope; expected one of {sorted(_VALID_SCOPES)}"
            )
        expires_at = utc_now() + timedelta(days=max(1, int(expires_in_days or 30)))
        portal = ProjectPortalToken(
            project_id=project_id,
            token=token_urlsafe(24),
            scope=scope,
            expires_at=expires_at,
            label=(label or "").strip(),
        )
        return self._repo.save(portal)

    def validate_portal_token(self, token: str) -> ProjectPortalToken:
        token = (token or "").strip()
        if not token:
            raise ValidationError("Token is required")
        portal = self._repo.find_by_token(token)
        if not portal:
            raise ValidationError("Invalid portal token")
        if portal.revoked:
            raise ValidationError("Portal token has been revoked")
        if portal.expires_at and portal.expires_at < utc_now():
            raise ValidationError("Portal token has expired")
        return portal

    def list_tokens(self, project_id: str) -> List[ProjectPortalToken]:
        return self._repo.list_by_project(project_id)
