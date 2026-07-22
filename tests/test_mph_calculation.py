from datetime import date

import pytest

from vaybooks.bms.domain.boutique.expenses.entities import Expense
from vaybooks.bms.domain.boutique.invoices.services import InvoiceDomainService
from vaybooks.bms.domain.boutique.orders.entities import CustomizationItem, CustomizationOrder
from vaybooks.bms.domain.shared.enums import ExpenseSource
from vaybooks.bms.domain.shared.exceptions import ValidationError
from tests.conftest import FakeInvoiceRepository


def _expenses():
    return [
        Expense(
            order_id="o1",
            order_number="CO-0001",
            expense_date=date.today(),
            expense_name="Stitching",
            expense_source=ExpenseSource.IN_HOUSE,
            purchase_price=250,
            selling_price=500,
            quantity=4,
            total_purchase_price=1000,
            total_selling_price=2000,
            linked_time_hours=4,
            bill_id="b1",
        ),
    ]


def test_mph_calculation():
    result = InvoiceDomainService.calculate_mph(8500, _expenses())
    assert result["margin_amount"] == 6500  # 8500 - 2000
    assert result["margin_per_hour"] == 1625  # 6500 / 4


def test_mph_zero_hours_returns_null():
    expenses = [
        Expense(
            order_id="o1",
            order_number="CO-0001",
            expense_date=date.today(),
            expense_name="Material",
            expense_source=ExpenseSource.MATERIAL,
            purchase_price=100,
            selling_price=200,
            total_purchase_price=100,
            total_selling_price=200,
        ),
    ]
    result = InvoiceDomainService.calculate_mph(5000, expenses)
    assert result["margin_per_hour"] is None


def test_invoice_requires_bill_ids():
    repo = FakeInvoiceRepository()
    service = InvoiceDomainService(repo)
    order = CustomizationOrder(
        order_number="CO-0001",
        customer_id="c1",
        customer_name="Test",
        phone_number="123",
        order_date=date.today(),
        expected_delivery_date=date.today(),
        customization_items=[
            CustomizationItem(bill_number="ZB001", item_id="b1", description="Saree")
        ],
    )
    with pytest.raises(ValidationError):
        service.generate_invoice(
            order, "INV-0001", date.today(), 5000, [], _expenses()
        )
