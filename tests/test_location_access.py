"""Tests for header working-location access rules."""

from vaybooks.bms.domain.entitlements.catalog import (
    ROLE_OWNER,
    ROLE_PROCUREMENT,
    ROLE_SALES,
    ROLE_STORE_ASSOCIATE,
    ROLE_WAREHOUSE_MANAGER,
)
from vaybooks.bms.domain.identity.entities import User
from vaybooks.bms.domain.identity.location_access import (
    ALL_LOCATIONS,
    accessible_locations,
    can_select_all,
    default_working_location_id,
    is_multi_location_user,
    user_location_ids,
)
from vaybooks.bms.domain.inventory.entities import Location
from vaybooks.bms.domain.shared.enums import LocationType
from vaybooks.bms.domain.shared.exceptions import ValidationError


def test_owner_is_unrestricted_even_with_location_ids():
    user = User(
        username="owner",
        role_ids=[ROLE_OWNER],
        location_ids=["loc1"],
    )
    assert user_location_ids(user) is None


def test_assigned_locations_restrict_user():
    user = User(
        username="clerk",
        role_ids=[ROLE_STORE_ASSOCIATE],
        location_ids=["store-a", "store-b"],
    )
    assert user_location_ids(user) == ["store-a", "store-b"]


def test_empty_assignment_is_unrestricted():
    user = User(username="sales", role_ids=["role_sales"], location_ids=[])
    assert user_location_ids(user) == []


def test_multi_location_roles_are_explicit():
    assert is_multi_location_user(
        User(username="wm", role_ids=[ROLE_WAREHOUSE_MANAGER])
    )
    assert is_multi_location_user(
        User(username="buyer", role_ids=[ROLE_PROCUREMENT])
    )
    assert not is_multi_location_user(
        User(username="sales", role_ids=[ROLE_SALES])
    )


class _Inventory:
    def __init__(self, locations):
        self.locations = locations

    def list_locations(self, active_only=True):
        return [loc for loc in self.locations if loc.is_active or not active_only]


def test_accessible_locations_by_assignment():
    wh = Location(code="MAIN", name="Main", location_type=LocationType.WAREHOUSE)
    store = Location(
        code="S1", name="Store", location_type=LocationType.RETAIL_STORE
    )
    user = User(
        username="assoc",
        role_ids=[ROLE_STORE_ASSOCIATE],
        location_ids=[store.id],
    )
    filtered = accessible_locations(user, _Inventory([wh, store]))
    assert [loc.id for loc in filtered] == [store.id]


def test_owner_accesses_every_active_location():
    wh = Location(code="MAIN", name="Main", location_type=LocationType.WAREHOUSE)
    store = Location(
        code="S1", name="Store", location_type=LocationType.RETAIL_STORE
    )
    user = User(username="owner", role_ids=[ROLE_OWNER])
    filtered = accessible_locations(user, _Inventory([wh, store]))
    assert [loc.id for loc in filtered] == [wh.id, store.id]


def test_single_location_defaults_to_that_location():
    loc = Location(code="S1", name="Store")
    user = User(username="sales", role_ids=[ROLE_SALES], location_ids=[loc.id])
    assert default_working_location_id(user, [loc]) == loc.id
    assert not can_select_all(user, [loc])


def test_multi_location_defaults_to_all_and_can_select_all():
    a = Location(code="A", name="A")
    b = Location(code="B", name="B")
    user = User(
        username="wm",
        role_ids=[ROLE_WAREHOUSE_MANAGER],
        location_ids=[a.id, b.id],
    )
    assert can_select_all(user, [a, b])
    assert default_working_location_id(user, [a, b]) == ALL_LOCATIONS


def test_require_specific_location_blocks_all(monkeypatch):
    from vaybooks.bms.ui.auth import session

    monkeypatch.setattr(
        session, "ensure_working_location", lambda _services: ALL_LOCATIONS
    )
    try:
        session.require_specific_location({})
    except ValidationError as exc:
        assert "Select a specific location" in str(exc)
    else:
        raise AssertionError("All locations must block document creation")


def test_require_specific_location_returns_location(monkeypatch):
    from vaybooks.bms.ui.auth import session

    monkeypatch.setattr(
        session, "ensure_working_location", lambda _services: "loc-1"
    )
    assert session.require_specific_location({}) == "loc-1"
