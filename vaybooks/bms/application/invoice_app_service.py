from datetime import date
from typing import Dict, List, Optional

from vaybooks.bms.domain.accounting.repository import CounterRepository
from vaybooks.bms.domain.expenses.repository import ExpenseRepository
from vaybooks.bms.domain.invoices.entities import Invoice
from vaybooks.bms.domain.invoices.repository import InvoiceRepository
from vaybooks.bms.domain.invoices.services import InvoiceDomainService
from vaybooks.bms.domain.orders.repository import OrderRepository
from vaybooks.bms.domain.orders.services import OrderDomainService
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import VoucherType
from vaybooks.bms.domain.shared.exceptions import ValidationError


class InvoiceAppService:
    def __init__(
        self,
        invoice_repo: InvoiceRepository,
        order_repo: OrderRepository,
        expense_repo: ExpenseRepository,
        counter_repo: CounterRepository,
        delivery_repo=None,
        accounting_service=None,
    ):
        self._invoice_repo = invoice_repo
        self._order_repo = order_repo
        self._expense_repo = expense_repo
        self._counter_repo = counter_repo
        self._delivery_repo = delivery_repo
        self._accounting = accounting_service
        self._domain = InvoiceDomainService(invoice_repo)
        self._order_domain = OrderDomainService(order_repo, None)

    def _snapshot_item_mph(self, order, invoices: List[Invoice]) -> None:
        """Freeze per-item MPH for items that are both invoiced and delivered.
        Backfills items delivered before their invoice was created."""
        deliveries = (
            self._delivery_repo.list_by_order(order.id) if self._delivery_repo else []
        )
        if not deliveries:
            return
        expenses = self._expense_repo.find_by_order(order.id)
        self._domain.snapshot_order_items(order, invoices, deliveries, expenses)

    def _resolve_customization_account_id(self) -> str:
        account = self._accounting.get_customization_account()
        if account:
            return account.id
        raise ValueError(
            'No "Customization" revenue account found. '
            "Restart the app to seed defaults or create one in Accounts."
        )

    def _resolve_discount_account_id(self) -> str:
        account = self._accounting.get_discount_account()
        if not account:
            raise ValueError(
                'No "Discount Allowed" account found. Create one in the Accounts page.'
            )
        return account.id

    def _sync_sales_posting(
        self,
        order,
        invoice: Invoice,
        post_entry: bool,
    ) -> None:
        """Create, update, or void the Dr Customer / Dr Discount / Cr Customization voucher."""
        if self._accounting is None:
            return
        existing = self._accounting.find_sales_voucher_by_invoice(invoice.id)
        if not post_entry:
            if existing:
                self._accounting.void_voucher(existing.id)
            return

        customer_account = self._accounting.get_customer_account(order.customer_id)
        if not customer_account:
            raise ValueError("No customer account found for this order")
        income_id = self._resolve_customization_account_id()
        discount = round(invoice.discount_amount or 0.0, 2)
        discount_account_id = (
            self._resolve_discount_account_id() if discount > 0 else None
        )
        description = f"Invoice {invoice.invoice_number} - {order.order_number}"
        if existing:
            self._accounting.update_sales_invoice(
                existing.id,
                customer_account.id,
                income_id,
                invoice.invoice_amount,
                description,
                invoice.invoice_date,
                discount_amount=discount,
                discount_account_id=discount_account_id,
                voucher_type=VoucherType.CUSTOMIZATION_INVOICE,
            )
        else:
            self._accounting.create_sales_invoice(
                customer_account.id,
                income_id,
                invoice.invoice_amount,
                description,
                invoice.invoice_date,
                reference_order_id=order.id,
                reference_invoice_id=invoice.id,
                discount_amount=discount,
                discount_account_id=discount_account_id,
                voucher_type=VoucherType.CUSTOMIZATION_INVOICE,
            )

    def generate_invoice(
        self,
        order_id: str,
        bill_ids: List[str],
        invoice_amount: float,
        invoice_date: Optional[date] = None,
        allow_already_invoiced: bool = False,
        item_amounts: Optional[Dict[str, float]] = None,
    ) -> Invoice:
        order = self._order_repo.find_by_id(order_id)
        expenses = self._expense_repo.find_by_order(order_id)
        existing = self._invoice_repo.list_by_order(order_id)

        self._domain.validate_bill_ids(
            order,
            bill_ids,
            existing,
            allow_already_invoiced=allow_already_invoiced,
        )
        if invoice_amount <= 0:
            raise ValidationError("Invoice amount is required")

        invoice_number = self._counter_repo.next("invoice_number")
        inv_date = invoice_date or date.today()

        invoice = self._domain.build_invoice(
            order=order,
            invoice_number=invoice_number,
            invoice_date=inv_date,
            invoice_amount=invoice_amount,
            bill_ids=bill_ids,
            expenses=expenses,
            existing_invoices=existing,
            allow_already_invoiced=allow_already_invoiced,
            item_amounts=item_amounts,
        )
        saved = self._invoice_repo.save(invoice)

        invoices = existing + [saved]
        deliveries = (
            self._delivery_repo.list_by_order(order_id) if self._delivery_repo else []
        )
        self._order_domain.recalculate_status(order, invoices, deliveries)
        self._snapshot_item_mph(order, invoices)
        order.updated_at = utc_now()
        self._order_repo.save(order)
        return saved

    def record_invoice(
        self,
        order_id: str,
        invoice_number: str,
        bill_ids: List[str],
        invoice_amount: float,
        invoice_date: Optional[date] = None,
        allow_already_invoiced: bool = False,
        post_entry: bool = False,
        discount_amount: float = 0.0,
        item_amounts: Optional[Dict[str, float]] = None,
        item_discounts: Optional[Dict[str, float]] = None,
    ) -> Invoice:
        if not invoice_number or not invoice_number.strip():
            raise ValueError("Invoice number is required")
        order = self._order_repo.find_by_id(order_id)
        expenses = self._expense_repo.find_by_order(order_id)
        existing = self._invoice_repo.list_by_order(order_id)

        self._domain.validate_bill_ids(
            order,
            bill_ids,
            existing,
            allow_already_invoiced=allow_already_invoiced,
        )
        if invoice_amount <= 0:
            raise ValidationError("Invoice amount is required")

        inv_date = invoice_date or date.today()

        invoice = self._domain.build_invoice(
            order=order,
            invoice_number=invoice_number.strip(),
            invoice_date=inv_date,
            invoice_amount=invoice_amount,
            bill_ids=bill_ids,
            expenses=expenses,
            existing_invoices=existing,
            allow_already_invoiced=allow_already_invoiced,
            discount_amount=discount_amount,
            item_amounts=item_amounts,
            item_discounts=item_discounts,
        )
        saved = self._invoice_repo.save(invoice)

        self._sync_sales_posting(order, saved, post_entry)

        invoices = existing + [saved]
        deliveries = (
            self._delivery_repo.list_by_order(order_id) if self._delivery_repo else []
        )
        self._order_domain.recalculate_status(order, invoices, deliveries)
        self._snapshot_item_mph(order, invoices)
        order.updated_at = utc_now()
        self._order_repo.save(order)
        return saved

    def update_invoice(
        self,
        invoice_id: str,
        invoice_number: str,
        bill_ids: List[str],
        invoice_amount: float,
        invoice_date: Optional[date] = None,
        allow_already_invoiced: bool = True,
        post_entry: bool = False,
        discount_amount: float = 0.0,
        item_amounts: Optional[Dict[str, float]] = None,
        item_discounts: Optional[Dict[str, float]] = None,
    ) -> Invoice:
        invoice = self._invoice_repo.find_by_id(invoice_id)
        if not invoice:
            raise ValueError("Invoice not found")
        if not invoice_number or not invoice_number.strip():
            raise ValueError("Invoice number is required")
        if invoice_amount <= 0:
            raise ValueError("Invoice amount is required")

        order = self._order_repo.find_by_id(invoice.order_id)
        expenses = self._expense_repo.find_by_order(invoice.order_id)
        others = [
            inv
            for inv in self._invoice_repo.list_by_order(invoice.order_id)
            if inv.id != invoice.id
        ]
        self._domain.validate_bill_ids(
            order, bill_ids, others, allow_already_invoiced=allow_already_invoiced
        )

        bill_id_set = set(bill_ids)
        item_amounts = {
            b: round(float(v), 2)
            for b, v in (item_amounts or {}).items()
            if b in bill_id_set
        }
        # Per-item discounts are authoritative; a bare order discount is split
        # proportionally to item gross amounts.
        if item_discounts:
            item_discounts = {
                b: round(float(v), 2)
                for b, v in item_discounts.items()
                if b in bill_id_set
            }
        else:
            item_discounts = self._domain.allocate_discount_proportionally(
                item_amounts, round(discount_amount or 0.0, 2)
            )
        discount_amount = round(sum(item_discounts.values()), 2)
        if discount_amount < 0:
            raise ValueError("Discount cannot be negative")
        if discount_amount > invoice_amount:
            raise ValueError("Discount cannot exceed the invoice amount")

        scoped = [e for e in expenses if e.bill_id and e.bill_id in bill_id_set]
        # MPH excludes discount: margin is measured on the gross amount.
        mph = self._domain.calculate_mph(invoice_amount, scoped)

        invoice.invoice_number = invoice_number.strip()
        invoice.bill_ids = list(bill_ids)
        invoice.item_amounts = item_amounts
        invoice.item_discounts = item_discounts
        invoice.invoice_amount = invoice_amount
        invoice.discount_amount = discount_amount
        invoice.invoice_date = invoice_date or invoice.invoice_date
        invoice.total_expense_purchase_price = mph["total_expense_purchase_price"]
        invoice.total_expense_selling_price = mph["total_expense_selling_price"]
        invoice.total_in_house_hours = mph["total_in_house_hours"]
        invoice.margin_amount = mph["margin_amount"]
        invoice.margin_per_hour = mph["margin_per_hour"]
        invoice.updated_at = utc_now()
        saved = self._invoice_repo.save(invoice)

        self._sync_sales_posting(order, saved, post_entry)

        deliveries = (
            self._delivery_repo.list_by_order(invoice.order_id)
            if self._delivery_repo
            else []
        )
        invoices = others + [saved]
        self._order_domain.recalculate_status(order, invoices, deliveries)
        self._snapshot_item_mph(order, invoices)
        order.updated_at = utc_now()
        self._order_repo.save(order)
        return saved

    def get_invoice(self, invoice_id: str) -> Optional[Invoice]:
        return self._invoice_repo.find_by_id(invoice_id)

    def list_invoices_by_order(self, order_id: str) -> List[Invoice]:
        return self._invoice_repo.list_by_order(order_id)

    def get_invoice_by_order(self, order_id: str) -> Optional[Invoice]:
        invoices = self._invoice_repo.list_by_order(order_id)
        return invoices[0] if invoices else None

    def preview_mph(
        self,
        order_id: str,
        bill_ids: List[str],
        invoice_amount: float,
        discount_amount: float = 0.0,
    ) -> dict:
        expenses = self._expense_repo.find_by_order(order_id)
        bill_id_set = set(bill_ids)
        scoped = [e for e in expenses if e.bill_id and e.bill_id in bill_id_set]
        # MPH excludes discount: margin is measured on the gross amount.
        return self._domain.calculate_mph(max(invoice_amount, 0.0), scoped)

    def preview_item_mph(
        self,
        order_id: str,
        item_amounts: Dict[str, float],
        item_discounts: Optional[Dict[str, float]] = None,
        exclude_invoice_id: Optional[str] = None,
    ) -> List[dict]:
        """Per-item margin preview for the invoice dialog.

        MPH is computed on cumulative *gross* revenue (this invoice plus any
        prior invoices for the same item), so discounts never affect MPH and
        re-invoicing is additive. Each row also carries the previously invoiced
        net amount and this invoice's discount/net for display.
        """
        if not item_amounts:
            return []
        expenses = self._expense_repo.find_by_order(order_id)
        exp_by_bill: Dict[str, list] = {}
        for e in expenses:
            if e.bill_id:
                exp_by_bill.setdefault(e.bill_id, []).append(e)
        existing = self._invoice_repo.list_by_order(order_id)
        item_discounts = item_discounts or {}
        rows = []
        for bill_id, gross in item_amounts.items():
            prev_gross = self._domain.item_gross_revenue(
                bill_id, existing, exclude_invoice_id=exclude_invoice_id
            )
            prev_net = (
                self._domain.item_net_revenue(
                    bill_id, existing, exclude_invoice_id=exclude_invoice_id
                )
                or 0.0
            )
            cumulative_gross = round(prev_gross + gross, 2)
            discount = round(float(item_discounts.get(bill_id, 0.0)), 2)
            net = round(gross - discount, 2)
            data = self._domain.calculate_item_mph(
                cumulative_gross, exp_by_bill.get(bill_id, [])
            )
            rows.append(
                {
                    "bill_id": bill_id,
                    "gross": round(gross, 2),
                    "discount": discount,
                    "net": net,
                    "previously_invoiced": round(prev_net, 2),
                    "cumulative_gross": cumulative_gross,
                    **data,
                }
            )
        return rows
