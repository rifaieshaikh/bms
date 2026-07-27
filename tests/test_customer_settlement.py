"""Two-step customer settlement: park receivable → approve expense."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from tests.conftest import FakeAccountRepository, FakeCounterRepository, FakeVoucherRepository
from vaybooks.bms.application.finance.accounting.service import AccountingAppService
from vaybooks.bms.domain.finance.accounting.entities import Account, Voucher, VoucherLine
from vaybooks.bms.domain.finance.accounting.services import (
    SETTLEMENT_ACCOUNT_NAME,
    SETTLEMENT_EXPENSE_ACCOUNT_NAME,
)
from vaybooks.bms.domain.finance.accounting.settlement import (
    CUSTOMER_SETTLEMENT_TAG,
    allocation_rows_from_meta,
    parse_meta,
)
from vaybooks.bms.domain.shared.enums import AccountType, VoucherType


def _seed(repo: FakeAccountRepository) -> dict[str, Account]:
    accounts = {
        "settlement": Account(
            id="settlement",
            account_name=SETTLEMENT_ACCOUNT_NAME,
            account_type=AccountType.ASSET,
        ),
        "expense": Account(
            id="settlement-expense",
            account_name=SETTLEMENT_EXPENSE_ACCOUNT_NAME,
            account_type=AccountType.EXPENSE,
        ),
        "customer": Account(
            id="customer",
            account_name="Customer - Test",
            account_type=AccountType.ASSET,
            linked_customer_id="cust-1",
            current_balance=1000.0,
        ),
        "sales": Account(
            id="sales",
            account_name="Sales",
            account_type=AccountType.REVENUE,
        ),
    }
    for account in accounts.values():
        repo.save(account)
    return accounts


def _service() -> tuple[AccountingAppService, dict[str, Account]]:
    accounts_repo = FakeAccountRepository()
    accounts = _seed(accounts_repo)
    svc = AccountingAppService(
        accounts_repo,
        FakeVoucherRepository(),
        FakeCounterRepository(),
    )
    return svc, accounts


def _post_invoice(svc: AccountingAppService, accounts: dict, *, net: float, inv_id: str) -> Voucher:
    customer = accounts["customer"]
    sales = accounts["sales"]
    voucher = Voucher(
        id=inv_id,
        voucher_number=f"INV-{inv_id}",
        voucher_type=VoucherType.SALES_INVOICE,
        voucher_date=datetime.combine(date.today(), datetime.min.time()),
        description=f"Store invoice {inv_id}",
        lines=[
            VoucherLine(
                account_id=customer.id,
                account_name=customer.account_name,
                debit_amount=net,
                credit_amount=0,
                description=f"Store invoice {inv_id}",
            ),
            VoucherLine(
                account_id=sales.id,
                account_name=sales.account_name,
                debit_amount=0,
                credit_amount=net,
                description="Sales invoice",
            ),
        ],
    )
    return svc._save_voucher(voucher)


def test_park_moves_receivable_to_settlement():
    svc, accounts = _service()
    vouchers = svc.settle_customer_balance(
        accounts["customer"].id, 400.0, mode="park", reason="Bad debt"
    )
    assert len(vouchers) == 1
    v = vouchers[0]
    assert v.voucher_type == VoucherType.JOURNAL
    meta = parse_meta(v.description or "", CUSTOMER_SETTLEMENT_TAG)
    assert meta["phase"] == "park"
    assert float(meta["amount"]) == 400.0
    assert meta["customer_account_id"] == accounts["customer"].id

    lines = {
        (ln.account_id, round(ln.debit_amount, 2), round(ln.credit_amount, 2))
        for ln in v.lines
    }
    assert ("settlement", 400.0, 0.0) in lines
    assert ("customer", 0.0, 400.0) in lines
    assert svc.customer_receivable_balance(accounts["customer"].id) == pytest.approx(600.0)
    assert svc.get_customer_parked_settlement(accounts["customer"].id) == pytest.approx(400.0)


def test_park_fifo_allocates_open_invoices():
    svc, accounts = _service()
    _post_invoice(svc, accounts, net=300.0, inv_id="inv-a")
    _post_invoice(svc, accounts, net=500.0, inv_id="inv-b")
    # Customer balance already 1000 from seed; invoices don't change balance in fake unless we update.
    # Outstanding comes from invoice lines; park allocates against open invoices.
    park = svc.park_customer_receivable_to_settlement(
        accounts["customer"].id, 400.0, reason="Write off"
    )
    rows = allocation_rows_from_meta(park.description or "")
    assert rows == [
        {"invoice_id": "inv-a", "amount": 300.0},
        {"invoice_id": "inv-b", "amount": 100.0},
    ]
    settlement_map = svc.invoice_settlement_map()
    assert settlement_map["inv-a"]["settlement_allocated"] == pytest.approx(300.0)
    assert settlement_map["inv-b"]["settlement_allocated"] == pytest.approx(100.0)
    open_rows = svc.list_open_sales_invoices_for_customer(accounts["customer"].id)
    by_id = {r["id"]: r for r in open_rows}
    assert "inv-a" not in by_id
    assert by_id["inv-b"]["outstanding"] == pytest.approx(400.0)


def test_full_mode_parks_only_pending_approval():
    svc, accounts = _service()
    vouchers = svc.settle_customer_balance(
        accounts["customer"].id, 250.0, mode="full", reason="Uncollectible"
    )
    assert len(vouchers) == 1
    assert parse_meta(vouchers[0].description or "", CUSTOMER_SETTLEMENT_TAG)["phase"] == "park"
    pending = svc.list_customer_settlements(status="pending")
    assert len(pending) == 1
    assert pending[0]["remaining"] == pytest.approx(250.0)
    assert svc.get_customer_parked_settlement(accounts["customer"].id) == pytest.approx(250.0)


def test_approve_expenses_park():
    svc, accounts = _service()
    park = svc.park_customer_receivable_to_settlement(accounts["customer"].id, 500.0)
    expense = svc.approve_customer_settlement(park.id)
    meta = parse_meta(expense.description or "", CUSTOMER_SETTLEMENT_TAG)
    assert meta["phase"] == "expense"
    assert meta["park_voucher_id"] == park.id
    assert svc.list_customer_settlements(status="pending") == []
    approved = svc.list_customer_settlements(status="approved")
    assert len(approved) == 1
    assert approved[0]["remaining"] == pytest.approx(0.0)
    assert svc.get_customer_parked_settlement(accounts["customer"].id) == pytest.approx(0.0)


def test_reject_reverses_park_and_invoice_allocation():
    svc, accounts = _service()
    _post_invoice(svc, accounts, net=200.0, inv_id="inv-r")
    park = svc.park_customer_receivable_to_settlement(accounts["customer"].id, 200.0)
    assert allocation_rows_from_meta(park.description or "")
    assert not svc.list_open_sales_invoices_for_customer(accounts["customer"].id)
    svc.reject_customer_settlement(park.id)
    assert svc._voucher_repo.find_by_id(park.id) is None
    # Seed 1000 + invoice 200, park reversed — receivable restored.
    assert svc.customer_receivable_balance(accounts["customer"].id) == pytest.approx(1200.0)
    open_rows = svc.list_open_sales_invoices_for_customer(accounts["customer"].id)
    assert len(open_rows) == 1
    assert open_rows[0]["outstanding"] == pytest.approx(200.0)


def test_reject_blocked_after_approve():
    svc, accounts = _service()
    park = svc.park_customer_receivable_to_settlement(accounts["customer"].id, 100.0)
    svc.approve_customer_settlement(park.id)
    with pytest.raises(ValueError, match="approved"):
        svc.reject_customer_settlement(park.id)


def test_park_rejects_over_receivable():
    svc, accounts = _service()
    with pytest.raises(ValueError, match="receivable"):
        svc.park_customer_receivable_to_settlement(accounts["customer"].id, 1100.0)


def test_expense_rejects_over_parked():
    svc, accounts = _service()
    svc.settle_customer_balance(accounts["customer"].id, 100.0, mode="park")
    with pytest.raises(ValueError, match="parked settlement"):
        svc.expense_customer_settlement(accounts["customer"].id, 150.0)


def test_invalid_mode_rejected():
    svc, accounts = _service()
    with pytest.raises(ValueError, match="park, expense, or full"):
        svc.settle_customer_balance(accounts["customer"].id, 10.0, mode="wipe")
