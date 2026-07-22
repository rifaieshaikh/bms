"""Tests for sales customer lookup and find-or-create flow."""

from vaybooks.bms.application.parties.customers.service import CustomerAppService
from vaybooks.bms.domain.parties.customers.entities import Customer
from vaybooks.bms.ui.components.common.customer_identity_selector import (
    CustomerIdentitySelection,
    resolve_customer_identity,
)
from tests.conftest import FakeAccountRepository, FakeCustomerRepository


def _service():
    customer_repo = FakeCustomerRepository()
    account_repo = FakeAccountRepository()
    return CustomerAppService(customer_repo, account_repo), customer_repo, account_repo


def test_lookup_returns_customer_by_phone():
    service, customer_repo, _ = _service()
    customer_repo.save(Customer(id="c1", customer_name="Aysha", phone_number="9876543210"))

    found = service.lookup_customer_by_phone("9876543210")

    assert found is not None
    assert found.id == "c1"
    assert found.customer_name == "Aysha"


def test_lookup_returns_none_when_phone_unknown():
    service, _, _ = _service()

    assert service.lookup_customer_by_phone("9000000001") is None


def test_find_or_create_trusts_existing_phone_over_name():
    service, customer_repo, account_repo = _service()
    existing = customer_repo.save(
        Customer(id="c1", customer_name="Aysha", phone_number="9876543210")
    )

    resolved = service.find_or_create_customer("Different Name", "9876543210")

    assert resolved.id == existing.id
    assert resolved.customer_name == "Aysha"
    assert account_repo.find_customer_account("c1") is not None


def test_find_or_create_creates_customer_when_phone_new():
    service, customer_repo, account_repo = _service()

    resolved = service.find_or_create_customer("New Buyer", "9000000001")

    assert resolved.customer_name == "New Buyer"
    assert resolved.phone_number == "9000000001"
    assert len(customer_repo.list_all()) == 1
    assert account_repo.find_customer_account(resolved.id) is not None


def test_customer_identity_resolves_selected_existing_customer():
    service, customer_repo, _ = _service()
    existing = customer_repo.save(
        Customer(id="c1", customer_name="Aysha", phone_number="9876543210")
    )

    resolved = resolve_customer_identity(
        service,
        CustomerIdentitySelection(
            customer_id=existing.id,
            customer_name=existing.customer_name,
            phone_number=existing.phone_number,
            customer=existing,
        ),
    )

    assert resolved.id == existing.id
    assert len(customer_repo.list_all()) == 1


def test_customer_identity_creates_new_customer_and_account():
    service, customer_repo, account_repo = _service()

    resolved = resolve_customer_identity(
        service,
        CustomerIdentitySelection(
            customer_id="",
            customer_name="New Buyer",
            phone_number="9000000001",
        ),
    )

    assert resolved.customer_name == "New Buyer"
    assert len(customer_repo.list_all()) == 1
    assert account_repo.find_customer_account(resolved.id) is not None
