"""Access audit service, service hooks, and catalog page-permission tests."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from vaybooks.bms.application.identity.audit import AccessAuditAppService
from vaybooks.bms.application.identity.service import RoleAppService, UserAppService
from vaybooks.bms.domain.entitlements.catalog import (
    PERMISSIONS,
    ROLE_OWNER,
    ROLE_SETTINGS_ADMIN,
    SYSTEM_ROLE_DEFINITIONS,
    permission_for_page,
)
from vaybooks.bms.domain.identity.audit import AccessAuditEntry

from tests.test_identity_entitlements import FakeRoleRepo, FakeUserRepo


class FakeAuditRepo:
    def __init__(self):
        self.entries: List[AccessAuditEntry] = []

    def save(self, entry: AccessAuditEntry) -> AccessAuditEntry:
        self.entries.append(entry)
        return entry

    def count(self) -> int:
        return len(self.entries)

    def list_entries(
        self,
        *,
        actor_id: str = "",
        action: str = "",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 200,
    ) -> List[AccessAuditEntry]:
        results = [
            e
            for e in self.entries
            if (not actor_id or e.actor_id == actor_id)
            and (not action or e.action == action)
            and (start is None or e.created_at >= start)
            and (end is None or e.created_at <= end)
        ]
        results.sort(key=lambda e: e.created_at, reverse=True)
        return results[:limit]


def test_record_uses_actor_resolver():
    repo = FakeAuditRepo()
    audit = AccessAuditAppService(repo, actor_resolver=lambda: ("u1", "Alice"))
    entry = audit.record("login", target_type="user", target_id="u1")
    assert entry.actor_id == "u1"
    assert entry.actor_name == "Alice"
    assert repo.entries[0].action == "login"


def test_record_explicit_actor_beats_resolver():
    repo = FakeAuditRepo()
    audit = AccessAuditAppService(repo, actor_resolver=lambda: ("u1", "Alice"))
    entry = audit.record("login_failed", actor_name="ghost")
    assert entry.actor_id == ""
    assert entry.actor_name == "ghost"


def test_list_by_actor_and_action_filters():
    repo = FakeAuditRepo()
    audit = AccessAuditAppService(repo)
    audit.record("login", actor_id="u1", actor_name="Alice")
    audit.record("logout", actor_id="u1", actor_name="Alice")
    audit.record("login", actor_id="u2", actor_name="Bob")

    assert len(audit.list_by_actor("u1")) == 2
    assert len(audit.list_entries(action="login")) == 2
    only = audit.list_entries(actor_id="u2", action="login")
    assert len(only) == 1
    assert only[0].actor_name == "Bob"


def test_catalog_includes_access_page_permissions():
    assert "settings.permissions.view" in PERMISSIONS
    assert "settings.audit.view" in PERMISSIONS
    assert permission_for_page("permissions-settings") == "settings.permissions.view"
    assert permission_for_page("audit-logs") == "settings.audit.view"
    for role_id in (ROLE_OWNER, ROLE_SETTINGS_ADMIN):
        keys = SYSTEM_ROLE_DEFINITIONS[role_id]["permission_keys"]
        assert "settings.permissions.view" in keys
        assert "settings.audit.view" in keys


def test_user_service_writes_audit_entries():
    repo = FakeAuditRepo()
    audit = AccessAuditAppService(repo, actor_resolver=lambda: ("admin", "Admin"))
    users = UserAppService(FakeUserRepo(), role_repo=FakeRoleRepo(), audit=audit)

    user = users.create_user(username="jane", password="pass1234")
    users.update_user(user.id, display_name="Jane D")
    users.update_user(user.id, active=False)
    users.set_password(user.id, "newpass1")

    actions = [e.action for e in repo.entries]
    assert actions == ["user.create", "user.update", "user.deactivate", "user.password_reset"]
    assert all(e.actor_id == "admin" for e in repo.entries)
    assert repo.entries[0].target_label == "jane"


def test_role_service_writes_audit_entries():
    repo = FakeAuditRepo()
    audit = AccessAuditAppService(repo)
    roles = RoleAppService(FakeRoleRepo(), audit=audit)

    role = roles.create_custom_role(
        name="Custom", permission_keys=["sales.invoices.view"]
    )
    roles.update_custom_role(role.id, description="d")
    roles.delete_custom_role(role.id)

    actions = [e.action for e in repo.entries]
    assert actions == ["role.create", "role.update", "role.delete"]
    assert repo.entries[0].target_label == "Custom"


def test_async_record_flushes_before_list():
    repo = FakeAuditRepo()
    audit = AccessAuditAppService(repo, async_write=True)
    try:
        audit.record("login", actor_id="u1", actor_name="Alice")
        audit.record("logout", actor_id="u1", actor_name="Alice")
        entries = audit.list_entries(actor_id="u1")
        assert len(entries) == 2
        assert {e.action for e in entries} == {"login", "logout"}
    finally:
        if audit._writer is not None:
            audit._writer.shutdown()


def test_async_record_returns_immediately():
    repo = FakeAuditRepo()
    audit = AccessAuditAppService(repo, async_write=True)
    try:
        entry = audit.record("login", actor_id="u9", actor_name="Zed")
        assert entry.action == "login"
        assert entry.actor_id == "u9"
        audit.flush(timeout=2.0)
        assert any(e.id == entry.id for e in repo.entries)
    finally:
        if audit._writer is not None:
            audit._writer.shutdown()
