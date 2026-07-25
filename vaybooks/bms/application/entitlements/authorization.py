"""Authorization: plan ∩ modules ∩ flags ∩ role permissions."""

from __future__ import annotations

from typing import Optional, Set

from vaybooks.bms.domain.entitlements.catalog import (
    ALL_FEATURE_KEYS,
    expand_modules,
    permission_for_page,
)
from vaybooks.bms.domain.entitlements.entities import OrgEntitlement
from vaybooks.bms.domain.identity.entities import User
from vaybooks.bms.domain.shared.exceptions import ValidationError


class AuthorizationService:
    def __init__(
        self,
        *,
        user_repo,
        role_repo,
        plan_repo,
        flag_repo,
        org_entitlement_repo,
        membership_repo=None,
    ):
        self._user_repo = user_repo
        self._role_repo = role_repo
        self._plan_repo = plan_repo
        self._flag_repo = flag_repo
        self._org_repo = org_entitlement_repo
        self._membership_repo = membership_repo

    def get_org_entitlement(self) -> OrgEntitlement:
        ent = self._org_repo.get() if self._org_repo else None
        if ent is None:
            return OrgEntitlement()
        return ent

    def entitlement_keys(self) -> Set[str]:
        """Keys available to the org before user roles: plan ∩ modules ∩ flags."""
        ent = self.get_org_entitlement()
        plan = self._plan_repo.find_by_id(ent.plan_id) if self._plan_repo else None
        if plan and plan.feature_keys:
            plan_keys = set(plan.feature_keys)
        else:
            plan_keys = set(ALL_FEATURE_KEYS)

        module_keys = set(expand_modules(ent.enabled_modules or []))

        if self._flag_repo:
            enabled_flags: Set[str] = set()
            existing_keys: Set[str] = set()
            # Single query for all flags; avoid a per-key lookup (was O(N) DB hits).
            for flag in self._flag_repo.list_all():
                existing_keys.add(flag.key)
                if flag.enabled:
                    enabled_flags.add(flag.key)
            # Missing flags default to enabled for forward-compat with new catalog keys.
            enabled_flags |= set(ALL_FEATURE_KEYS) - existing_keys
        else:
            enabled_flags = set(ALL_FEATURE_KEYS)

        return plan_keys & module_keys & enabled_flags

    def _role_ids_for_user(self, user: User, project_id: str = "") -> list[str]:
        role_ids = list(user.role_ids or [])
        if project_id and self._membership_repo:
            for m in self._membership_repo.list_by_user(user.id):
                if m.project_id != project_id:
                    continue
                rid = getattr(m, "role_id", "") or ""
                if not rid and getattr(m, "role", None) is not None:
                    from vaybooks.bms.domain.entitlements.catalog import (
                        PROJECT_APP_ROLE_TO_ROLE_ID,
                    )

                    rid = PROJECT_APP_ROLE_TO_ROLE_ID.get(
                        m.role.value if hasattr(m.role, "value") else str(m.role), ""
                    )
                if rid and rid not in role_ids:
                    role_ids.append(rid)
        return role_ids

    def user_permission_keys(self, user: User, project_id: str = "") -> Set[str]:
        keys: Set[str] = set()
        for role_id in self._role_ids_for_user(user, project_id):
            role = self._role_repo.find_by_id(role_id) if self._role_repo else None
            if role:
                keys.update(role.permission_keys or [])
        return keys

    def effective_keys(self, user: Optional[User], project_id: str = "") -> Set[str]:
        if user is None or not user.active:
            return set()
        return self.entitlement_keys() & self.user_permission_keys(user, project_id)

    def can(
        self,
        user: Optional[User],
        feature_key: str,
        *,
        project_id: str = "",
    ) -> bool:
        key = (feature_key or "").strip()
        if not key:
            return True
        effective = self.effective_keys(user, project_id)
        if key in effective:
            return True
        # Module gate: asking for module.X requires that key.
        if key.startswith("module."):
            return key in effective
        # Concrete permission also needs its module key present in entitlements
        # (already enforced via expand_modules ∩ plan); role must grant permission.
        return False

    def require(
        self,
        user: Optional[User],
        feature_key: str,
        *,
        project_id: str = "",
        message: str = "",
    ) -> None:
        if not self.can(user, feature_key, project_id=project_id):
            raise ValidationError(
                message or f"Permission denied: {feature_key}"
            )

    def can_see_page(
        self,
        user: Optional[User],
        url_path: str,
        *,
        project_id: str = "",
    ) -> bool:
        perm = permission_for_page(url_path)
        if not perm:
            return True
        return self.can(user, perm, project_id=project_id)

    def assignable_permission_keys(self) -> Set[str]:
        """Keys custom roles may be granted (plan ∩ modules ∩ flags, permissions only)."""
        return {k for k in self.entitlement_keys() if not k.startswith("module.")}

    def bump_org_version(self) -> OrgEntitlement:
        ent = self.get_org_entitlement()
        ent.bump_version()
        return self._org_repo.save(ent)
