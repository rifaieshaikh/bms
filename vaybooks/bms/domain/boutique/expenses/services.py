from datetime import date
from typing import Optional

from vaybooks.bms.domain.boutique.activities.services import ActivityCompletionPreview
from vaybooks.bms.domain.boutique.expenses.entities import Expense
from vaybooks.bms.domain.boutique.expenses.repository import ExpenseRepository
from vaybooks.bms.domain.shared.enums import ExpenseSource
from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.domain.shared.money import validate_non_negative


class ExpenseDomainService:
    def __init__(self, repo: ExpenseRepository):
        self._repo = repo

    def create_expense(
        self,
        order_id: str,
        order_number: str,
        expense_date: date,
        expense_name: str,
        expense_source: ExpenseSource,
        purchase_price: float,
        selling_price: float,
        quantity: float = 1.0,
        bill_id: Optional[str] = None,
        bill_number: Optional[str] = None,
        activity_id: Optional[str] = None,
        activity_name: Optional[str] = None,
        linked_time_minutes: int = 0,
        linked_time_hours: float = 0.0,
        vendor_or_worker_name: str = "",
        account_id: Optional[str] = None,
        notes: str = "",
    ) -> Expense:
        validate_non_negative(purchase_price, "Purchase price")
        validate_non_negative(selling_price, "Selling price")
        validate_non_negative(quantity, "Quantity")

        expense = Expense(
            order_id=order_id,
            order_number=order_number,
            expense_date=expense_date,
            expense_name=expense_name,
            expense_source=expense_source,
            purchase_price=purchase_price,
            selling_price=selling_price,
            quantity=quantity,
            bill_id=bill_id,
            bill_number=bill_number,
            activity_id=activity_id,
            activity_name=activity_name,
            linked_time_minutes=linked_time_minutes,
            linked_time_hours=linked_time_hours,
            vendor_or_worker_name=vendor_or_worker_name,
            account_id=account_id,
            notes=notes,
        )
        expense.calculate_totals()
        return self._repo.save(expense)

    def create_from_activity_completion(
        self,
        preview: ActivityCompletionPreview,
        expense_date: date,
        purchase_price: float,
        selling_price: float,
        vendor_or_worker_name: str = "",
        notes: str = "",
    ) -> Expense:
        validate_non_negative(purchase_price, "Purchase price")
        validate_non_negative(selling_price, "Selling price")

        quantity = preview.total_hours if preview.total_hours > 0 else 1.0
        expense_name = f"{preview.activity_name} - {preview.expense_source}"

        return self.create_expense(
            order_id=preview.order_id,
            order_number=preview.order_number,
            expense_date=expense_date,
            expense_name=expense_name,
            expense_source=ExpenseSource(preview.expense_source)
            if preview.expense_source in [e.value for e in ExpenseSource]
            else ExpenseSource.IN_HOUSE,
            purchase_price=purchase_price,
            selling_price=selling_price,
            quantity=quantity,
            bill_id=preview.bill_id,
            bill_number=preview.bill_number,
            activity_id=preview.activity_id,
            activity_name=preview.activity_name,
            linked_time_minutes=preview.total_duration_minutes,
            linked_time_hours=preview.total_hours,
            vendor_or_worker_name=vendor_or_worker_name,
            notes=notes,
        )

    @staticmethod
    def calculate_from_time(
        total_hours: float,
        default_purchase_price: float,
        default_selling_price: float,
    ) -> tuple:
        total_purchase = round(total_hours * default_purchase_price, 2)
        total_selling = round(total_hours * default_selling_price, 2)
        return total_purchase, total_selling

    def get_order_totals(self, expenses: list) -> dict:
        return {
            "total_purchase": sum(e.total_purchase_price for e in expenses),
            "total_selling": sum(e.total_selling_price for e in expenses),
        }
