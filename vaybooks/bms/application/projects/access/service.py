"""Access control, maker-checker, and session identity for projects."""

from __future__ import annotations

from typing import List, Optional, Union

from vaybooks.bms.domain.entitlements.catalog import (
    PROJECT_APP_ROLE_TO_ROLE_ID,
    ROLE_OWNER,
)
from vaybooks.bms.domain.identity.entities import User
from vaybooks.bms.domain.projects.access import AppUser, ProjectMembership
from vaybooks.bms.domain.shared.enums import ProjectAppRole
from vaybooks.bms.domain.shared.exceptions import ValidationError

UserLike = Union[User, AppUser, None]


def _as_user(user: UserLike, user_repo=None) -> Optional[User]:
    if user is None:
        return None
    if isinstance(user, User):
        return user
    if user_repo and getattr(user, "id", None):
        found = user_repo.find_by_id(user.id)
        if found:
            return found
    # Best-effort adapter from legacy AppUser
    role_ids = []
    for r in getattr(user, "global_roles", None) or []:
        val = r.value if hasattr(r, "value") else str(r)
        rid = PROJECT_APP_ROLE_TO_ROLE_ID.get(val)
        if rid:
            role_ids.append(rid)
    return User(
        id=getattr(user, "id", "") or "",
        username=getattr(user, "username", "") or "",
        display_name=getattr(user, "display_name", "") or "",
        password_hash=getattr(user, "password_hash", "") or "",
        role_ids=role_ids or list(getattr(user, "role_ids", None) or []),
        active=bool(getattr(user, "active", True)),
    )


class ProjectAccessPolicy:
    """UC-043 + AC-013 cost visibility + maker-checker (delegates to AuthorizationService)."""

    def __init__(
        self,
        *,
        maker_checker_enabled: bool = True,
        user_repo=None,
        membership_repo=None,
        authorization=None,
    ):
        self.maker_checker_enabled = maker_checker_enabled
        self._user_repo = user_repo
        self._membership_repo = membership_repo
        self._authorization = authorization

    def get_user(self, user_id: str) -> Optional[User]:
        if not self._user_repo or not user_id:
            return None
        return self._user_repo.find_by_id(user_id)

    def resolve_roles(self, user: UserLike, project_id: str = "") -> List[ProjectAppRole]:
        u = _as_user(user, self._user_repo)
        roles: List[ProjectAppRole] = []
        if u is None:
            return roles
        reverse = {v: k for k, v in PROJECT_APP_ROLE_TO_ROLE_ID.items()}
        for rid in u.role_ids or []:
            name = reverse.get(rid)
            if name:
                try:
                    roles.append(ProjectAppRole(name))
                except ValueError:
                    continue
        if project_id and self._membership_repo:
            for m in self._membership_repo.list_by_project(project_id):
                if m.user_id == u.id and m.role not in roles:
                    roles.append(m.role)
        return roles

    def can_view_internal_cost(self, user: UserLike, project_id: str = "") -> bool:
        u = _as_user(user, self._user_repo)
        if self._authorization is not None:
            if u is None or not u.active:
                return False
            return self._authorization.can(
                u, "projects.cost.view_internal", project_id=project_id
            )
        if u is None:
            return True
        if not u.active:
            return False
        roles = self.resolve_roles(u, project_id)
        from vaybooks.bms.domain.projects.access import _COST_VIEWERS

        return any(r in _COST_VIEWERS for r in roles)

    def assert_commercial_approve(
        self,
        *,
        actor_id: str,
        actor_name: str,
        submitted_by: str,
        document_label: str = "document",
        user: UserLike = None,
        project_id: str = "",
    ) -> None:
        if user is not None and self._authorization is not None:
            self._authorization.require(
                _as_user(user, self._user_repo),
                "projects.commercial.approve",
                project_id=project_id,
                message=f"Permission denied to approve {document_label}",
            )
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
    ) -> User:
        if not self._user_repo:
            raise ValidationError("User repository is not configured")
        existing = self._user_repo.find_by_username(username)
        if existing:
            return existing
        role_ids = []
        for r in roles or [ProjectAppRole.OWNER]:
            rid = PROJECT_APP_ROLE_TO_ROLE_ID.get(r.value if hasattr(r, "value") else str(r))
            if rid:
                role_ids.append(rid)
        if not role_ids:
            role_ids = [ROLE_OWNER]
        user = User(
            username=username.strip(),
            display_name=(display_name or username).strip(),
            role_ids=role_ids,
        )
        return self._user_repo.save(user)

    def assign_membership(
        self, project_id: str, user_id: str, role: ProjectAppRole
    ) -> ProjectMembership:
        if not self._membership_repo:
            raise ValidationError("Membership repository is not configured")
        role_id = PROJECT_APP_ROLE_TO_ROLE_ID.get(role.value, "")
        membership = ProjectMembership(
            project_id=project_id,
            user_id=user_id,
            role=role,
            role_id=role_id,
        )
        return self._membership_repo.save(membership)
