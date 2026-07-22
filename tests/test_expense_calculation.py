from datetime import date

import pytest

from vaybooks.bms.domain.boutique.expenses.services import ExpenseDomainService
from vaybooks.bms.domain.shared.enums import ExpenseSource
from vaybooks.bms.domain.shared.exceptions import ValidationError
from tests.conftest import FakeExpenseRepository


def test_expense_calculation_from_time():
    total_purchase, total_selling = ExpenseDomainService.calculate_from_time(
        total_hours=4.0,
        default_purchase_price=250,
        default_selling_price=500,
    )
    assert total_purchase == 1000.0
    assert total_selling == 2000.0


def test_expense_negative_price_rejected():
    repo = FakeExpenseRepository()
    service = ExpenseDomainService(repo)

    with pytest.raises(ValidationError):
        service.create_expense(
            order_id="o1",
            order_number="CO-0001",
            expense_date=date.today(),
            expense_name="Test",
            expense_source=ExpenseSource.IN_HOUSE,
            purchase_price=-1,
            selling_price=100,
        )
