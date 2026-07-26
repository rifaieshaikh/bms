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
    MODULE_CRM,
    MODULE_LABELS,
    MODULE_PARTIES,
    MODULE_SALES,
    MODULE_SETTINGS,
    ORG_ENTITLEMENT_ID,
    PERMISSIONS,
    PLAN_DEFINITIONS,
    PLAN_ENTERPRISE,
    PLAN_GROWTH,
    PLAN_STARTER,
    ROLE_AUDITOR,
    ROLE_COLLECTIONS,
    ROLE_CRM_ADMIN,
    ROLE_OWNER,
    ROLE_SALES,
    ROLE_SALES_MANAGER,
    ROLE_SALES_REP,
    SYSTEM_ROLE_DEFINITIONS,
    expand_modules,
    permission_for_page,
    permissions_for_module,
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


# ---------------------------------------------------------------------------
# CRM module
# ---------------------------------------------------------------------------


def _role_keys(role_id: str) -> set:
    return set(SYSTEM_ROLE_DEFINITIONS[role_id]["permission_keys"])


def test_crm_module_registered_in_catalog():
    assert MODULE_CRM in ALL_MODULES
    assert "module.crm" in ALL_FEATURE_KEYS
    assert MODULE_LABELS[MODULE_CRM] == "CRM"
    crm_perms = permissions_for_module(MODULE_CRM)
    assert crm_perms
    assert all(p.startswith("crm.") for p in crm_perms)
    assert crm_perms <= set(PERMISSIONS)


def test_crm_permission_catalog_covers_role_needs():
    for key in (
        "crm.dashboard.view",
        "crm.leads.view",
        "crm.leads.assign",
        "crm.enquiries.convert",
        "crm.activities.create",
        "crm.calendar.manage_team",
        "crm.records.view_own",
        "crm.records.view_team",
        "crm.records.view_all",
        "crm.reports.team.view",
        "crm.reports.collection.view",
        "crm.settings.edit",
        "crm.import.run",
        "crm.audit.view",
        "crm.corrections.auto_apply",
        "crm.balances.view",
        "crm.credit.manage",
        "crm.payment_followups.edit",
        "crm.reminders.whatsapp.send",
    ):
        assert key in PERMISSIONS


def test_expand_modules_includes_crm_permissions():
    keys = expand_modules([MODULE_CRM])
    assert "module.crm" in keys
    assert "crm.leads.view" in keys
    assert "sales.invoices.view" not in keys


def test_crm_page_permission_lookup():
    assert permission_for_page("crm-dashboard") == "crm.dashboard.view"
    assert permission_for_page("crm-leads") == "crm.leads.view"
    assert permission_for_page("crm-enquiries") == "crm.enquiries.view"
    assert permission_for_page("crm-activities") == "crm.activities.view"
    assert permission_for_page("crm-calendar") == "crm.calendar.view"
    assert permission_for_page("crm-reports") == "crm.reports.view"
    assert permission_for_page("crm-settings") == "crm.settings.view"


def test_hidden_crm_detail_routes_reuse_list_permissions():
    assert permission_for_page("crm-lead-detail") == "crm.leads.view"
    assert permission_for_page("crm-enquiry-detail") == "crm.enquiries.view"
    assert permission_for_page("crm-activity-detail") == "crm.activities.view"


def test_sales_rep_limited_to_own_records():
    keys = _role_keys(ROLE_SALES_REP)
    assert {
        "crm.leads.create",
        "crm.activities.create",
        "crm.calendar.edit",
        "crm.records.view_own",
        "crm.reports.view",
    } <= keys
    assert "crm.records.view_team" not in keys
    assert "crm.records.view_all" not in keys
    assert "crm.leads.assign" not in keys
    assert "crm.settings.edit" not in keys


def test_sales_manager_can_assign_and_see_team():
    keys = _role_keys(ROLE_SALES_MANAGER)
    assert {
        "crm.leads.assign",
        "crm.enquiries.assign",
        "crm.records.view_team",
        "crm.reports.team.view",
        "crm.calendar.manage_team",
        "crm.settings.view",
    } <= keys
    assert "crm.records.view_all" not in keys
    assert "crm.settings.edit" not in keys


def test_crm_admin_has_every_crm_permission():
    keys = _role_keys(ROLE_CRM_ADMIN)
    assert permissions_for_module(MODULE_CRM) <= keys
    assert {
        "crm.settings.edit",
        "crm.import.run",
        "crm.audit.view",
        "crm.corrections.auto_apply",
        "crm.records.view_all",
    } <= keys


def test_collections_role_covers_balances_and_followups():
    keys = _role_keys(ROLE_COLLECTIONS)
    assert {
        "crm.balances.view",
        "crm.credit.view",
        "crm.credit.manage",
        "crm.payment_followups.view",
        "crm.payment_followups.edit",
        "crm.reports.collection.view",
        "crm.reminders.whatsapp.send",
        "crm.records.view_all",
    } <= keys
    assert "crm.settings.edit" not in keys
    assert "crm.leads.create" not in keys


def test_owner_receives_crm_permissions_on_default_plan():
    assert permissions_for_module(MODULE_CRM) <= _role_keys(ROLE_OWNER)
    auth = _auth()
    owner = User(username="admin", role_ids=[ROLE_OWNER], active=True)
    assert auth.can(owner, "crm.leads.view")
    assert auth.can(owner, "crm.settings.edit")
    assert auth.can_see_page(owner, "crm-dashboard")
    assert auth.can_see_page(owner, "crm-lead-detail")


def test_crm_module_off_blocks_crm_pages():
    modules = [m for m in ALL_MODULES if m != MODULE_CRM]
    auth = _auth(modules=modules)
    owner = User(username="admin", role_ids=[ROLE_OWNER], active=True)
    assert not auth.can(owner, "crm.leads.view")
    assert not auth.can_see_page(owner, "crm-leads")
    assert auth.can(owner, "sales.invoices.view")


def test_existing_plans_stay_backward_compatible():
    for plan_id in (PLAN_STARTER, PLAN_GROWTH):
        keys = set(PLAN_DEFINITIONS[plan_id]["feature_keys"])
        assert "module.crm" not in keys
        assert not any(k.startswith("crm.") for k in keys)
    assert "sales.invoices.view" in set(PLAN_DEFINITIONS[PLAN_STARTER]["feature_keys"])
    assert "boutique.orders.view" in set(PLAN_DEFINITIONS[PLAN_GROWTH]["feature_keys"])
    assert "module.crm" in set(PLAN_DEFINITIONS[PLAN_ENTERPRISE]["feature_keys"])


class FakeCollection:
    """Minimal in-memory stand-in for the migration's pymongo usage."""

    def __init__(self, docs=None):
        self.docs: Dict[str, dict] = {d["_id"]: dict(d) for d in (docs or [])}

    def find_one(self, query):
        return self.docs.get(query["_id"])

    def insert_one(self, doc):
        self.docs[doc["_id"]] = dict(doc)

    def replace_one(self, query, doc, upsert=False):
        if query["_id"] in self.docs or upsert:
            self.docs[query["_id"]] = dict(doc)

    def update_one(self, query, update):
        doc = self.docs.get(query["_id"])
        if doc is None:
            return
        for field, value in (update.get("$set") or {}).items():
            doc[field] = value
        for field, value in (update.get("$inc") or {}).items():
            doc[field] = (doc.get(field) or 0) + value


class FakeDb:
    def __init__(self, org_modules: List[str]):
        self.roles = FakeCollection()
        self.plans = FakeCollection()
        self.feature_flags = FakeCollection(
            [{"_id": "sales.invoices.view", "key": "sales.invoices.view", "enabled": False}]
        )
        self.org_entitlements = FakeCollection(
            [
                {
                    "_id": ORG_ENTITLEMENT_ID,
                    "plan_id": PLAN_ENTERPRISE,
                    "enabled_modules": list(org_modules),
                    "version": 3,
                }
            ]
        )


def _run_crm_migration(org_modules: List[str]) -> FakeDb:
    import importlib

    migration = importlib.import_module(
        "vaybooks.bms.infrastructure.db.migrations.versions.017_crm_entitlements"
    )
    db = FakeDb(org_modules)
    migration.up(db)
    return db


def test_crm_migration_seeds_roles_flags_and_enables_module():
    legacy_modules = [m for m in ALL_MODULES if m != MODULE_CRM]
    db = _run_crm_migration(legacy_modules)

    for role_id in (ROLE_SALES_REP, ROLE_SALES_MANAGER, ROLE_CRM_ADMIN, ROLE_COLLECTIONS):
        assert role_id in db.roles.docs
        assert db.roles.docs[role_id]["is_system"] is True
    assert "crm.leads.view" in db.roles.docs[ROLE_OWNER]["permission_keys"]

    assert "crm.leads.view" in db.feature_flags.docs
    # Flags an admin already turned off are never re-enabled.
    assert db.feature_flags.docs["sales.invoices.view"]["enabled"] is False

    org = db.org_entitlements.docs[ORG_ENTITLEMENT_ID]
    assert MODULE_CRM in org["enabled_modules"]
    assert org["version"] == 4


def test_crm_migration_respects_restricted_modules():
    db = _run_crm_migration([MODULE_CORE, MODULE_SETTINGS, MODULE_SALES])
    org = db.org_entitlements.docs[ORG_ENTITLEMENT_ID]
    assert MODULE_CRM not in org["enabled_modules"]
    assert org["version"] == 4


def test_existing_roles_keep_their_permissions():
    sales = _role_keys(ROLE_SALES)
    assert {"sales.invoices.view", "parties.customers.view"} <= sales
    assert not any(k.startswith("crm.") for k in sales)
    auditor_keys = _role_keys(ROLE_AUDITOR)
    assert "crm.records.view_all" in auditor_keys
    assert "crm.leads.create" not in auditor_keys
