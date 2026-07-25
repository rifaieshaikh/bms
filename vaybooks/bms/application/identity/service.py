"""User and Role application services."""

from __future__ import annotations

from typing import List, Optional
from uuid import uuid4

from vaybooks.bms.domain.entitlements.catalog import ROLE_OWNER
from vaybooks.bms.domain.identity.entities import Role, User
from vaybooks.bms.domain.identity.passwords import hash_password, verify_password
from vaybooks.bms.domain.shared.exceptions import ValidationError


class UserAppService:
    def __init__(self, user_repo, role_repo=None, authorization=None, audit=None):
        self._user_repo = user_repo
        self._role_repo = role_repo
        self._auth = authorization
        self._audit = audit

    def _record(self, action: str, user: User, detail: Optional[dict] = None) -> None:
        if self._audit is None:
            return
        try:
            self._audit.record(
                action,
                target_type="user",
                target_id=user.id,
                target_label=user.username,
                detail=detail or {},
            )
        except Exception:
            pass  # auditing must never break the operation

    def list_users(self) -> List[User]:
        return self._user_repo.list_all()

    def get_user(self, user_id: str) -> Optional[User]:
        return self._user_repo.find_by_id(user_id)

    def get_by_username(self, username: str) -> Optional[User]:
        return self._user_repo.find_by_username((username or "").strip())

    def authenticate(self, username: str, password: str) -> User:
        user = self.get_by_username(username)
        if user is None or not user.active:
            raise ValidationError("Invalid username or password")
        if not verify_password(password, user.password_hash):
            raise ValidationError("Invalid username or password")
        return user

    def create_user(
        self,
        *,
        username: str,
        display_name: str = "",
        password: str,
        role_ids: Optional[List[str]] = None,
        active: bool = True,
    ) -> User:
        username = (username or "").strip()
        if not username:
            raise ValidationError("Username is required")
        if self._user_repo.find_by_username(username):
            raise ValidationError(f"Username already exists: {username}")
        if not password or len(password) < 4:
            raise ValidationError("Password must be at least 4 characters")
        roles = list(role_ids or [])
        self._validate_role_ids(roles)
        user = User(
            username=username,
            display_name=(display_name or username).strip(),
            password_hash=hash_password(password),
            role_ids=roles,
            active=active,
        )
        saved = self._user_repo.save(user)
        self._record("user.create", saved, {"role_ids": roles})
        return saved

    def update_user(
        self,
        user_id: str,
        *,
        display_name: Optional[str] = None,
        role_ids: Optional[List[str]] = None,
        active: Optional[bool] = None,
    ) -> User:
        user = self._user_repo.find_by_id(user_id)
        if user is None:
            raise ValidationError("User not found")
        was_active = user.active
        if display_name is not None:
            user.display_name = display_name.strip()
        if role_ids is not None:
            self._validate_role_ids(role_ids)
            user.role_ids = list(role_ids)
        if active is not None:
            if not active and self._is_last_active_owner(user):
                raise ValidationError("Cannot deactivate the last active Owner")
            user.active = active
        saved = self._user_repo.save(user)
        if active is not None and active != was_active:
            self._record(
                "user.deactivate" if not active else "user.activate", saved
            )
        else:
            self._record("user.update", saved, {"role_ids": saved.role_ids})
        return saved

    def set_password(self, user_id: str, password: str) -> User:
        user = self._user_repo.find_by_id(user_id)
        if user is None:
            raise ValidationError("User not found")
        if not password or len(password) < 4:
            raise ValidationError("Password must be at least 4 characters")
        user.password_hash = hash_password(password)
        saved = self._user_repo.save(user)
        self._record("user.password_reset", saved)
        return saved

    def _validate_role_ids(self, role_ids: List[str]) -> None:
        if not self._role_repo:
            return
        for rid in role_ids:
            if not self._role_repo.find_by_id(rid):
                raise ValidationError(f"Unknown role: {rid}")

    def _is_last_active_owner(self, user: User) -> bool:
        if ROLE_OWNER not in (user.role_ids or []):
            return False
        owners = [
            u
            for u in self._user_repo.list_all()
            if u.active and u.id != user.id and ROLE_OWNER in (u.role_ids or [])
        ]
        return len(owners) == 0


class RoleAppService:
    def __init__(self, role_repo, authorization=None, audit=None):
        self._role_repo = role_repo
        self._auth = authorization
        self._audit = audit

    def _record(self, action: str, role: Role, detail: Optional[dict] = None) -> None:
        if self._audit is None:
            return
        try:
            self._audit.record(
                action,
                target_type="role",
                target_id=role.id,
                target_label=role.name,
                detail=detail or {},
            )
        except Exception:
            pass

    def list_roles(self) -> List[Role]:
        return self._role_repo.list_all()

    def get_role(self, role_id: str) -> Optional[Role]:
        return self._role_repo.find_by_id(role_id)

    def create_custom_role(
        self,
        *,
        name: str,
        permission_keys: List[str],
        description: str = "",
        clone_from_role_id: str = "",
    ) -> Role:
        name = (name or "").strip()
        if not name:
            raise ValidationError("Role name is required")
        if self._role_repo.find_by_name(name):
            raise ValidationError(f"Role name already exists: {name}")
        keys = list(permission_keys or [])
        if clone_from_role_id and not keys:
            source = self._role_repo.find_by_id(clone_from_role_id)
            if source:
                keys = list(source.permission_keys or [])
        keys = self._cap_keys(keys)
        role = Role(
            id=uuid4().hex,
            name=name,
            description=description.strip(),
            is_system=False,
            permission_keys=keys,
        )
        saved = self._role_repo.save(role)
        if self._auth:
            self._auth.bump_org_version()
        self._record("role.create", saved, {"permission_keys": keys})
        return saved

    def update_custom_role(
        self,
        role_id: str,
        *,
        name: Optional[str] = None,
        permission_keys: Optional[List[str]] = None,
        description: Optional[str] = None,
    ) -> Role:
        role = self._role_repo.find_by_id(role_id)
        if role is None:
            raise ValidationError("Role not found")
        if role.is_system:
            raise ValidationError("System roles cannot be modified")
        if name is not None:
            name = name.strip()
            if not name:
                raise ValidationError("Role name is required")
            existing = self._role_repo.find_by_name(name)
            if existing and existing.id != role.id:
                raise ValidationError(f"Role name already exists: {name}")
            role.name = name
        if description is not None:
            role.description = description.strip()
        if permission_keys is not None:
            role.permission_keys = self._cap_keys(list(permission_keys))
        saved = self._role_repo.save(role)
        if self._auth:
            self._auth.bump_org_version()
        self._record("role.update", saved, {"permission_keys": saved.permission_keys})
        return saved

    def delete_custom_role(self, role_id: str) -> None:
        role = self._role_repo.find_by_id(role_id)
        if role is None:
            raise ValidationError("Role not found")
        if role.is_system:
            raise ValidationError("System roles cannot be deleted")
        self._role_repo.delete(role_id)
        if self._auth:
            self._auth.bump_org_version()
        self._record("role.delete", role)

    def _cap_keys(self, keys: List[str]) -> List[str]:
        if self._auth is None:
            return sorted(set(keys))
        allowed = self._auth.assignable_permission_keys()
        capped = sorted({k for k in keys if k in allowed})
        rejected = set(keys) - set(capped)
        if rejected:
            raise ValidationError(
                "Custom role includes permissions outside current plan/modules/flags: "
                + ", ".join(sorted(rejected)[:8])
            )
        return capped
