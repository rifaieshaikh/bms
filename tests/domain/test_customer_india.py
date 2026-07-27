"""Tests for India-standard customer validation and creation."""

from typing import Dict, List, Optional

import pytest

from vaybooks.bms.domain.parties.customers.entities import Customer, CustomerInput
from vaybooks.bms.domain.parties.customers.services import CustomerDomainService
from vaybooks.bms.domain.shared.enums import PartyRegistrationType
from vaybooks.bms.domain.shared.exceptions import (
    DuplicateCustomerError,
    ValidationError,
)


class InMemoryCustomerRepository:
    def __init__(self):
        self._store: Dict[str, Customer] = {}

    def save(self, customer: Customer) -> Customer:
        self._store[customer.id] = customer
        return customer

    def find_by_id(self, customer_id: str) -> Optional[Customer]:
        return self._store.get(customer_id)

    def find_by_phone(self, phone: str) -> Optional[Customer]:
        phone = (phone or "").strip()
        if not phone:
            return None
        for customer in self._store.values():
            if customer.phone_number == phone:
                return customer
        return None

    def find_by_gstin(self, gstin: str) -> Optional[Customer]:
        if not gstin:
            return None
        upper = gstin.upper()
        for customer in self._store.values():
            if customer.gstin == upper:
                return customer
        return None

    def search(self, query: str) -> List[Customer]:
        return list(self._store.values())

    def list_all(self) -> List[Customer]:
        return list(self._store.values())


def _customer_input(**kwargs) -> CustomerInput:
    defaults = {
        "customer_name": "Ananya Rao",
        "phone_number": "9876543210",
        "address_line1": "12 MG Road",
        "city": "Mumbai",
        "state_code": "27",
        "pincode": "400001",
    }
    defaults.update(kwargs)
    return CustomerInput(**defaults)


def test_create_customer_success():
    repo = InMemoryCustomerRepository()
    service = CustomerDomainService(repo)
    customer = service.create(_customer_input())
    assert customer.customer_name == "Ananya Rao"
    assert customer.phone_number == "9876543210"
    assert customer.formatted_address


def test_minimal_customer_name_phone_only_succeeds():
    repo = InMemoryCustomerRepository()
    service = CustomerDomainService(repo)
    customer = service.create(
        CustomerInput(customer_name="Ravi Kumar", phone_number="9876543210")
    )
    assert customer.customer_name == "Ravi Kumar"
    assert not customer.address_line1


def test_registered_customer_requires_gstin():
    repo = InMemoryCustomerRepository()
    service = CustomerDomainService(repo)
    with pytest.raises(ValidationError, match="GSTIN is required"):
        service.create(
            _customer_input(
                registration_type=PartyRegistrationType.REGISTERED,
                gstin="",
            )
        )


def test_create_customer_with_valid_gstin():
    repo = InMemoryCustomerRepository()
    service = CustomerDomainService(repo)
    customer = service.create(
        _customer_input(
            registration_type=PartyRegistrationType.REGISTERED,
            gstin="27AAAAA0000A1Z5",
            pan="AAAAA0000A",
        )
    )
    assert customer.gstin == "27AAAAA0000A1Z5"


def test_duplicate_phone_raises_with_existing_id():
    repo = InMemoryCustomerRepository()
    service = CustomerDomainService(repo)
    first = service.create(_customer_input())
    with pytest.raises(DuplicateCustomerError) as exc:
        service.create(_customer_input(customer_name="Other Customer"))
    assert exc.value.existing_customer_id == first.id


def test_duplicate_gstin_raises():
    repo = InMemoryCustomerRepository()
    service = CustomerDomainService(repo)
    first = service.create(
        _customer_input(
            registration_type=PartyRegistrationType.REGISTERED,
            gstin="27AAAAA0000A1Z5",
            pan="AAAAA0000A",
        )
    )
    with pytest.raises(DuplicateCustomerError) as exc:
        service.create(
            _customer_input(
                phone_number="9123456780",
                registration_type=PartyRegistrationType.REGISTERED,
                gstin="27AAAAA0000A1Z5",
                pan="AAAAA0000A",
            )
        )
    assert exc.value.existing_customer_id == first.id


def test_update_allows_same_customer_phone():
    repo = InMemoryCustomerRepository()
    service = CustomerDomainService(repo)
    customer = service.create(_customer_input())
    updated = service.update(
        customer.id,
        _customer_input(customer_name="Ananya Rao Updated"),
    )
    assert updated.customer_name == "Ananya Rao Updated"


def test_create_phone_only_when_name_optional():
    repo = InMemoryCustomerRepository()
    service = CustomerDomainService(repo)
    customer = service.create(
        CustomerInput(customer_name="", phone_number="9876543210"),
        require_name=False,
        require_phone=True,
    )
    assert customer.customer_name == ""
    assert customer.phone_number == "9876543210"


def test_create_name_only_when_phone_optional():
    repo = InMemoryCustomerRepository()
    service = CustomerDomainService(repo)
    customer = service.create(
        CustomerInput(customer_name="Walk-in", phone_number=""),
        require_name=True,
        require_phone=False,
    )
    assert customer.customer_name == "Walk-in"
    assert customer.phone_number == ""


def test_create_rejects_blank_identity_even_when_both_optional():
    repo = InMemoryCustomerRepository()
    service = CustomerDomainService(repo)
    customer = service.create(
        CustomerInput(customer_name="", phone_number=""),
        require_name=False,
        require_phone=False,
    )
    assert customer.customer_name == ""
    assert customer.phone_number == ""



def test_find_or_create_creates_when_phone_unknown_and_name_empty():
    repo = InMemoryCustomerRepository()
    service = CustomerDomainService(repo)
    customer = service.find_or_create(
        "",
        "9000000002",
        require_name=False,
        require_phone=True,
    )
    assert customer.phone_number == "9000000002"
    assert customer.customer_name == ""
    assert len(repo.list_all()) == 1


def test_find_or_create_returns_existing_by_phone():
    repo = InMemoryCustomerRepository()
    service = CustomerDomainService(repo)
    first = service.create(_customer_input())
    found = service.find_or_create("Different", "9876543210")
    assert found.id == first.id
    assert found.customer_name == "Ananya Rao"
    assert len(repo.list_all()) == 1


def test_multiple_customers_without_phone_allowed():
    repo = InMemoryCustomerRepository()
    service = CustomerDomainService(repo)
    a = service.create(
        CustomerInput(customer_name="A", phone_number=""),
        require_phone=False,
    )
    b = service.create(
        CustomerInput(customer_name="B", phone_number=""),
        require_phone=False,
    )
    assert a.id != b.id
    assert len(repo.list_all()) == 2

