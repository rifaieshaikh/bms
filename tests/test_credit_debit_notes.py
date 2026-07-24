"""Tests for Finance credit notes and debit notes."""

from datetime import date

import pytest

from tests.conftest import FakeAccountRepository, FakeCounterRepository, FakeVoucherRepository
from vaybooks.bms.application.finance.accounting.service import AccountingAppService
from vaybooks.bms.domain.finance.accounting.entities import Account
from vaybooks.bms.domain.shared.enums import AccountType, VoucherType
from vaybooks.bms.domain.shared.exceptions import ValidationError


def _accounting() -> AccountingAppService:
    accounts = FakeAccountRepository()
    customer = Account(
        account_name="Customer A",
        account_type=AccountType.ASSET,
        linked_customer_id="c1",
    )
    vendor = Account(
        account_name="Vendor A",
        account_type=AccountType.LIABILITY,
        linked_vendor_id="v1",
    )
    sales = Account(account_name="Sales", account_type=AccountType.REVENUE)
    expense = Account(
        account_name="Material Purchase Expense",
        account_type=AccountType.EXPENSE,
    )
    cash = Account(
        account_name="Cash",
        account_type=AccountType.ASSET,
        is_store_account=True,
    )
    for acct in (customer, vendor, sales, expense, cash):
        accounts.save(acct)
    return AccountingAppService(accounts, FakeVoucherRepository(), FakeCounterRepository())


def _ids(accounting: AccountingAppService):
    customer = accounting.get_customer_account("c1")
    vendor = accounting.get_vendor_account("v1")
    sales = accounting.get_sales_account()
    expense = accounting.get_expense_accounts()[0]
    cash = accounting.get_store_accounts()[0]
    return customer, vendor, sales, expense, cash


def test_customer_credit_note_posting():
    accounting = _accounting()
    customer, _, sales, _, _ = _ids(accounting)
    voucher = accounting.create_credit_note(
        party_kind="customer",
        party_account_id=customer.id,
        amount=500.0,
        description="CN customer",
        contra_account_id=sales.id,
        voucher_date=date.today(),
    )
    assert voucher.voucher_type == VoucherType.CREDIT_NOTE
    assert voucher.is_balanced
    assert abs(voucher.total_debit - 500.0) < 0.01
    cust_credit = sum(
        l.credit_amount for l in voucher.lines if l.account_id == customer.id
    )
    sales_debit = sum(
        l.debit_amount for l in voucher.lines if l.account_id == sales.id
    )
    assert cust_credit == 500.0
    assert sales_debit == 500.0


def test_customer_debit_note_posting():
    accounting = _accounting()
    customer, _, sales, _, _ = _ids(accounting)
    voucher = accounting.create_debit_note(
        party_kind="customer",
        party_account_id=customer.id,
        amount=250.0,
        description="DN customer",
        contra_account_id=sales.id,
    )
    assert voucher.voucher_type == VoucherType.DEBIT_NOTE
    assert voucher.is_balanced
    cust_debit = sum(
        l.debit_amount for l in voucher.lines if l.account_id == customer.id
    )
    sales_credit = sum(
        l.credit_amount for l in voucher.lines if l.account_id == sales.id
    )
    assert cust_debit == 250.0
    assert sales_credit == 250.0


def test_vendor_credit_note_posting():
    accounting = _accounting()
    _, vendor, _, expense, _ = _ids(accounting)
    voucher = accounting.create_credit_note(
        party_kind="vendor",
        party_account_id=vendor.id,
        amount=300.0,
        description="CN vendor",
        contra_account_id=expense.id,
    )
    assert voucher.voucher_type == VoucherType.CREDIT_NOTE
    assert voucher.is_balanced
    vendor_debit = sum(
        l.debit_amount for l in voucher.lines if l.account_id == vendor.id
    )
    expense_credit = sum(
        l.credit_amount for l in voucher.lines if l.account_id == expense.id
    )
    assert vendor_debit == 300.0
    assert expense_credit == 300.0


def test_vendor_debit_note_posting():
    accounting = _accounting()
    _, vendor, _, expense, _ = _ids(accounting)
    voucher = accounting.create_debit_note(
        party_kind="vendor",
        party_account_id=vendor.id,
        amount=175.0,
        description="DN vendor",
        contra_account_id=expense.id,
    )
    assert voucher.voucher_type == VoucherType.DEBIT_NOTE
    assert voucher.is_balanced
    expense_debit = sum(
        l.debit_amount for l in voucher.lines if l.account_id == expense.id
    )
    vendor_credit = sum(
        l.credit_amount for l in voucher.lines if l.account_id == vendor.id
    )
    assert expense_debit == 175.0
    assert vendor_credit == 175.0


def test_customer_credit_note_settlement_lines():
    accounting = _accounting()
    customer, _, sales, _, cash = _ids(accounting)
    voucher = accounting.create_credit_note(
        party_kind="customer",
        party_account_id=customer.id,
        amount=400.0,
        description="CN settled",
        contra_account_id=sales.id,
        amount_settled=150.0,
        settle_account_id=cash.id,
    )
    assert voucher.is_balanced
    assert len(voucher.lines) == 4
    cash_credit = sum(
        l.credit_amount for l in voucher.lines if l.account_id == cash.id
    )
    assert cash_credit == 150.0


def test_list_by_type_isolates_notes():
    accounting = _accounting()
    customer, vendor, sales, expense, _ = _ids(accounting)
    accounting.create_credit_note(
        party_kind="customer",
        party_account_id=customer.id,
        amount=100.0,
        description="cn",
        contra_account_id=sales.id,
    )
    accounting.create_debit_note(
        party_kind="vendor",
        party_account_id=vendor.id,
        amount=80.0,
        description="dn",
        contra_account_id=expense.id,
    )
    accounting.create_receipt(
        receiving_account_id=accounting.get_store_accounts()[0].id,
        customer_account_id=customer.id,
        amount=50.0,
        description="rcpt",
    )
    credit_notes = accounting.list_vouchers_by_type(VoucherType.CREDIT_NOTE)
    debit_notes = accounting.list_vouchers_by_type(VoucherType.DEBIT_NOTE)
    receipts = accounting.list_vouchers_by_type(VoucherType.RECEIPT)
    assert len(credit_notes) == 1
    assert len(debit_notes) == 1
    assert len(receipts) == 1
    assert credit_notes[0].voucher_type == VoucherType.CREDIT_NOTE
    assert debit_notes[0].voucher_type == VoucherType.DEBIT_NOTE


def test_create_note_does_not_create_sales_return_type():
    accounting = _accounting()
    customer, _, sales, _, _ = _ids(accounting)
    accounting.create_credit_note(
        party_kind="customer",
        party_account_id=customer.id,
        amount=90.0,
        description="standalone cn",
        contra_account_id=sales.id,
    )
    assert accounting.list_vouchers_by_type(VoucherType.SALES_RETURN) == []
    assert accounting.list_vouchers_by_type(VoucherType.PURCHASE_DEBIT_NOTE) == []
    assert len(accounting.list_vouchers_by_type(VoucherType.CREDIT_NOTE)) == 1


def test_invalid_party_kind_rejected():
    accounting = _accounting()
    customer, _, sales, _, _ = _ids(accounting)
    with pytest.raises((ValueError, ValidationError)):
        accounting.create_credit_note(
            party_kind="worker",
            party_account_id=customer.id,
            amount=10.0,
            description="bad",
            contra_account_id=sales.id,
        )


def test_reference_invoice_id_stored():
    accounting = _accounting()
    customer, _, sales, _, _ = _ids(accounting)
    voucher = accounting.create_credit_note(
        party_kind="customer",
        party_account_id=customer.id,
        amount=55.0,
        description="linked",
        contra_account_id=sales.id,
        reference_invoice_id="inv-abc",
    )
    assert voucher.reference_invoice_id == "inv-abc"
