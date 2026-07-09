from datetime import date
from typing import List, Optional, Tuple

from vaybooks.bms.domain.expenses.entities import Expense
from vaybooks.bms.domain.expenses.repository import ExpenseRepository
from vaybooks.bms.domain.expenses.services import ExpenseDomainService
from vaybooks.bms.domain.invoices.services import InvoiceDomainService
from vaybooks.bms.domain.orders.repository import OrderRepository
from vaybooks.bms.domain.shared.date_utils import minutes_to_hours, utc_now
from vaybooks.bms.domain.shared.enums import ExpenseSource
from vaybooks.bms.domain.shared.exceptions import ValidationError

_POSITIVE_PRICE_MSG = "Price must be a positive value"


class ExpenseAppService:
    def __init__(
        self,
        expense_repo: ExpenseRepository,
        order_repo: OrderRepository,
        invoice_repo=None,
        delivery_repo=None,
        time_repo=None,
    ):
        self._expense_repo = expense_repo
        self._order_repo = order_repo
        self._invoice_repo = invoice_repo
        self._delivery_repo = delivery_repo
        self._time_repo = time_repo
        self._domain = ExpenseDomainService(expense_repo)
        self._invoice_domain = InvoiceDomainService(invoice_repo)

    def _derive_linked_time(
        self,
        order_id: str,
        activity_id: Optional[str],
        bill_id: Optional[str],
    ) -> Tuple[int, float]:
        """Sum tracked time (minutes/hours) for an activity on a specific bill.

        This is the denominator for MPH; deriving it from the source time
        entries keeps every expense self-consistent regardless of which UI
        path created it."""
        if not (self._time_repo and activity_id and bill_id):
            return 0, 0.0
        entries = self._time_repo.find_by_order_and_activity(order_id, activity_id)
        minutes = sum(e.duration_minutes for e in entries if e.bill_id == bill_id)
        return minutes, minutes_to_hours(minutes)

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
        linked_time_minutes: int = 0,
        linked_time_hours: float = 0.0,
    ) -> Expense:
        if purchase_price <= 0 or selling_price <= 0:
            raise ValidationError(_POSITIVE_PRICE_MSG)

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

        # Populate linked time from tracked entries when the caller didn't
        # supply it explicitly (in-house service expenses drive MPH hours).
        if not linked_time_hours and not linked_time_minutes:
            linked_time_minutes, linked_time_hours = self._derive_linked_time(
                order.id, activity_id, bill_id
            )

        expense = self._domain.create_expense(
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
            linked_time_minutes=linked_time_minutes,
            linked_time_hours=linked_time_hours,
            vendor_or_worker_name=vendor_or_worker_name,
            notes=notes,
        )
        self._recalculate_item_mph(order.id, bill_id)
        return expense

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

    def _recalculate_item_mph(
        self, order_id: Optional[str], bill_id: Optional[str]
    ) -> None:
        """Recompute a delivered+invoiced item's MPH snapshot after an expense
        change. Forces recomputation even if the item was already frozen so the
        figures always reflect current expenses/time."""
        if not order_id or not bill_id:
            return
        if not (self._invoice_repo and self._delivery_repo):
            return
        order = self._order_repo.find_by_id(order_id)
        if not order:
            return
        invoices = self._invoice_repo.list_by_order(order_id)
        deliveries = self._delivery_repo.list_by_order(order_id)
        expenses = self._expense_repo.find_by_order(order_id)
        changed = self._invoice_domain.snapshot_order_items(
            order, invoices, deliveries, expenses, force_bill_ids={bill_id}
        )
        if changed:
            order.updated_at = utc_now()
            self._order_repo.save(order)

    def update_expense(self, expense: Expense) -> Expense:
        expense.calculate_totals()
        # Keep linked time in sync with tracked entries on edit.
        if expense.activity_id and expense.bill_id:
            minutes, hours = self._derive_linked_time(
                expense.order_id, expense.activity_id, expense.bill_id
            )
            if minutes or hours:
                expense.linked_time_minutes = minutes
                expense.linked_time_hours = hours
        saved = self._expense_repo.save(expense)
        self._recalculate_item_mph(expense.order_id, expense.bill_id)
        return saved

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
        expense = self._expense_repo.find_by_id(expense_id)
        self._expense_repo.delete(expense_id)
        if expense:
            self._recalculate_item_mph(expense.order_id, expense.bill_id)
