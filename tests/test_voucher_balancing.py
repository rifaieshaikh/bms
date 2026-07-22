from datetime import datetime

import pytest

from vaybooks.bms.domain.finance.accounting.entities import Voucher, VoucherLine
from vaybooks.bms.domain.finance.accounting.services import AccountingDomainService
from vaybooks.bms.domain.shared.enums import VoucherType
from vaybooks.bms.domain.shared.exceptions import UnbalancedVoucherError
from tests.conftest import FakeAccountRepository, FakeVoucherRepository


def test_balanced_voucher_passes():
    repo = FakeAccountRepository()
    voucher_repo = FakeVoucherRepository()
    service = AccountingDomainService(repo, voucher_repo)
    voucher = Voucher(
        voucher_number="VCH-0001",
        voucher_type=VoucherType.RECEIPT,
        voucher_date=datetime.utcnow(),
        description="Test",
        lines=[
            VoucherLine("a1", "Cash", debit_amount=1000),
            VoucherLine("a2", "Customer", credit_amount=1000),
        ],
    )
    service.validate_voucher(voucher)


def test_unbalanced_voucher_fails():
    repo = FakeAccountRepository()
    voucher_repo = FakeVoucherRepository()
    service = AccountingDomainService(repo, voucher_repo)
    voucher = Voucher(
        voucher_number="VCH-0002",
        voucher_type=VoucherType.RECEIPT,
        voucher_date=datetime.utcnow(),
        description="Test",
        lines=[
            VoucherLine("a1", "Cash", debit_amount=1000),
            VoucherLine("a2", "Customer", credit_amount=500),
        ],
    )
    with pytest.raises(UnbalancedVoucherError):
        service.validate_voucher(voucher)
