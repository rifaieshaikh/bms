"""Access control, maker-checker, and session identity for projects."""

from __future__ import annotations

from typing import List, Optional

from vaybooks.bms.domain.projects.access import AppUser, ProjectMembership
from vaybooks.bms.domain.shared.enums import ProjectAppRole
from vaybooks.bms.domain.shared.exceptions import ValidationError


class ProjectAccessPolicy:
    """UC-043 skeleton + AC-013 cost visibility + maker-checker."""

    def __init__(
        self,
        *,
        maker_checker_enabled: bool = True,
        user_repo=None,
        membership_repo=None,
    ):
        self.maker_checker_enabled = maker_checker_enabled
        self._user_repo = user_repo
        self._membership_repo = membership_repo

    def get_user(self, user_id: str) -> Optional[AppUser]:
        if not self._user_repo or not user_id:
            return None
        return self._user_repo.find_by_id(user_id)

    def resolve_roles(self, user: AppUser, project_id: str = "") -> List[ProjectAppRole]:
        roles = list(user.global_roles or [])
        if project_id and self._membership_repo:
            for m in self._membership_repo.list_by_project(project_id):
                if m.user_id == user.id and m.role not in roles:
                    roles.append(m.role)
        return roles

    def can_view_internal_cost(self, user: Optional[AppUser], project_id: str = "") -> bool:
        if user is None:
            # Desktop single-user default: allow until users are configured.
            return True
        if not user.active:
            return False
        roles = self.resolve_roles(user, project_id)
        from vaybooks.bms.domain.projects.access import _COST_VIEWERS

        return any(r in _COST_VIEWERS for r in roles)

    def assert_commercial_approve(
        self,
        *,
        actor_id: str,
        actor_name: str,
        submitted_by: str,
        document_label: str = "document",
    ) -> None:
        if not self.maker_checker_enabled:
            return
        actor = (actor_id or actor_name or "").strip().lower()
        submitter = (submitted_by or "").strip().lower()
        if actor and submitter and actor == submitter:
            raise ValidationError(
                f"Maker-checker: you cannot approve your own {document_label}"
            )

    def ensure_user(
        self,
        username: str,
        *,
        display_name: str = "",
        roles: Optional[List[ProjectAppRole]] = None,
    ) -> AppUser:
        if not self._user_repo:
            raise ValidationError("User repository is not configured")
        existing = self._user_repo.find_by_username(username)
        if existing:
            return existing
        user = AppUser(
            username=username.strip(),
            display_name=(display_name or username).strip(),
            global_roles=list(roles or [ProjectAppRole.OWNER]),
        )
        return self._user_repo.save(user)

    def assign_membership(
        self, project_id: str, user_id: str, role: ProjectAppRole
    ) -> ProjectMembership:
        if not self._membership_repo:
            raise ValidationError("Membership repository is not configured")
        membership = ProjectMembership(
            project_id=project_id, user_id=user_id, role=role
        )
        return self._membership_repo.save(membership)
