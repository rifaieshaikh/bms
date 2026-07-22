import pytest

from vaybooks.bms.application.finance.accounting.service import AccountingAppService
from vaybooks.bms.domain.finance.accounting.entities import Account
from vaybooks.bms.domain.finance.accounting.services import AccountingDomainService
from vaybooks.bms.domain.shared.enums import AccountType
from vaybooks.bms.domain.shared.exceptions import DuplicateCustomerAccountError
from tests.conftest import FakeAccountRepository, FakeCounterRepository, FakeVoucherRepository


def test_no_duplicate_customer_account():
    repo = FakeAccountRepository()
    service = AccountingDomainService(repo, FakeVoucherRepository())
    service.create_customer_account("cust1", "Customer - Aysha - 9876543210")
    with pytest.raises(DuplicateCustomerAccountError):
        service.create_customer_account("cust1", "Customer - Aysha - 9876543210")


def test_ensure_customer_account_idempotent():
    repo = FakeAccountRepository()
    service = AccountingDomainService(repo, FakeVoucherRepository())
    acc1 = service.ensure_customer_account("cust1", "Customer - Aysha - 9876543210")
    acc2 = service.ensure_customer_account("cust1", "Customer - Aysha - 9876543210")
    assert acc1.id == acc2.id


def test_sync_customer_account_renames():
    repo = FakeAccountRepository()
    service = AccountingDomainService(repo, FakeVoucherRepository())
    acc = service.ensure_customer_account("cust1", "Customer - Aysha - 9876543210")
    updated = service.sync_customer_account("cust1", "Customer - Aysha - 9999999999")
    assert updated.id == acc.id
    assert updated.account_name == "Customer - Aysha - 9999999999"


def test_customer_balances_by_customer():
    repo = FakeAccountRepository()
    repo.save(
        Account(
            id="acc-1",
            account_name="Customer - A",
            account_type=AccountType.ASSET,
            linked_customer_id="cust-1",
            current_balance=1500.0,
        )
    )
    repo.save(
        Account(
            id="acc-2",
            account_name="Customer - B",
            account_type=AccountType.ASSET,
            linked_customer_id="cust-2",
            current_balance=-200.0,
        )
    )
    repo.save(
        Account(
            id="acc-3",
            account_name="Cash",
            account_type=AccountType.ASSET,
            current_balance=5000.0,
        )
    )

    service = AccountingAppService(
        repo, FakeVoucherRepository(), FakeCounterRepository()
    )

    assert service.customer_balances_by_customer() == {
        "cust-1": 1500.0,
        "cust-2": -200.0,
    }
