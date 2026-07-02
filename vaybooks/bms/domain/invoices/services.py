from datetime import date
from typing import List, Set

from vaybooks.bms.domain.expenses.entities import Expense
from vaybooks.bms.domain.invoices.entities import Invoice
from vaybooks.bms.domain.invoices.repository import InvoiceRepository
from vaybooks.bms.domain.orders.entities import CustomizationOrder
from vaybooks.bms.domain.shared.enums import ExpenseSource
from vaybooks.bms.domain.shared.exceptions import ValidationError


class InvoiceDomainService:
    def __init__(self, invoice_repo: InvoiceRepository):
        self._invoice_repo = invoice_repo

    @staticmethod
    def invoiced_bill_ids(invoices: List[Invoice]) -> Set[str]:
        ids: Set[str] = set()
        for invoice in invoices:
            ids.update(invoice.bill_ids)
        return ids

    @staticmethod
    def calculate_mph(
        invoice_amount: float,
        expenses: List[Expense],
    ) -> dict:
        total_expense_selling = sum(e.total_selling_price for e in expenses)
        total_expense_purchase = sum(e.total_purchase_price for e in expenses)
        total_in_house_hours = sum(
            e.linked_time_hours
            for e in expenses
            if e.expense_source == ExpenseSource.IN_HOUSE and e.linked_time_hours > 0
        )
        margin_amount = round(invoice_amount - total_expense_selling, 2)
        margin_per_hour = None
        if total_in_house_hours > 0:
            margin_per_hour = round(margin_amount / total_in_house_hours, 2)

        return {
            "total_expense_purchase_price": total_expense_purchase,
            "total_expense_selling_price": total_expense_selling,
            "total_in_house_hours": total_in_house_hours,
            "margin_amount": margin_amount,
            "margin_per_hour": margin_per_hour,
        }

    def validate_bill_ids(
        self,
        order: CustomizationOrder,
        bill_ids: List[str],
        existing_invoices: List[Invoice],
        allow_already_invoiced: bool = False,
    ) -> None:
        if not bill_ids:
            raise ValidationError("Select at least one bill for the invoice")

        order_bill_ids = {item.item_id for item in order.customization_items}
        for bill_id in bill_ids:
            if bill_id not in order_bill_ids:
                raise ValidationError(f"Item {bill_id} does not belong to this order")
            if not order.item_activities_complete(bill_id):
                raise ValidationError(
                    "Only completed customization items can be invoiced"
                )

        if not allow_already_invoiced:
            already = self.invoiced_bill_ids(existing_invoices)
            overlap = already.intersection(bill_ids)
            if overlap:
                raise ValidationError(
                    "One or more selected bills are already invoiced. "
                    "Enable override to invoice again."
                )

    def generate_invoice(
        self,
        order: CustomizationOrder,
        invoice_number: str,
        invoice_date: date,
        invoice_amount: float,
        bill_ids: List[str],
        expenses: List[Expense],
        existing_invoices: List[Invoice] | None = None,
        allow_already_invoiced: bool = False,
        discount_amount: float = 0.0,
    ) -> Invoice:
        existing = existing_invoices or self._invoice_repo.list_by_order(order.id)
        self.validate_bill_ids(
            order, bill_ids, existing, allow_already_invoiced=allow_already_invoiced
        )
        if invoice_amount <= 0:
            raise ValidationError("Invoice amount is required")
        discount_amount = round(discount_amount or 0.0, 2)
        if discount_amount < 0:
            raise ValidationError("Discount cannot be negative")
        if discount_amount > invoice_amount:
            raise ValidationError("Discount cannot exceed the invoice amount")

        bill_id_set = set(bill_ids)
        scoped_expenses = [
            e for e in expenses if e.bill_id and e.bill_id in bill_id_set
        ]
        # Margin is realized on the net amount (after discount).
        mph_data = self.calculate_mph(invoice_amount - discount_amount, scoped_expenses)
        invoice = Invoice(
            order_id=order.id,
            order_number=order.order_number,
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            invoice_amount=invoice_amount,
            bill_ids=list(bill_ids),
            discount_amount=discount_amount,
            **mph_data,
        )
        return self._invoice_repo.save(invoice)
