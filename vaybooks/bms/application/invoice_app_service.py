from datetime import date
from typing import List, Optional

from vaybooks.bms.domain.accounting.repository import CounterRepository
from vaybooks.bms.domain.expenses.repository import ExpenseRepository
from vaybooks.bms.domain.invoices.entities import Invoice
from vaybooks.bms.domain.invoices.repository import InvoiceRepository
from vaybooks.bms.domain.invoices.services import InvoiceDomainService
from vaybooks.bms.domain.orders.repository import OrderRepository
from vaybooks.bms.domain.orders.services import OrderDomainService
from vaybooks.bms.domain.shared.date_utils import utc_now


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

    def _resolve_income_account_id(self, income_account_id: Optional[str]) -> str:
        if income_account_id:
            return income_account_id
        income_accounts = self._accounting.get_income_accounts()
        if not income_accounts:
            raise ValueError(
                "No income account configured to credit the sale. "
                "Create one in the Accounts page."
            )
        # Prefer an account named "Sales", otherwise the first income account.
        for account in income_accounts:
            if account.account_name.strip().lower() == "sales":
                return account.id
        return income_accounts[0].id

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
        income_account_id: Optional[str],
    ) -> None:
        """Create, update, or void the Dr Customer / Dr Discount / Cr Sales voucher."""
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
        income_id = self._resolve_income_account_id(income_account_id)
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
            )

    def generate_invoice(
        self,
        order_id: str,
        bill_ids: List[str],
        invoice_amount: float,
        invoice_date: Optional[date] = None,
        allow_already_invoiced: bool = False,
    ) -> Invoice:
        order = self._order_repo.find_by_id(order_id)
        expenses = self._expense_repo.find_by_order(order_id)
        existing = self._invoice_repo.list_by_order(order_id)
        invoice_number = self._counter_repo.next("invoice_number")
        inv_date = invoice_date or date.today()

        invoice = self._domain.generate_invoice(
            order=order,
            invoice_number=invoice_number,
            invoice_date=inv_date,
            invoice_amount=invoice_amount,
            bill_ids=bill_ids,
            expenses=expenses,
            existing_invoices=existing,
            allow_already_invoiced=allow_already_invoiced,
        )

        invoices = existing + [invoice]
        deliveries = (
            self._delivery_repo.list_by_order(order_id) if self._delivery_repo else []
        )
        self._order_domain.recalculate_status(order, invoices, deliveries)
        order.updated_at = utc_now()
        self._order_repo.save(order)
        return invoice

    def record_invoice(
        self,
        order_id: str,
        invoice_number: str,
        bill_ids: List[str],
        invoice_amount: float,
        invoice_date: Optional[date] = None,
        allow_already_invoiced: bool = False,
        post_entry: bool = False,
        income_account_id: Optional[str] = None,
        discount_amount: float = 0.0,
    ) -> Invoice:
        if not invoice_number or not invoice_number.strip():
            raise ValueError("Invoice number is required")
        order = self._order_repo.find_by_id(order_id)
        expenses = self._expense_repo.find_by_order(order_id)
        existing = self._invoice_repo.list_by_order(order_id)
        inv_date = invoice_date or date.today()

        invoice = self._domain.generate_invoice(
            order=order,
            invoice_number=invoice_number.strip(),
            invoice_date=inv_date,
            invoice_amount=invoice_amount,
            bill_ids=bill_ids,
            expenses=expenses,
            existing_invoices=existing,
            allow_already_invoiced=allow_already_invoiced,
            discount_amount=discount_amount,
        )

        self._sync_sales_posting(order, invoice, post_entry, income_account_id)

        invoices = existing + [invoice]
        deliveries = (
            self._delivery_repo.list_by_order(order_id) if self._delivery_repo else []
        )
        self._order_domain.recalculate_status(order, invoices, deliveries)
        order.updated_at = utc_now()
        self._order_repo.save(order)
        return invoice

    def update_invoice(
        self,
        invoice_id: str,
        invoice_number: str,
        bill_ids: List[str],
        invoice_amount: float,
        invoice_date: Optional[date] = None,
        allow_already_invoiced: bool = True,
        post_entry: bool = False,
        income_account_id: Optional[str] = None,
        discount_amount: float = 0.0,
    ) -> Invoice:
        invoice = self._invoice_repo.find_by_id(invoice_id)
        if not invoice:
            raise ValueError("Invoice not found")
        if not invoice_number or not invoice_number.strip():
            raise ValueError("Invoice number is required")
        if invoice_amount <= 0:
            raise ValueError("Invoice amount is required")
        discount_amount = round(discount_amount or 0.0, 2)
        if discount_amount < 0:
            raise ValueError("Discount cannot be negative")
        if discount_amount > invoice_amount:
            raise ValueError("Discount cannot exceed the invoice amount")

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
        scoped = [e for e in expenses if e.bill_id and e.bill_id in bill_id_set]
        # Margin realized on net (after discount).
        mph = self._domain.calculate_mph(invoice_amount - discount_amount, scoped)

        invoice.invoice_number = invoice_number.strip()
        invoice.bill_ids = list(bill_ids)
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

        self._sync_sales_posting(order, saved, post_entry, income_account_id)

        deliveries = (
            self._delivery_repo.list_by_order(invoice.order_id)
            if self._delivery_repo
            else []
        )
        self._order_domain.recalculate_status(order, others + [saved], deliveries)
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
        net = max(invoice_amount - (discount_amount or 0.0), 0.0)
        return self._domain.calculate_mph(net, scoped)
