from datetime import date
from typing import List, Optional

from vaybooks.bms.domain.expenses.entities import Expense
from vaybooks.bms.domain.expenses.repository import ExpenseRepository
from vaybooks.bms.domain.expenses.services import ExpenseDomainService
from vaybooks.bms.domain.orders.repository import OrderRepository
from vaybooks.bms.domain.shared.enums import ExpenseSource


class ExpenseAppService:
    def __init__(
        self,
        expense_repo: ExpenseRepository,
        order_repo: OrderRepository,
    ):
        self._expense_repo = expense_repo
        self._order_repo = order_repo
        self._domain = ExpenseDomainService(expense_repo)

    def add_expense(
        self,
        order_id: str,
        expense_date: date,
        expense_name: str,
        expense_source: str,
        purchase_price: float,
        selling_price: float,
        quantity: float = 1.0,
        bill_id: Optional[str] = None,
        activity_id: Optional[str] = None,
        vendor_or_worker_name: str = "",
        notes: str = "",
    ) -> Expense:
        order = self._order_repo.find_by_id(order_id)
        bill_number = None
        activity_name = None
        if bill_id:
            bill = order.get_bill_by_id(bill_id)
            bill_number = bill.bill_number if bill else None
        if activity_id:
            for oa in order.order_activities:
                if oa.activity_id == activity_id:
                    activity_name = oa.activity_name
                    break

        return self._domain.create_expense(
            order_id=order.id,
            order_number=order.order_number,
            expense_date=expense_date,
            expense_name=expense_name,
            expense_source=ExpenseSource(expense_source),
            purchase_price=purchase_price,
            selling_price=selling_price,
            quantity=quantity,
            bill_id=bill_id,
            bill_number=bill_number,
            activity_id=activity_id,
            activity_name=activity_name,
            vendor_or_worker_name=vendor_or_worker_name,
            notes=notes,
        )

    def get_expenses_by_order(self, order_id: str) -> List[Expense]:
        return self._expense_repo.find_by_order(order_id)

    def get_expenses_by_bill(self, bill_id: str) -> List[Expense]:
        return self._expense_repo.find_by_bill(bill_id)

    def get_expense(self, expense_id: str) -> Optional[Expense]:
        return self._expense_repo.find_by_id(expense_id)

    def get_order_totals(self, order_id: str) -> dict:
        expenses = self._expense_repo.find_by_order(order_id)
        return self._domain.get_order_totals(expenses)

    def list_all(self) -> List[Expense]:
        return self._expense_repo.list_all()

    def update_expense(self, expense: Expense) -> Expense:
        expense.calculate_totals()
        return self._expense_repo.save(expense)

    def update_expense_details(
        self,
        expense_id: str,
        expense_date: date,
        expense_name: str,
        expense_source: str,
        purchase_price: float,
        selling_price: float,
        quantity: float = 1.0,
        vendor_or_worker_name: str = "",
        notes: str = "",
        activity_id: Optional[str] = None,
        activity_name: Optional[str] = None,
    ) -> Expense:
        expense = self._expense_repo.find_by_id(expense_id)
        if not expense:
            raise ValueError("Expense not found")
        expense.expense_date = expense_date
        expense.expense_name = expense_name
        expense.expense_source = ExpenseSource(expense_source)
        expense.purchase_price = purchase_price
        expense.selling_price = selling_price
        expense.quantity = quantity
        expense.vendor_or_worker_name = vendor_or_worker_name
        expense.notes = notes
        if activity_id is not None:
            expense.activity_id = activity_id
            expense.activity_name = activity_name
        return self.update_expense(expense)

    def delete_expense(self, expense_id: str) -> None:
        self._expense_repo.delete(expense_id)
