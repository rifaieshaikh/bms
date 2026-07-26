"""Entitlements for the Schedulers module: catalog, pages, plans, and roles."""

import pytest

from vaybooks.bms.domain.entitlements.catalog import (
    ALL_FEATURE_KEYS,
    ALL_MODULES,
    MODULE_LABELS,
    MODULE_SCHEDULERS,
    PERMISSIONS,
    PLAN_DEFINITIONS,
    PLAN_ENTERPRISE,
    PLAN_GROWTH,
    PLAN_STARTER,
    SYSTEM_ROLE_DEFINITIONS,
    module_key,
    permission_for_page,
    permissions_for_module,
)

SCHEDULER_PAGES = (
    "schedulers-crm",
    "schedulers-sales",
    "schedulers-purchases",
    "schedulers-inventory",
    "schedulers-boutique",
    "schedulers-projects",
)

SCHEDULED_REPORT_PAGES = (
    "crm-scheduled-reports",
    "sales-scheduled-reports",
    "purchases-scheduled-reports",
    "inventory-scheduled-reports",
    "boutique-scheduled-reports",
    "projects-scheduled-reports",
)


def test_schedulers_is_a_first_class_module():
    assert MODULE_SCHEDULERS in ALL_MODULES
    assert MODULE_LABELS[MODULE_SCHEDULERS] == "Schedulers"
    assert module_key(MODULE_SCHEDULERS) in ALL_FEATURE_KEYS


def test_the_module_declares_view_run_and_edit():
    assert permissions_for_module(MODULE_SCHEDULERS) == frozenset(
        {"schedulers.view", "schedulers.run", "schedulers.edit"}
    )
    assert {"schedulers.view", "schedulers.run", "schedulers.edit"} <= set(PERMISSIONS)


@pytest.mark.parametrize("url_path", SCHEDULER_PAGES + SCHEDULED_REPORT_PAGES)
def test_every_scheduler_page_is_guarded_by_view(url_path):
    assert permission_for_page(url_path) == "schedulers.view"


def test_growth_and_enterprise_include_schedulers_but_starter_does_not():
    growth = set(PLAN_DEFINITIONS[PLAN_GROWTH]["feature_keys"])
    enterprise = set(PLAN_DEFINITIONS[PLAN_ENTERPRISE]["feature_keys"])
    starter = set(PLAN_DEFINITIONS[PLAN_STARTER]["feature_keys"])

    assert "schedulers.run" in growth and module_key(MODULE_SCHEDULERS) in growth
    assert "schedulers.run" in enterprise
    assert not any(key.startswith("schedulers.") for key in starter)


def test_owner_and_settings_admin_can_run_and_edit_schedulers():
    for role_id in ("role_owner", "role_settings_admin"):
        keys = set(SYSTEM_ROLE_DEFINITIONS[role_id]["permission_keys"])
        assert {"schedulers.view", "schedulers.run", "schedulers.edit"} <= keys


def test_the_auditor_can_look_but_not_trigger():
    keys = set(SYSTEM_ROLE_DEFINITIONS["role_auditor"]["permission_keys"])
    assert "schedulers.view" in keys
    assert "schedulers.run" not in keys and "schedulers.edit" not in keys


def test_operational_roles_do_not_inherit_scheduler_control():
    for role_id in ("role_sales_rep", "role_storekeeper", "role_site_engineer"):
        keys = set(SYSTEM_ROLE_DEFINITIONS[role_id]["permission_keys"])
        assert not any(key.startswith("schedulers.") for key in keys)


def test_the_page_helper_delegates_to_the_session_permission_check(monkeypatch):
    import vaybooks.bms.ui.auth.session as session
    from vaybooks.bms.ui.pages.schedulers._common import can

    granted = {"schedulers.view"}
    monkeypatch.setattr(
        session, "can_permission", lambda services, key, **kw: key in granted
    )

    assert can({}, "schedulers.view") is True
    assert can({}, "schedulers.run") is False
    assert can({}, "schedulers.edit") is False


def test_the_page_helper_fails_open_when_no_authorization_is_wired():
    from vaybooks.bms.ui.pages.schedulers._common import can

    assert can({}, "schedulers.run") is True
