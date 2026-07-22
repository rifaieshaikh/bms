import pytest

from vaybooks.bms.domain.finance.accounting.services import AccountingDomainService
from vaybooks.bms.domain.shared.enums import AccountType
from vaybooks.bms.domain.shared.exceptions import DuplicateWorkerAccountError
from tests.conftest import FakeAccountRepository, FakeVoucherRepository


def test_no_duplicate_worker_salary_account():
    repo = FakeAccountRepository()
    service = AccountingDomainService(repo, FakeVoucherRepository())
    service.create_worker_salary_account("worker-1", "Salary - Ravi")
    with pytest.raises(DuplicateWorkerAccountError):
        service.create_worker_salary_account("worker-1", "Salary - Ravi")


def test_ensure_worker_salary_account_idempotent():
    repo = FakeAccountRepository()
    service = AccountingDomainService(repo, FakeVoucherRepository())
    acc1 = service.ensure_worker_salary_account("worker-1", "Salary - Ravi")
    acc2 = service.ensure_worker_salary_account("worker-1", "Salary - Ravi")
    assert acc1.id == acc2.id
    assert acc1.is_salary_account is True
    assert acc1.account_type == AccountType.LIABILITY
