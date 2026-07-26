from types import SimpleNamespace

from vaybooks.bms.application.parties.workers.activity_options import (
    ActivityOption,
    EmployeeActivityOptionsService,
    refs_from_keys,
)
from vaybooks.bms.domain.entitlements.catalog import (
    MODULE_BOUTIQUE,
    MODULE_CORE,
    MODULE_PROJECTS,
    MODULE_SETTINGS,
)
from vaybooks.bms.domain.parties.workers.entities import (
    SOURCE_CUSTOMIZATION,
    SOURCE_PROJECT,
    SOURCE_STORE,
    WorkerActivityRef,
)


class _FakePlans:
    def __init__(self, modules):
        self._modules = modules

    def get_org_entitlement(self):
        return SimpleNamespace(enabled_modules=list(self._modules))


class _FakeCatalog:
    def __init__(self, activities):
        self._activities = activities

    def list_activities(self, active_only: bool = True):
        if active_only:
            return [a for a in self._activities if a.is_active]
        return list(self._activities)

    def get_activity(self, activity_id: str):
        for activity in self._activities:
            if activity.id == activity_id:
                return activity
        return None


def _activity(activity_id, name, is_active=True):
    return SimpleNamespace(id=activity_id, activity_name=name, is_active=is_active)


def _service(modules):
    return EmployeeActivityOptionsService(
        _FakePlans(modules),
        _FakeCatalog([_activity("s1", "Billing"), _activity("s2", "Packing", False)]),
        _FakeCatalog([_activity("c1", "Cutting")]),
        _FakeCatalog([_activity("p1", "Electrical")]),
    )


_BASE = [MODULE_CORE, MODULE_SETTINGS]


def _sources(options):
    return {o.source for o in options}


def test_neither_module_loads_store_only():
    options = _service(_BASE).list_options()
    assert _sources(options) == {SOURCE_STORE}
    assert [o.activity_id for o in options] == ["s1"]  # inactive s2 hidden


def test_boutique_loads_store_plus_customization():
    options = _service(_BASE + [MODULE_BOUTIQUE]).list_options()
    assert _sources(options) == {SOURCE_STORE, SOURCE_CUSTOMIZATION}


def test_projects_loads_store_plus_project():
    options = _service(_BASE + [MODULE_PROJECTS]).list_options()
    assert _sources(options) == {SOURCE_STORE, SOURCE_PROJECT}


def test_both_modules_load_all_catalogs():
    options = _service(_BASE + [MODULE_BOUTIQUE, MODULE_PROJECTS]).list_options()
    assert _sources(options) == {SOURCE_STORE, SOURCE_CUSTOMIZATION, SOURCE_PROJECT}


def test_labels_carry_source_and_keys_are_composite():
    options = _service(_BASE + [MODULE_BOUTIQUE]).list_options()
    by_key = {o.key: o for o in options}
    assert by_key["store:s1"].label == "Billing · Store"
    assert by_key["customization:c1"].label == "Cutting · Customization"


def test_options_for_refs_keeps_disabled_module_and_inactive_refs():
    svc = _service(_BASE)  # boutique and projects disabled
    refs = [
        WorkerActivityRef(activity_id="c1", source=SOURCE_CUSTOMIZATION),
        WorkerActivityRef(activity_id="s2", source=SOURCE_STORE),
        WorkerActivityRef(activity_id="missing", source=SOURCE_STORE),
    ]
    resolved = svc.options_for_refs(refs)
    assert len(resolved) == 3
    assert resolved[0].label == "Cutting · Customization (module disabled)"
    assert resolved[1].label == "Packing · Store (inactive)"
    assert "Unknown activity" in resolved[2].label


def test_refs_from_keys_roundtrip():
    refs = refs_from_keys(["store:s1", "customization:c1", "bad-key", ""])
    assert refs == [
        WorkerActivityRef(activity_id="s1", source="store"),
        WorkerActivityRef(activity_id="c1", source="customization"),
    ]
    option = ActivityOption(
        activity_id="s1", activity_name="Billing", source="store",
        label="Billing · Store",
    )
    assert option.key == "store:s1"
    assert option.ref == WorkerActivityRef(activity_id="s1", source="store")
