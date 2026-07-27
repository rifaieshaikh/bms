"""Tests for invoice settlement, FIFO receipts, credit→advance."""

from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

from tests.conftest import FakeAccountRepository, FakeCounterRepository, FakeVoucherRepository
from vaybooks.bms.application.finance.accounting.service import AccountingAppService
from vaybooks.bms.domain.finance.accounting.entities import Account, Voucher, VoucherLine
from vaybooks.bms.domain.finance.accounting.sales_parsing import (
    sales_amounts_from_lines,
    sales_row_from_voucher,
)
from vaybooks.bms.domain.finance.accounting.services import ADVANCE_FROM_CUSTOMERS_ACCOUNT_NAME
from vaybooks.bms.domain.finance.accounting.settlement import (
    append_meta,
    allocation_rows_from_meta,
    fifo_allocations,
    payment_status,
    resolve_receipt_allocations,
    single_invoice_allocation,
)
from vaybooks.bms.domain.shared.enums import AccountType, VoucherType


def _seed(repo: FakeAccountRepository) -> dict[str, Account]:
    accounts = {
        "cash": Account(
            id="cash",
            account_name="Cash Drawer",
            account_type=AccountType.ASSET,
            is_store_account=True,
        ),
        "advance": Account(
            id="advance",
            account_name=ADVANCE_FROM_CUSTOMERS_ACCOUNT_NAME,
            account_type=AccountType.LIABILITY,
        ),
        "customer": Account(
            id="customer",
            account_name="Customer - Test",
            account_type=AccountType.ASSET,
            linked_customer_id="cust-1",
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


def _service() -> AccountingAppService:
    return AccountingAppService(
        FakeAccountRepository(),
        FakeVoucherRepository(),
        FakeCounterRepository(),
    )


def _invoice_voucher(
    customer: Account,
    sales: Account,
    *,
    net: float,
    collected: float = 0.0,
    sale_date: date | None = None,
) -> Voucher:
    lines = [
        VoucherLine(
            account_id=customer.id,
            account_name=customer.account_name,
            debit_amount=net,
            credit_amount=0,
            description="Store invoice INV-1",
        ),
        VoucherLine(
            account_id=sales.id,
            account_name=sales.account_name,
            debit_amount=0,
            credit_amount=net,
            description="Sales invoice",
        ),
    ]
    if collected > 0:
        lines.extend(
            [
                VoucherLine(
                    account_id="cash",
                    account_name="Cash",
                    debit_amount=collected,
                    credit_amount=0,
                    description="Cash/Bank received",
                ),
                VoucherLine(
                    account_id=customer.id,
                    account_name=customer.account_name,
                    debit_amount=0,
                    credit_amount=collected,
                    description="Payment received",
                ),
            ]
        )
    return Voucher(
        id=str(uuid4()),
        voucher_number="SI-1",
        voucher_type=VoucherType.SALES_INVOICE,
        voucher_date=datetime.combine(
            sale_date or date(2026, 4, 1), datetime.min.time()
        ),
        description="Store invoice INV-1",
        lines=lines,
    )


def test_fifo_allocations_oldest_first():
    open_invoices = [
        {"id": "a", "outstanding": 100},
        {"id": "b", "outstanding": 50},
        {"id": "c", "outstanding": 80},
    ]
    rows = fifo_allocations(120, open_invoices)
    assert rows == [
        {"invoice_id": "a", "amount": 100.0},
        {"invoice_id": "b", "amount": 20.0},
    ]


def test_single_invoice_allocation_caps_at_outstanding():
    rows = single_invoice_allocation(500, "inv-1", 120)
    assert rows == [{"invoice_id": "inv-1", "amount": 120.0}]


def test_resolve_selected_vs_fifo():
    open_invoices = [
        {"id": "old", "outstanding": 100},
        {"id": "new", "outstanding": 200},
    ]
    selected, unalloc = resolve_receipt_allocations(
        150,
        allocation_invoice_id="new",
        open_invoices=open_invoices,
    )
    assert selected == [{"invoice_id": "new", "amount": 150.0}]
    assert unalloc == 0.0

    fifo_rows, fifo_unalloc = resolve_receipt_allocations(
        150,
        open_invoices=open_invoices,
    )
    assert fifo_rows[0]["invoice_id"] == "old"
    assert fifo_rows[0]["amount"] == 100.0
    assert fifo_rows[1]["invoice_id"] == "new"
    assert fifo_rows[1]["amount"] == 50.0
    assert fifo_unalloc == 0.0


def test_overpay_leaves_unallocated():
    rows, unalloc = resolve_receipt_allocations(
        300,
        allocation_invoice_id="inv",
        selected_outstanding=100,
    )
    assert rows == [{"invoice_id": "inv", "amount": 100.0}]
    assert unalloc == 200.0


def test_payment_status_tiers():
    assert payment_status(100, 0) == "unpaid"
    assert payment_status(100, 40) == "partially_paid"
    assert payment_status(100, 100) == "paid"
    assert payment_status(100, 100.005) == "paid"


def test_sales_amounts_include_advance_applied():
    lines = [
        VoucherLine(
            account_id="c",
            account_name="Cust",
            debit_amount=1000,
            credit_amount=0,
            description="inv",
        ),
        VoucherLine(
            account_id="s",
            account_name="Sales",
            debit_amount=0,
            credit_amount=1000,
            description="Sales invoice",
        ),
        VoucherLine(
            account_id="adv",
            account_name="Advance",
            debit_amount=400,
            credit_amount=0,
            description="Advance applied",
        ),
        VoucherLine(
            account_id="c",
            account_name="Cust",
            debit_amount=0,
            credit_amount=400,
            description="Advance applied",
        ),
    ]
    amounts = sales_amounts_from_lines(lines)
    assert amounts["net"] == 1000
    assert amounts["collected"] == 400
    assert amounts["outstanding"] == 600
    assert amounts["payment_status"] == "partially_paid"


def test_receipt_allocates_fifo_and_marks_paid():
    svc = _service()
    accounts = _seed(svc._account_repo)
    inv1 = _invoice_voucher(
        accounts["customer"], accounts["sales"], net=100, sale_date=date(2026, 4, 1)
    )
    inv2 = _invoice_voucher(
        accounts["customer"], accounts["sales"], net=50, sale_date=date(2026, 4, 2)
    )
    svc._voucher_repo.save(inv1)
    svc._voucher_repo.save(inv2)
    accounts["customer"].current_balance = 150.0

    receipt = svc.create_receipt(
        accounts["cash"].id,
        accounts["customer"].id,
        150,
        "Payment",
        voucher_date=date(2026, 4, 3),
    )
    meta_rows = allocation_rows_from_meta(receipt.description)
    assert {r["invoice_id"] for r in meta_rows} == {inv1.id, inv2.id}
    assert sum(r["amount"] for r in meta_rows) == 150.0

    settlement = svc.invoice_settlement_map()
    row1 = svc.enrich_sales_invoice_row(inv1, settlement_map=settlement)
    row2 = svc.enrich_sales_invoice_row(inv2, settlement_map=settlement)
    assert row1["payment_status"] == "paid"
    assert row2["payment_status"] == "paid"
    assert row1["outstanding"] == 0
    assert row2["outstanding"] == 0


def test_receipt_selected_invoice_only():
    svc = _service()
    accounts = _seed(svc._account_repo)
    inv1 = _invoice_voucher(
        accounts["customer"], accounts["sales"], net=100, sale_date=date(2026, 4, 1)
    )
    inv2 = _invoice_voucher(
        accounts["customer"], accounts["sales"], net=100, sale_date=date(2026, 4, 2)
    )
    svc._voucher_repo.save(inv1)
    svc._voucher_repo.save(inv2)
    accounts["customer"].current_balance = 200.0

    receipt = svc.create_receipt(
        accounts["cash"].id,
        accounts["customer"].id,
        80,
        "Partial",
        allocation_invoice_id=inv2.id,
    )
    rows = allocation_rows_from_meta(receipt.description)
    assert rows == [{"invoice_id": inv2.id, "amount": 80.0}]

    settlement = svc.invoice_settlement_map()
    row1 = svc.enrich_sales_invoice_row(inv1, settlement_map=settlement)
    row2 = svc.enrich_sales_invoice_row(inv2, settlement_map=settlement)
    assert row1["payment_status"] == "unpaid"
    assert row2["payment_status"] == "partially_paid"
    assert row2["outstanding"] == 20.0


def test_credit_to_advance_increases_unapplied_pool():
    svc = _service()
    accounts = _seed(svc._account_repo)
    accounts["customer"].current_balance = -500.0

    voucher = svc.allocate_customer_credit_to_advance(
        customer_account_id=accounts["customer"].id,
        amount=200,
        reference_order_id="order-1",
        description="Credit to advance",
    )
    assert voucher.voucher_type == VoucherType.ADVANCE
    assert voucher.reference_order_id == "order-1"
    assert voucher.cash_movement_amount == 0.0

    unapplied = svc.get_order_unapplied_advance("order-1")
    assert unapplied == 200.0
    assert abs(accounts["customer"].current_balance - (-300.0)) < 0.01


def test_credit_note_allocates_to_source_invoice():
    svc = _service()
    accounts = _seed(svc._account_repo)
    inv = _invoice_voucher(accounts["customer"], accounts["sales"], net=1000)
    svc._voucher_repo.save(inv)

    cn = svc.create_credit_note(
        party_kind="customer",
        party_account_id=accounts["customer"].id,
        amount=250,
        description="Price adjustment",
        contra_account_id=accounts["sales"].id,
        reference_invoice_id=inv.id,
        amount_settled=0,
    )
    assert cn.reference_invoice_id == inv.id

    settlement = svc.invoice_settlement_map()
    row = svc.enrich_sales_invoice_row(inv, settlement_map=settlement)
    assert row["collected"] == 250.0
    assert row["outstanding"] == 750.0
    assert row["payment_status"] == "partially_paid"


def test_credit_applied_meta_on_sales_row():
    voucher = Voucher(
        id="v1",
        voucher_number="1",
        voucher_type=VoucherType.SALES_INVOICE,
        voucher_date=datetime(2026, 4, 1),
        description=append_meta(
            "Store invoice X",
            "CREDIT_APPLIED",
            {"amount": 150},
        ),
        lines=[
            VoucherLine(
                account_id="c",
                account_name="Cust",
                debit_amount=500,
                credit_amount=0,
                description="x",
            ),
            VoucherLine(
                account_id="s",
                account_name="Sales",
                debit_amount=0,
                credit_amount=500,
                description="Sales invoice",
            ),
            VoucherLine(
                account_id="cash",
                account_name="Cash",
                debit_amount=350,
                credit_amount=0,
                description="Cash/Bank received",
            ),
        ],
    )
    row = sales_row_from_voucher(voucher)
    assert row["collected"] == 500.0
    assert row["outstanding"] == 0.0
    assert row["payment_status"] == "paid"
