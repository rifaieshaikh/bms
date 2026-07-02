import pytest

from vaybooks.bms.domain.accounting.services import AccountingDomainService
from vaybooks.bms.domain.shared.exceptions import DuplicateCustomerAccountError
from tests.conftest import FakeAccountRepository, FakeVoucherRepository


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
