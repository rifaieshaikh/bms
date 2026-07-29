"""Location association helpers and party/document location rules."""

import pytest

from vaybooks.bms.domain.identity.location_access import (
    ALL_LOCATIONS,
    location_id_mongo_filter,
    location_ids_mongo_filter,
    merge_mongo_filters,
)
from vaybooks.bms.domain.parties.customers.entities import CustomerInput
from vaybooks.bms.domain.parties.customers.services import CustomerDomainService
from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.domain.shared import party_location
from vaybooks.bms.domain.shared.party_location import (
    normalize_location_ids,
    require_location_id,
    require_location_ids,
)
from tests.domain.test_customer_india import InMemoryCustomerRepository


@pytest.fixture(autouse=True)
def _strict_location_validation():
    party_location.set_strict_location_validation(True)
    yield
    party_location.set_strict_location_validation(False)


def test_require_location_ids_rejects_empty():
    with pytest.raises(ValidationError, match="at least one location"):
        require_location_ids([])
    with pytest.raises(ValidationError, match="at least one location"):
        require_location_ids(None)


def test_require_location_ids_normalizes():
    assert require_location_ids([" a ", "a", "b", ""]) == ["a", "b"]


def test_require_location_id_rejects_blank():
    with pytest.raises(ValidationError, match="Location is required"):
        require_location_id("")
    with pytest.raises(ValidationError, match="Location is required"):
        require_location_id(None)
    assert require_location_id("  loc-1  ") == "loc-1"


def test_normalize_location_ids_dedupes():
    assert normalize_location_ids(["x", "x", " y "]) == ["x", "y"]


def test_location_id_mongo_filter_specific():
    assert location_id_mongo_filter("loc-a", ["loc-a", "loc-b"]) == {
        "location_id": "loc-a"
    }


def test_location_id_mongo_filter_all_accessible():
    assert location_id_mongo_filter(ALL_LOCATIONS, ["loc-a", "loc-b"]) == {
        "location_id": {"$in": ["loc-a", "loc-b"]}
    }


def test_location_id_mongo_filter_all_unrestricted():
    assert location_id_mongo_filter(ALL_LOCATIONS, None) == {}


def test_location_ids_mongo_filter_party_visibility():
    assert location_ids_mongo_filter("loc-a", ["loc-a", "loc-b"]) == {
        "location_ids": "loc-a"
    }
    assert location_ids_mongo_filter(ALL_LOCATIONS, ["loc-a", "loc-b"]) == {
        "location_ids": {"$in": ["loc-a", "loc-b"]}
    }


def test_merge_mongo_filters():
    assert merge_mongo_filters({}, {"a": 1}) == {"a": 1}
    assert merge_mongo_filters({"a": 1}, {"b": 2}) == {
        "$and": [{"a": 1}, {"b": 2}]
    }


def test_customer_create_requires_location_ids():
    repo = InMemoryCustomerRepository()
    service = CustomerDomainService(repo)
    with pytest.raises(ValidationError, match="at least one location"):
        service.create(
            CustomerInput(
                customer_name="No Loc",
                phone_number="9876543210",
                location_ids=[],
            )
        )


def test_customer_create_stores_location_ids():
    repo = InMemoryCustomerRepository()
    service = CustomerDomainService(repo)
    customer = service.create(
        CustomerInput(
            customer_name="With Loc",
            phone_number="9876543211",
            location_ids=["loc-main", "loc-store"],
        )
    )
    assert customer.location_ids == ["loc-main", "loc-store"]
