"""Authorization, plans, custom roles, passwords, and catalog smoke tests."""

from __future__ import annotations

from typing import Dict, List, Optional

import pytest

from vaybooks.bms.application.entitlements.authorization import AuthorizationService
from vaybooks.bms.application.entitlements.service import PlanAppService
from vaybooks.bms.application.identity.service import RoleAppService, UserAppService
from vaybooks.bms.domain.entitlements.catalog import (
    ALL_FEATURE_KEYS,
    ALL_MODULES,
    DEFAULT_ADMIN_PASSWORD,
    DEFAULT_ADMIN_USERNAME,
    MODULE_BOUTIQUE,
    MODULE_CORE,
    MODULE_PARTIES,
    MODULE_SALES,
    MODULE_SETTINGS,
    PERMISSIONS,
    PLAN_DEFINITIONS,
    PLAN_ENTERPRISE,
    PLAN_STARTER,
    ROLE_OWNER,
    ROLE_SALES,
    SYSTEM_ROLE_DEFINITIONS,
    expand_modules,
    permission_for_page,
)
from vaybooks.bms.domain.entitlements.entities import FeatureFlag, OrgEntitlement, Plan
from vaybooks.bms.domain.identity.entities import Role, User
from vaybooks.bms.domain.identity.passwords import hash_password, verify_password
from vaybooks.bms.domain.shared.exceptions import ValidationError


class FakeUserRepo:
    def __init__(self):
        self._store: Dict[str, User] = {}

    def save(self, user: User) -> User:
        self._store[user.id] = user
        return user

    def find_by_id(self, user_id: str):
        return self._store.get(user_id)

    def find_by_username(self, username: str):
        for u in self._store.values():
            if u.username == username:
                return u
        return None

    def list_all(self):
        return list(self._store.values())

    def delete(self, user_id: str) -> None:
        self._store.pop(user_id, None)


class FakeRoleRepo:
    def __init__(self, seed: bool = True):
        self._store: Dict[str, Role] = {}
        if seed:
            for rid, meta in SYSTEM_ROLE_DEFINITIONS.items():
                self.save(
                    Role(
                        id=rid,
                        name=meta["name"],
                        description=meta.get("description", ""),
                        is_system=True,
                        permission_keys=list(meta.get("permission_keys") or []),
                    )
                )

    def save(self, role: Role) -> Role:
        self._store[role.id] = role
        return role

    def find_by_id(self, role_id: str):
        return self._store.get(role_id)

    def find_by_name(self, name: str):
        for r in self._store.values():
            if r.name == name:
                return r
        return None

    def list_all(self):
        return list(self._store.values())

    def delete(self, role_id: str) -> None:
        self._store.pop(role_id, None)


class FakeFlagRepo:
    def __init__(self, enabled: bool = True):
        self._store: Dict[str, FeatureFlag] = {
            k: FeatureFlag(key=k, enabled=enabled) for k in ALL_FEATURE_KEYS
        }

    def save(self, flag: FeatureFlag) -> FeatureFlag:
        self._store[flag.key] = flag
        return flag

    def find_by_key(self, key: str):
        return self._store.get(key)

    def list_all(self):
        return list(self._store.values())


class FakePlanRepo:
    def __init__(self):
        self._store: Dict[str, Plan] = {
            pid: Plan(
                id=meta["id"],
                name=meta["name"],
                description=meta.get("description", ""),
                feature_keys=list(meta.get("feature_keys") or []),
                is_system=True,
            )
            for pid, meta in PLAN_DEFINITIONS.items()
        }

    def save(self, plan: Plan) -> Plan:
        self._store[plan.id] = plan
        return plan

    def find_by_id(self, plan_id: str):
        return self._store.get(plan_id)

    def list_all(self):
        return list(self._store.values())

    def delete(self, plan_id: str) -> None:
        self._store.pop(plan_id, None)


class FakeOrgRepo:
    def __init__(self, plan_id: str = PLAN_ENTERPRISE, modules=None):
        self._ent = OrgEntitlement(
            plan_id=plan_id,
            enabled_modules=list(modules or ALL_MODULES),
            version=1,
        )

    def get(self):
        return self._ent

    def save(self, entitlement: OrgEntitlement) -> OrgEntitlement:
        self._ent = entitlement
        return entitlement


def _auth(
    *,
    plan_id: str = PLAN_ENTERPRISE,
    modules=None,
    flags_enabled: bool = True,
) -> AuthorizationService:
    return AuthorizationService(
        user_repo=FakeUserRepo(),
        role_repo=FakeRoleRepo(),
        plan_repo=FakePlanRepo(),
        flag_repo=FakeFlagRepo(enabled=flags_enabled),
        org_entitlement_repo=FakeOrgRepo(plan_id=plan_id, modules=modules),
    )


def test_password_hash_roundtrip():
    hashed = hash_password("secret123")
    assert verify_password("secret123", hashed)
    assert not verify_password("wrong", hashed)


def test_catalog_has_module_and_permission_keys():
    assert "module.boutique" in ALL_FEATURE_KEYS
    assert "projects.cost.view_internal" in PERMISSIONS
    assert permission_for_page("dashboard") == "core.dashboard.view"
    assert permission_for_page("users-settings") == "settings.users.view"


def test_owner_can_everything_on_enterprise():
    auth = _auth()
    owner = User(username="admin", role_ids=[ROLE_OWNER], active=True)
    assert auth.can(owner, "projects.cost.view_internal")
    assert auth.can(owner, "boutique.orders.view")
    assert auth.can(owner, "settings.plans.manage")
    assert auth.can_see_page(owner, "dashboard")


def test_plan_off_blocks_boutique():
    auth = _auth(plan_id=PLAN_STARTER)
    owner = User(username="admin", role_ids=[ROLE_OWNER], active=True)
    assert not auth.can(owner, "boutique.orders.view")
    assert auth.can(owner, "sales.invoices.view")
    assert not auth.can_see_page(owner, "boutique-overview")


def test_module_off_blocks_boutique_even_on_enterprise():
    modules = [m for m in ALL_MODULES if m != MODULE_BOUTIQUE]
    auth = _auth(modules=modules)
    owner = User(username="admin", role_ids=[ROLE_OWNER], active=True)
    assert not auth.can(owner, "boutique.orders.view")
    assert auth.can(owner, "sales.invoices.view")


def test_flag_off_blocks_permission():
    auth = _auth()
    auth._flag_repo.save(
        FeatureFlag(key="sales.invoices.view", enabled=False)
    )
    owner = User(username="admin", role_ids=[ROLE_OWNER], active=True)
    assert not auth.can(owner, "sales.invoices.view")


def test_missing_role_permission_blocks():
    auth = _auth()
    sales = User(username="sales1", role_ids=[ROLE_SALES], active=True)
    assert auth.can(sales, "sales.invoices.view")
    assert not auth.can(sales, "projects.cost.view_internal")
    assert not auth.can(sales, "settings.users.manage")


def test_inactive_user_denied():
    auth = _auth()
    user = User(username="x", role_ids=[ROLE_OWNER], active=False)
    assert not auth.can(user, "core.dashboard.view")


def test_custom_role_capped_to_entitlements():
    auth = _auth(plan_id=PLAN_STARTER)
    roles = RoleAppService(FakeRoleRepo(), authorization=auth)
    with pytest.raises(ValidationError, match="outside current plan"):
        roles.create_custom_role(
            name="Bad Boutique",
            permission_keys=["boutique.orders.view"],
        )
    role = roles.create_custom_role(
        name="Sales Lite",
        permission_keys=["sales.invoices.view", "parties.customers.view"],
    )
    assert "sales.invoices.view" in role.permission_keys
    assert not role.is_system


def test_system_role_cannot_be_modified():
    auth = _auth()
    roles = RoleAppService(FakeRoleRepo(), authorization=auth)
    with pytest.raises(ValidationError, match="System roles"):
        roles.update_custom_role(ROLE_OWNER, name="Nope")


def test_login_authenticate_rejects_bad_password():
    users = UserAppService(FakeUserRepo(), role_repo=FakeRoleRepo())
    users.create_user(
        username=DEFAULT_ADMIN_USERNAME,
        password=DEFAULT_ADMIN_PASSWORD,
        role_ids=[ROLE_OWNER],
    )
    with pytest.raises(ValidationError, match="Invalid"):
        users.authenticate(DEFAULT_ADMIN_USERNAME, "wrong")
    ok = users.authenticate(DEFAULT_ADMIN_USERNAME, DEFAULT_ADMIN_PASSWORD)
    assert ok.username == DEFAULT_ADMIN_USERNAME


def test_set_enabled_modules_requires_core_settings():
    org = FakeOrgRepo()
    plans = PlanAppService(FakePlanRepo(), org)
    ent = plans.set_enabled_modules([MODULE_SALES, MODULE_PARTIES])
    assert MODULE_CORE in ent.enabled_modules
    assert MODULE_SETTINGS in ent.enabled_modules
    assert MODULE_SALES in ent.enabled_modules


def test_expand_modules_includes_permissions():
    keys = expand_modules([MODULE_SALES])
    assert "module.sales" in keys
    assert "sales.invoices.view" in keys
    assert "boutique.orders.view" not in keys


def test_create_custom_plan_and_apply():
    plans = PlanAppService(FakePlanRepo(), FakeOrgRepo())
    plan = plans.create_plan(
        name="Retail Lite",
        description="Sales only",
        feature_keys=["module.sales", "sales.invoices.view", "sales.invoices.create"],
    )
    assert plan.id == "retail_lite"
    assert not plan.is_system
    assert "sales.invoices.view" in plan.feature_keys
    assert any(p.id == "retail_lite" for p in plans.list_plans())
    ent = plans.set_plan("retail_lite")
    assert ent.plan_id == "retail_lite"


def test_create_plan_rejects_duplicate_name_and_unknown_keys():
    plans = PlanAppService(FakePlanRepo(), FakeOrgRepo())
    with pytest.raises(ValidationError, match="already exists"):
        plans.create_plan(name="Starter", feature_keys=["module.sales"])
    with pytest.raises(ValidationError, match="Unknown feature keys"):
        plans.create_plan(name="Bad", feature_keys=["nope.not.real"])
    with pytest.raises(ValidationError, match="at least one feature"):
        plans.create_plan(name="Empty", feature_keys=[])


def test_clone_plan_copies_feature_keys():
    plans = PlanAppService(FakePlanRepo(), FakeOrgRepo())
    clone = plans.create_plan(name="Starter Copy", clone_from_plan_id=PLAN_STARTER)
    starter_keys = set(PLAN_DEFINITIONS[PLAN_STARTER]["feature_keys"])
    assert set(clone.feature_keys) == starter_keys


def test_builtin_plan_cannot_be_modified_or_deleted():
    plans = PlanAppService(FakePlanRepo(), FakeOrgRepo())
    with pytest.raises(ValidationError, match="cannot be modified"):
        plans.update_plan(PLAN_STARTER, name="Nope")
    with pytest.raises(ValidationError, match="cannot be deleted"):
        plans.delete_plan(PLAN_STARTER)


def test_delete_active_plan_blocked_until_switched():
    plans = PlanAppService(FakePlanRepo(), FakeOrgRepo())
    plan = plans.create_plan(name="Temp", feature_keys=["module.core"])
    plans.set_plan(plan.id)
    with pytest.raises(ValidationError, match="currently active"):
        plans.delete_plan(plan.id)
    plans.set_plan(PLAN_ENTERPRISE)
    plans.delete_plan(plan.id)
    assert all(p.id != plan.id for p in plans.list_plans())


def test_plan_slug_uniqueness():
    plans = PlanAppService(FakePlanRepo(), FakeOrgRepo())
    first = plans.create_plan(name="My Plan!", feature_keys=["module.core"])
    second = plans.create_plan(name="My  Plan?", feature_keys=["module.core"])
    assert first.id == "my_plan"
    assert second.id == "my_plan_2"


def test_migration_seed_definitions_cover_plans_and_roles():
    assert set(PLAN_DEFINITIONS) == {"starter", "growth", "enterprise"}
    assert ROLE_OWNER in SYSTEM_ROLE_DEFINITIONS
    assert "Owner" == SYSTEM_ROLE_DEFINITIONS[ROLE_OWNER]["name"]
    # Enterprise includes all keys
    assert set(PLAN_DEFINITIONS[PLAN_ENTERPRISE]["feature_keys"]) == set(ALL_FEATURE_KEYS)
