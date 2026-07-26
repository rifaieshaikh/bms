from types import SimpleNamespace

import pytest

from vaybooks.bms.domain.identity.entities import User
from vaybooks.bms.ui.crm_adapters import CrmAdapter, CrmUnavailable


class FakeUsers:
    def __init__(self, user):
        self.user = user

    def get_user(self, user_id):
        return self.user if self.user.id == user_id else None


class FakeAuthorization:
    def __init__(self, permissions):
        self.permissions = set(permissions)

    def can(self, _user, permission):
        return permission in self.permissions


class FakeLeads:
    def __init__(self):
        self.rows = [
            SimpleNamespace(id="mine", assigned_user_id="rep-1"),
            SimpleNamespace(id="other", assigned_user_id="rep-2"),
        ]

    def list(self, **_query):
        return self.rows

    def create_lead(self, **payload):
        return payload


def _adapter(permissions):
    user = User(username="rep", id="rep-1")
    return CrmAdapter(
        {
            "crm_leads": FakeLeads(),
            "users": FakeUsers(user),
            "crm_access": FakeAuthorization(permissions),
        },
        actor_id=user.id,
        actor_name=user.username,
    )


def test_own_scope_hides_other_representatives_records():
    adapter = _adapter({"crm.records.view_own", "crm.leads.view"})
    assert [row.id for row in adapter.list_leads()] == ["mine"]


def test_team_scope_exposes_team_query_results():
    adapter = _adapter({"crm.records.view_team", "crm.leads.view"})
    assert [row.id for row in adapter.list_leads()] == ["mine", "other"]


def test_write_adapter_enforces_action_permission():
    adapter = _adapter({"crm.records.view_own", "crm.leads.view"})
    with pytest.raises(CrmUnavailable, match="crm.leads.create"):
        adapter.create_lead({"name": "Denied"})
