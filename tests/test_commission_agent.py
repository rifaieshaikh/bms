"""Commission agent party, invoice posting, and settlement tests."""

import pytest

from vaybooks.bms.application.finance.accounting.service import AccountingAppService
from vaybooks.bms.application.parties.commission_agents.service import (
    CommissionAgentAppService,
)
from vaybooks.bms.application.parties.customers.service import CustomerAppService
from vaybooks.bms.domain.finance.accounting.entities import Account
from vaybooks.bms.domain.finance.accounting.services import AccountingDomainService
from vaybooks.bms.domain.parties.commission_agents.entities import CommissionAgentInput
from vaybooks.bms.domain.parties.customers.entities import CustomerInput
from vaybooks.bms.domain.sales.commission import compute_commission_amount
from vaybooks.bms.domain.shared.enums import AccountType, VoucherType
from vaybooks.bms.domain.shared.exceptions import DuplicateAgentAccountError
from tests.conftest import (
    FakeAccountRepository,
    FakeCounterRepository,
    FakeCustomerRepository,
    FakeVoucherRepository,
)


class FakeCommissionAgentRepository:
    def __init__(self):
        self._store = {}

    def save(self, agent):
        self._store[agent.id] = agent
        return agent

    def find_by_id(self, agent_id):
        return self._store.get(agent_id)

    def find_by_phone(self, phone):
        for a in self._store.values():
            if a.phone_number == phone:
                return a
        return None

    def find_by_gstin(self, gstin):
        gstin = (gstin or "").upper()
        if not gstin:
            return None
        for a in self._store.values():
            if (a.gstin or "").upper() == gstin:
                return a
        return None

    def find_by_source_customer_id(self, customer_id):
        for a in self._store.values():
            if a.source_customer_id == customer_id:
                return a
        return None

    def search(self, query):
        return list(self._store.values())

    def list_all(self):
        return list(self._store.values())


def test_compute_commission_percentage_on_taxable():
    assert compute_commission_amount(
        commission_type="percentage",
        commission_rate=5,
        taxable_amount=1000,
    ) == 50.0


def test_compute_commission_flat():
    assert compute_commission_amount(
        commission_type="flat",
        commission_rate=75,
        taxable_amount=1000,
    ) == 75.0


def test_ensure_agent_account():
    repo = FakeAccountRepository()
    domain = AccountingDomainService(repo, FakeVoucherRepository())
    acc = domain.ensure_agent_account("agent-1", "Agent - Broker - 9000000001")
    assert acc.account_type == AccountType.LIABILITY
    assert acc.linked_agent_id == "agent-1"
    again = domain.ensure_agent_account("agent-1", "Agent - Broker - 9000000001")
    assert again.id == acc.id
    with pytest.raises(DuplicateAgentAccountError):
        domain.create_agent_account("agent-1", "Agent - Other")


def test_create_commission_agent_creates_liability_account():
    account_repo = FakeAccountRepository()
    agent_repo = FakeCommissionAgentRepository()
    service = CommissionAgentAppService(agent_repo, account_repo)
    agent = service.create_agent(
        CommissionAgentInput(
            agent_name="Ravi Broker",
            phone_number="9876500011",
            location_ids=["loc-test"],
        )
    )
    account = account_repo.find_agent_account(agent.id)
    assert account is not None
    assert account.account_name.startswith("Agent - Ravi Broker")
    assert account.account_type == AccountType.LIABILITY


def test_customer_flag_creates_linked_agent():
    customer_repo = FakeCustomerRepository()
    account_repo = FakeAccountRepository()
    agent_repo = FakeCommissionAgentRepository()
    agent_service = CommissionAgentAppService(agent_repo, account_repo)
    customers = CustomerAppService(
        customer_repo,
        account_repo,
        commission_agent_service=agent_service,
    )
    customer = customers.create_customer(
        CustomerInput(
            customer_name="Dual Role",
            phone_number="9876500022",
            is_commission_agent=True,
            location_ids=["loc-test"],
        )
    )
    assert customer.is_commission_agent
    assert customer.commission_agent_id
    agent = agent_service.get_agent_detail(customer.commission_agent_id)
    assert agent is not None
    assert agent.source_customer_id == customer.id
    assert account_repo.find_agent_account(agent.id) is not None


def _seed_sales_accounts(repo: FakeAccountRepository) -> dict:
    accounts = {
        "cash": Account(
            id="cash",
            account_name="Cash Drawer",
            account_type=AccountType.ASSET,
            is_store_account=True,
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
        "agent": Account(
            id="agent-acc",
            account_name="Agent - Broker",
            account_type=AccountType.LIABILITY,
            linked_agent_id="agent-1",
        ),
    }
    for account in accounts.values():
        repo.save(account)
    return accounts


def test_sales_invoice_unpaid_commission_nets_sales():
    service = AccountingAppService(
        FakeAccountRepository(),
        FakeVoucherRepository(),
        FakeCounterRepository(),
    )
    accounts = _seed_sales_accounts(service._account_repo)
    voucher = service.create_cash_sales_invoice(
        accounts["customer"].id,
        accounts["cash"].id,
        gross_amount=1000.0,
        discount_amount=0.0,
        amount_received=0.0,
        store_invoice_number="SI-COMM-1",
        commission_amount=50.0,
        agent_account_id=accounts["agent"].id,
        commission_paid=False,
        location_id="loc-test",
        location_name="Test",
    )
    assert voucher.is_balanced
    sales_line = next(l for l in voucher.lines if l.description == "Sales invoice")
    assert sales_line.credit_amount == 950.0
    payable = next(l for l in voucher.lines if l.description == "Commission payable")
    assert payable.credit_amount == 50.0
    assert accounts["sales"].current_balance == -950.0
    assert accounts["agent"].current_balance == -50.0
    assert accounts["customer"].current_balance == 1000.0


def test_sales_invoice_paid_commission_reduces_cash():
    service = AccountingAppService(
        FakeAccountRepository(),
        FakeVoucherRepository(),
        FakeCounterRepository(),
    )
    accounts = _seed_sales_accounts(service._account_repo)
    voucher = service.create_cash_sales_invoice(
        accounts["customer"].id,
        accounts["cash"].id,
        gross_amount=1000.0,
        discount_amount=0.0,
        amount_received=1000.0,
        store_invoice_number="SI-COMM-2",
        commission_amount=50.0,
        agent_account_id=accounts["agent"].id,
        commission_paid=True,
        commission_pay_account_id=accounts["cash"].id,
        location_id="loc-test",
        location_name="Test",
    )
    assert voucher.is_balanced
    assert accounts["sales"].current_balance == -950.0
    # Agent payable raised and settled → net zero
    assert accounts["agent"].current_balance == 0.0
    # Cash: +1000 customer receipt, -50 commission
    assert accounts["cash"].current_balance == 950.0


def test_commission_payment_settles_payable():
    service = AccountingAppService(
        FakeAccountRepository(),
        FakeVoucherRepository(),
        FakeCounterRepository(),
    )
    accounts = _seed_sales_accounts(service._account_repo)
    service.create_cash_sales_invoice(
        accounts["customer"].id,
        accounts["cash"].id,
        gross_amount=1000.0,
        discount_amount=0.0,
        amount_received=0.0,
        store_invoice_number="SI-COMM-3",
        commission_amount=50.0,
        agent_account_id=accounts["agent"].id,
        commission_paid=False,
        location_id="loc-test",
        location_name="Test",
    )
    assert accounts["agent"].current_balance == -50.0
    pay = service.create_commission_payment(
        accounts["agent"].id,
        accounts["cash"].id,
        50.0,
        "Commission settlement",
        reference_invoice_id="inv-ref",
    )
    assert pay.voucher_type == VoucherType.COMMISSION_PAYMENT
    assert accounts["agent"].current_balance == 0.0
    assert accounts["cash"].current_balance == -50.0


def test_compute_commission_reversal_proportional_to_taxable():
    from vaybooks.bms.domain.sales.commission import (
        compute_commission_reversal_for_return,
    )

    amount = compute_commission_reversal_for_return(
        commission_amount=50.0,
        invoice_taxable=1000.0,
        invoice_items=[
            {"product_id": "p1", "qty": 10, "taxable_amount": 1000.0},
        ],
        return_lines=[{"product_id": "p1", "qty": 4}],
    )
    assert amount == 20.0


def test_sales_return_reverses_agent_commission():
    service = AccountingAppService(
        FakeAccountRepository(),
        FakeVoucherRepository(),
        FakeCounterRepository(),
    )
    accounts = _seed_sales_accounts(service._account_repo)
    invoice = service.create_cash_sales_invoice(
        accounts["customer"].id,
        accounts["cash"].id,
        gross_amount=1000.0,
        discount_amount=0.0,
        amount_received=0.0,
        store_invoice_number="SI-COMM-RET",
        commission_amount=50.0,
        agent_account_id=accounts["agent"].id,
        commission_paid=False,
        location_id="loc-test",
        location_name="Test",
    )
    assert accounts["agent"].current_balance == -50.0
    ret = service.create_sales_return_voucher(
        customer_account_id=accounts["customer"].id,
        return_amount=400.0,
        description='Sales return SR-1\n{"commission":{"agent_id":"agent-1","commission_amount":20.0,"reversed":true}}',
        source_invoice_id=invoice.id,
        commission_reversal=20.0,
        agent_account_id=accounts["agent"].id,
    )
    assert ret.is_balanced
    reversed_line = next(
        l for l in ret.lines if l.description == "Commission reversed" and l.debit_amount > 0
    )
    assert reversed_line.account_id == accounts["agent"].id
    assert reversed_line.debit_amount == 20.0
    assert accounts["agent"].current_balance == -30.0


def test_commission_agent_metrics_include_sales_and_returns():
    import json
    from datetime import date

    from vaybooks.bms.application.sales.service import SalesAppService
    from vaybooks.bms.domain.sales.entities import SalesReturn, SalesReturnLine
    from vaybooks.bms.domain.shared.enums import SalesReturnStatus
    from tests.test_sales_workflow import (
        InMemoryDeliveryNoteRepository,
        InMemorySalesOrderRepository,
        InMemorySalesReturnRepository,
    )
    from tests.conftest import make_inventory_app_service

    account_repo = FakeAccountRepository()
    voucher_repo = FakeVoucherRepository()
    accounting = AccountingAppService(
        account_repo, voucher_repo, FakeCounterRepository()
    )
    accounts = _seed_sales_accounts(account_repo)
    note = {
        "items": [{"product_id": "p1", "qty": 10, "taxable_amount": 1000.0, "rate": 100}],
        "invoice_discount": 0,
        "tax_summary": {"taxable": 1000.0, "grand_total": 1000.0},
        "commission": {
            "agent_id": "agent-1",
            "agent_name": "Broker",
            "commission_type": "percentage",
            "commission_rate": 5,
            "commission_amount": 50.0,
            "commission_paid": False,
            "pay_account_id": "",
        },
    }
    invoice = accounting.create_cash_sales_invoice(
        accounts["customer"].id,
        accounts["cash"].id,
        gross_amount=1000.0,
        discount_amount=0.0,
        amount_received=0.0,
        store_invoice_number="SI-METRICS",
        line_items_note=json.dumps(note),
        commission_amount=50.0,
        agent_account_id=accounts["agent"].id,
        commission_paid=False,
        location_id="loc-test",
        location_name="Test",
    )

    returns = InMemorySalesReturnRepository()
    returns.save(
        SalesReturn(
            return_number="SR-M1",
            customer_id="cust-1",
            return_date=date.today(),
            lines=[SalesReturnLine(product_id="p1", qty=4, rate=100)],
            source_invoice_id=invoice.id,
            status=SalesReturnStatus.APPROVED,
        )
    )
    sales = SalesAppService(
        InMemorySalesOrderRepository(),
        InMemoryDeliveryNoteRepository(),
        returns,
        FakeCounterRepository(),
        accounting,
        make_inventory_app_service(),
    )
    metrics = sales.get_commission_agent_metrics("agent-1")
    assert metrics["invoice_count"] == 1
    assert metrics["sales_volume"] == 1000.0
    assert metrics["commission_accrued"] == 50.0
    assert metrics["return_count"] == 1
    assert metrics["return_volume"] == 400.0
    assert metrics["commission_reversed"] == 20.0
    assert metrics["commission_net"] == 30.0
    assert metrics["payable_balance"] == -50.0

    unpaid = sales.list_agent_commission_invoices("agent-1", unpaid_only=True)
    assert len(unpaid) == 1
    assert unpaid[0]["invoice_id"] == invoice.id
    assert unpaid[0]["commission_amount"] == 50.0
    assert unpaid[0]["commission_reversed"] == 20.0
    assert unpaid[0]["unpaid_amount"] == 30.0
    assert unpaid[0]["payment_status"] in ("paid", "partially_paid", "unpaid")
    assert unpaid[0]["payment_status_label"]
    assert "collected" in unpaid[0]
    assert "outstanding" in unpaid[0]
