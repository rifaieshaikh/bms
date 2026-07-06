from datetime import date
from typing import Dict, List, Optional, Set

from vaybooks.bms.domain.deliveries.entities import Delivery
from vaybooks.bms.domain.expenses.entities import Expense
from vaybooks.bms.domain.invoices.entities import Invoice
from vaybooks.bms.domain.invoices.repository import InvoiceRepository
from vaybooks.bms.domain.orders.bill_status import delivered_bill_ids
from vaybooks.bms.domain.orders.entities import CustomizationItem, CustomizationOrder
from vaybooks.bms.domain.shared.date_utils import utc_now
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

    @staticmethod
    def calculate_item_mph(
        item_net_revenue: float,
        item_expenses: List[Expense],
    ) -> dict:
        """MPH for a single customization item (bill)."""
        selling = sum(e.total_selling_price for e in item_expenses)
        purchase = sum(e.total_purchase_price for e in item_expenses)
        hours = sum(
            e.linked_time_hours
            for e in item_expenses
            if e.expense_source == ExpenseSource.IN_HOUSE and e.linked_time_hours > 0
        )
        margin = round(item_net_revenue - selling, 2)
        mph = round(margin / hours, 2) if hours > 0 else None
        return {
            "expense_selling_total": round(selling, 2),
            "expense_purchase_total": round(purchase, 2),
            "in_house_hours": hours,
            "margin_amount": margin,
            "margin_per_hour": mph,
        }

    @staticmethod
    def _item_gross_map(invoice: Invoice) -> Dict[str, float]:
        """bill_id -> gross price. Falls back to an equal split for older
        invoices saved before per-item pricing existed."""
        if invoice.item_amounts:
            return {b: float(invoice.item_amounts.get(b, 0.0)) for b in invoice.bill_ids}
        count = len(invoice.bill_ids) or 1
        each = round(float(invoice.invoice_amount) / count, 2)
        return {b: each for b in invoice.bill_ids}

    @classmethod
    def item_net_revenue(
        cls, bill_id: str, invoices: List[Invoice]
    ) -> Optional[float]:
        """Net revenue attributed to a bill from its most recent invoice, with
        the invoice discount allocated proportionally to the item's price."""
        latest: Optional[Invoice] = None
        for inv in invoices:
            if bill_id in inv.bill_ids:
                if latest is None or (inv.updated_at or inv.created_at) >= (
                    latest.updated_at or latest.created_at
                ):
                    latest = inv
        if latest is None:
            return None
        gross_map = cls._item_gross_map(latest)
        gross = gross_map.get(bill_id, 0.0)
        total_gross = sum(gross_map.values())
        discount = float(latest.discount_amount or 0.0)
        if total_gross > 0:
            share = gross / total_gross
        else:
            share = 1.0 / (len(latest.bill_ids) or 1)
        return round(gross - discount * share, 2)

    @classmethod
    def snapshot_order_items(
        cls,
        order: CustomizationOrder,
        invoices: List[Invoice],
        deliveries: List[Delivery],
        expenses: List[Expense],
    ) -> bool:
        """Freeze per-item MPH for every item that is both delivered and
        invoiced. Returns True if any item snapshot changed."""
        delivered = delivered_bill_ids(deliveries)
        expenses_by_bill: Dict[str, List[Expense]] = {}
        for e in expenses:
            if e.bill_id:
                expenses_by_bill.setdefault(e.bill_id, []).append(e)

        changed = False
        for item in order.customization_items:
            if item.item_id not in delivered:
                continue
            net = cls.item_net_revenue(item.item_id, invoices)
            if net is None:
                continue  # delivered but not invoiced yet — backfilled later
            data = cls.calculate_item_mph(net, expenses_by_bill.get(item.item_id, []))
            item.sell_amount = net
            item.expense_selling_total = data["expense_selling_total"]
            item.expense_purchase_total = data["expense_purchase_total"]
            item.in_house_hours = data["in_house_hours"]
            item.margin_amount = data["margin_amount"]
            item.margin_per_hour = data["margin_per_hour"]
            item.mph_snapshot_at = utc_now()
            item.updated_at = utc_now()
            changed = True
        return changed

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
        item_amounts: Optional[Dict[str, float]] = None,
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
        item_amounts = {
            b: round(float(v), 2)
            for b, v in (item_amounts or {}).items()
            if b in bill_id_set
        }
        invoice = Invoice(
            order_id=order.id,
            order_number=order.order_number,
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            invoice_amount=invoice_amount,
            bill_ids=list(bill_ids),
            item_amounts=item_amounts,
            discount_amount=discount_amount,
            **mph_data,
        )
        return self._invoice_repo.save(invoice)
