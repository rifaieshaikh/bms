from datetime import date
from typing import Dict, List, Optional, Set

from vaybooks.bms.domain.boutique.deliveries.entities import Delivery
from vaybooks.bms.domain.boutique.expenses.entities import Expense
from vaybooks.bms.domain.boutique.invoices.entities import (
    DEFAULT_CUSTOMIZATION_GST_RATE,
    DEFAULT_CUSTOMIZATION_SAC,
    INVOICE_KIND_CANCELLATION,
    INVOICE_KIND_STANDARD,
    INVOICE_SOURCE_GENERATED,
    INVOICE_SOURCE_RECORDED,
    Invoice,
)
from vaybooks.bms.domain.boutique.invoices.repository import InvoiceRepository
from vaybooks.bms.domain.boutique.orders.bill_status import delivered_bill_ids
from vaybooks.bms.domain.boutique.orders.entities import CustomizationItem, CustomizationOrder
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import ExpenseSource, OrderStatus
from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.domain.shared.india import compute_sales_gst
from vaybooks.bms.domain.sales.sales_line_resolver import effective_sales_gst_rate


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
        revenue_amount: float,
        expenses: List[Expense],
    ) -> dict:
        """Compute invoice-level margin and MPH from net revenue after discount."""
        total_expense_selling = sum(e.total_selling_price for e in expenses)
        total_expense_purchase = sum(e.total_purchase_price for e in expenses)
        total_in_house_hours = sum(
            e.linked_time_hours
            for e in expenses
            if e.expense_source == ExpenseSource.IN_HOUSE and e.linked_time_hours > 0
        )
        margin_amount = round(revenue_amount - total_expense_selling, 2)
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
        item_revenue: float,
        item_expenses: List[Expense],
    ) -> dict:
        """MPH for a single customization item (bill).

        ``item_revenue`` is cumulative net revenue (gross minus discounts) across
        every invoice for the item.
        """
        selling = sum(e.total_selling_price for e in item_expenses)
        purchase = sum(e.total_purchase_price for e in item_expenses)
        hours = sum(
            e.linked_time_hours
            for e in item_expenses
            if e.expense_source == ExpenseSource.IN_HOUSE and e.linked_time_hours > 0
        )
        margin = round(item_revenue - selling, 2)
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
    def _invoice_item_gross(cls, invoice: Invoice, bill_id: str) -> float:
        """Gross amount a single invoice attributes to a bill."""
        return float(cls._item_gross_map(invoice).get(bill_id, 0.0))

    @classmethod
    def _invoice_item_discount(cls, invoice: Invoice, bill_id: str) -> float:
        """Discount a single invoice attributes to a bill. Uses per-item
        discounts when present, otherwise allocates the order discount
        proportionally to the item's gross price (legacy invoices)."""
        if invoice.item_discounts:
            return float(invoice.item_discounts.get(bill_id, 0.0))
        discount = float(invoice.discount_amount or 0.0)
        if discount <= 0:
            return 0.0
        gross_map = cls._item_gross_map(invoice)
        total_gross = sum(gross_map.values())
        if total_gross > 0:
            return round(discount * gross_map.get(bill_id, 0.0) / total_gross, 2)
        return round(discount / (len(invoice.bill_ids) or 1), 2)

    @classmethod
    def item_gross_revenue(
        cls,
        bill_id: str,
        invoices: List[Invoice],
        exclude_invoice_id: Optional[str] = None,
    ) -> float:
        """Cumulative gross revenue billed to an item across every invoice.

        Re-invoicing an item is additive: invoice #1 (1000) + invoice #2 (500)
        means the item's lifetime gross is 1500.
        """
        total = 0.0
        for inv in invoices:
            if exclude_invoice_id and inv.id == exclude_invoice_id:
                continue
            if bill_id in inv.bill_ids:
                total += cls._invoice_item_gross(inv, bill_id)
        return round(total, 2)

    @classmethod
    def item_net_revenue(
        cls,
        bill_id: str,
        invoices: List[Invoice],
        exclude_invoice_id: Optional[str] = None,
    ) -> Optional[float]:
        """Cumulative net revenue for a bill (gross minus discount) across all
        invoices. Returns None if the bill has never been invoiced."""
        relevant = [
            inv
            for inv in invoices
            if bill_id in inv.bill_ids and inv.id != exclude_invoice_id
        ]
        if not relevant:
            return None
        gross = sum(cls._invoice_item_gross(inv, bill_id) for inv in relevant)
        discount = sum(cls._invoice_item_discount(inv, bill_id) for inv in relevant)
        return round(gross - discount, 2)

    @staticmethod
    def allocate_discount_proportionally(
        item_amounts: Dict[str, float], order_discount: float
    ) -> Dict[str, float]:
        """Split an order-level discount across items in proportion to gross.

        The last item absorbs the rounding remainder so the parts always sum
        back to ``order_discount``.
        """
        bills = list(item_amounts.keys())
        order_discount = round(order_discount or 0.0, 2)
        total = sum(item_amounts.values())
        if not bills or total <= 0 or order_discount <= 0:
            return {b: 0.0 for b in bills}
        result: Dict[str, float] = {}
        allocated = 0.0
        for idx, bill_id in enumerate(bills):
            if idx == len(bills) - 1:
                share = round(order_discount - allocated, 2)
            else:
                share = round(order_discount * item_amounts[bill_id] / total, 2)
                allocated = round(allocated + share, 2)
            result[bill_id] = max(0.0, min(share, item_amounts[bill_id]))
        return result

    @classmethod
    def redistribute_discount_delta(
        cls,
        item_amounts: Dict[str, float],
        current_item_discounts: Dict[str, float],
        new_order_discount: float,
    ) -> Dict[str, float]:
        """Apply the change in an order-level discount to existing item-level
        discounts, distributing only the *difference* proportionally to gross.
        """
        bills = list(item_amounts.keys())
        if not bills:
            return {}
        current_total = round(
            sum(current_item_discounts.get(b, 0.0) for b in bills), 2
        )
        delta = round((new_order_discount or 0.0) - current_total, 2)
        total = sum(item_amounts.values())
        if total <= 0:
            return {b: current_item_discounts.get(b, 0.0) for b in bills}
        result: Dict[str, float] = {}
        allocated = 0.0
        for idx, bill_id in enumerate(bills):
            base = current_item_discounts.get(bill_id, 0.0)
            if idx == len(bills) - 1:
                add = round(delta - allocated, 2)
            else:
                add = round(delta * item_amounts[bill_id] / total, 2)
                allocated = round(allocated + add, 2)
            result[bill_id] = max(0.0, min(round(base + add, 2), item_amounts[bill_id]))
        return result

    @classmethod
    def snapshot_order_items(
        cls,
        order: CustomizationOrder,
        invoices: List[Invoice],
        deliveries: List[Delivery],
        expenses: List[Expense],
        force_bill_ids: Optional[Set[str]] = None,
    ) -> bool:
        """Freeze per-item MPH for every item that is both delivered and
        invoiced. Returns True if any item snapshot changed.

        Items whose id is in ``force_bill_ids`` are recomputed even if already
        frozen — used when an expense changes and the item's MPH must reflect
        the new figures.
        """
        delivered = delivered_bill_ids(deliveries)
        force = force_bill_ids or set()
        expenses_by_bill: Dict[str, List[Expense]] = {}
        for e in expenses:
            if e.bill_id:
                expenses_by_bill.setdefault(e.bill_id, []).append(e)

        changed = False
        for item in order.customization_items:
            if item.mph_snapshot_at is not None and item.item_id not in force:
                continue  # frozen — never recalculate from live time/expense data
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

    @staticmethod
    def compute_total_amount(
        order: CustomizationOrder,
        bill_ids: List[str],
        item_amounts: Optional[Dict[str, float]] = None,
        invoice_amount: float = 0.0,
    ) -> float:
        """Sum per-item sale prices for the selected bills."""
        bill_id_set = set(bill_ids)
        if item_amounts:
            return round(
                sum(float(item_amounts.get(b, 0.0)) for b in bill_ids if b in bill_id_set),
                2,
            )

        total = 0.0
        for bill_id in bill_ids:
            item = order.get_item_by_id(bill_id)
            if item is not None:
                total += float(item.sale_price or 0.0)
        if total > 0:
            return round(total, 2)
        return round(float(invoice_amount), 2)

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
        if order.order_status == OrderStatus.CANCELLED:
            cancel_item = order.get_cancellation_charge_item()
            if not cancel_item:
                raise ValidationError(
                    "Cancellation charge item is missing on this cancelled order"
                )
            if set(bill_ids) != {cancel_item.item_id}:
                raise ValidationError(
                    "Cancelled orders can only invoice the cancellation charge"
                )
        else:
            for bill_id in bill_ids:
                if bill_id not in order_bill_ids:
                    raise ValidationError(f"Item {bill_id} does not belong to this order")
                item = order.get_item_by_id(bill_id)
                if item and item.is_cancellation_charge:
                    raise ValidationError(
                        "Cancellation charge can only be invoiced on cancelled orders"
                    )
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

    def build_invoice(
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
        item_discounts: Optional[Dict[str, float]] = None,
        invoice_source: str = INVOICE_SOURCE_RECORDED,
        gst_rate: float = 0.0,
        hsn_sac: str = "",
        place_of_supply_state: str = "",
        supply_type: str = "",
        business_registered: bool = False,
        business_state_code: str = "",
        business=None,
    ) -> Invoice:
        existing = existing_invoices or self._invoice_repo.list_by_order(order.id)
        self.validate_bill_ids(
            order, bill_ids, existing, allow_already_invoiced=allow_already_invoiced
        )
        if invoice_amount <= 0:
            raise ValidationError("Invoice amount is required")

        bill_id_set = set(bill_ids)
        item_amounts = {
            b: round(float(v), 2)
            for b, v in (item_amounts or {}).items()
            if b in bill_id_set
        }
        # Per-item discounts are authoritative; the order discount is their sum.
        # A bare order-level discount is split proportionally to item gross.
        if item_discounts:
            item_discounts = {
                b: round(float(v), 2)
                for b, v in item_discounts.items()
                if b in bill_id_set
            }
        else:
            item_discounts = self.allocate_discount_proportionally(
                item_amounts, round(discount_amount or 0.0, 2)
            )
        discount_amount = round(sum(item_discounts.values()), 2)
        if discount_amount < 0:
            raise ValidationError("Discount cannot be negative")
        if discount_amount > invoice_amount:
            raise ValidationError("Discount cannot exceed the invoice amount")

        scoped_expenses = [
            e for e in expenses if e.bill_id and e.bill_id in bill_id_set
        ]
        net_revenue = round(invoice_amount - discount_amount, 2)
        mph_data = self.calculate_mph(net_revenue, scoped_expenses)
        total_amount = self.compute_total_amount(
            order,
            bill_ids,
            item_amounts=item_amounts,
            invoice_amount=invoice_amount,
        )

        taxable_amount = net_revenue
        cgst_amount = sgst_amount = igst_amount = utgst_amount = 0.0
        effective_rate = 0.0
        cancel_item = order.get_cancellation_charge_item()
        invoice_kind = (
            INVOICE_KIND_CANCELLATION
            if cancel_item and set(bill_ids) == {cancel_item.item_id}
            else INVOICE_KIND_STANDARD
        )
        if invoice_source == INVOICE_SOURCE_GENERATED and business_registered:
            base_rate = float(gst_rate or DEFAULT_CUSTOMIZATION_GST_RATE)
            effective_rate = effective_sales_gst_rate(business, base_rate)
            gst = compute_sales_gst(
                taxable_amount,
                effective_rate,
                business_registered=True,
                business_state_code=business_state_code,
                customer_state_code=place_of_supply_state,
            )
            taxable_amount = gst.taxable_amount
            cgst_amount = gst.cgst_amount
            sgst_amount = gst.sgst_amount
            igst_amount = gst.igst_amount
            utgst_amount = gst.utgst_amount

        return Invoice(
            order_id=order.id,
            order_number=order.order_number,
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            invoice_amount=invoice_amount,
            total_amount=total_amount,
            bill_ids=list(bill_ids),
            item_amounts=item_amounts,
            item_discounts=item_discounts,
            discount_amount=discount_amount,
            invoice_source=invoice_source,
            invoice_kind=invoice_kind,
            gst_rate=effective_rate if invoice_source == INVOICE_SOURCE_GENERATED else 0.0,
            hsn_sac=(hsn_sac or DEFAULT_CUSTOMIZATION_SAC).strip(),
            place_of_supply_state=(place_of_supply_state or "").strip(),
            supply_type=(supply_type or "").strip(),
            taxable_amount=taxable_amount,
            cgst_amount=cgst_amount,
            sgst_amount=sgst_amount,
            igst_amount=igst_amount,
            utgst_amount=utgst_amount,
            **mph_data,
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
        item_discounts: Optional[Dict[str, float]] = None,
    ) -> Invoice:
        invoice = self.build_invoice(
            order=order,
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            invoice_amount=invoice_amount,
            bill_ids=bill_ids,
            expenses=expenses,
            existing_invoices=existing_invoices,
            allow_already_invoiced=allow_already_invoiced,
            discount_amount=discount_amount,
            item_amounts=item_amounts,
            item_discounts=item_discounts,
        )
        return self._invoice_repo.save(invoice)
