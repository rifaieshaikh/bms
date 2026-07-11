from __future__ import annotations

from datetime import date
from typing import List, Optional

from vaybooks.bms.application.accounting_app_service import AccountingAppService
from vaybooks.bms.application.inventory_app_service import InventoryAppService
from vaybooks.bms.domain.accounting.entities import Voucher
from vaybooks.bms.domain.accounting.sales_parsing import sales_row_from_voucher
from vaybooks.bms.domain.customers.entities import Customer
from vaybooks.bms.domain.sales.entities import DeliveryNote, SalesOrder, SalesReturn
from vaybooks.bms.domain.sales.line_items import (
    apply_invoice_discount_to_lines,
    serialize_sales_line_items,
    tax_summary_from_lines,
)
from vaybooks.bms.domain.sales.repository import (
    DeliveryNoteRepository,
    SalesOrderRepository,
    SalesReturnRepository,
)
from vaybooks.bms.domain.sales.sales_line_resolver import (
    SalesLineResolver,
    business_is_registered,
)
from vaybooks.bms.domain.sales.services import SalesDomainService
from vaybooks.bms.domain.shared.enums import (
    DeliveryNoteStatus,
    SalesOrderStatus,
    StockReferenceType,
    VoucherType,
)
from vaybooks.bms.infrastructure.repositories.mongo_counter_repository import (
    MongoCounterRepository,
)


class SalesAppService:
    def __init__(
        self,
        so_repo: SalesOrderRepository,
        dn_repo: DeliveryNoteRepository,
        return_repo: SalesReturnRepository,
        counter_repo: MongoCounterRepository,
        accounting: AccountingAppService,
        inventory: InventoryAppService,
        customer_service=None,
        business_service=None,
    ):
        self._so_repo = so_repo
        self._dn_repo = dn_repo
        self._return_repo = return_repo
        self._counter_repo = counter_repo
        self._accounting = accounting
        self._inventory = inventory
        self._customer_service = customer_service
        self._business_service = business_service
        self._domain = SalesDomainService(so_repo, dn_repo, return_repo)

    def _line_resolver(self) -> SalesLineResolver:
        return SalesLineResolver(get_product=self._inventory.get_product)

    def _customer_from_account(self, customer_account_id: str) -> Customer:
        account = self._accounting.get_account(customer_account_id)
        if not account or not account.linked_customer_id:
            raise ValueError("Customer not found for account")
        if not self._customer_service:
            raise ValueError("Customer service not configured")
        customer = self._customer_service.get_customer_detail(account.linked_customer_id)
        if not customer:
            raise ValueError("Customer not found")
        return customer

    def _prepare_sales_invoice(
        self,
        customer_account_id: str,
        raw_lines: list[dict],
        invoice_discount: float = 0.0,
    ) -> tuple[list[dict], str, float]:
        customer = self._customer_from_account(customer_account_id)
        business = (
            self._business_service.get_profile()
            if self._business_service
            else None
        )
        resolved = self._line_resolver().resolve_lines(
            raw_lines, customer=customer, business=business
        )
        if invoice_discount > 0:
            resolved = apply_invoice_discount_to_lines(
                resolved,
                invoice_discount,
                business_registered=business_is_registered(business),
                business_state_code=business.state_code if business else "",
                customer_state_code=customer.state_code if customer else "",
            )
        sales_lines = [line.to_line_dict() for line in resolved]
        summary = tax_summary_from_lines(resolved)
        note = serialize_sales_line_items(
            sales_lines,
            invoice_discount=invoice_discount,
            tax_summary=summary,
        )
        return sales_lines, note, summary["grand_total"]

    def list_sales_orders(self) -> List[SalesOrder]:
        return self._so_repo.list_all()

    def get_sales_order(self, order_id: str) -> Optional[SalesOrder]:
        return self._so_repo.find_by_id(order_id)

    def create_sales_order(
        self,
        customer_id: str,
        order_date: date,
        lines: list[dict],
        expected_date: Optional[date] = None,
        notes: str = "",
        status: SalesOrderStatus = SalesOrderStatus.CONFIRMED,
    ) -> SalesOrder:
        so_number = self._counter_repo.next("so_number")
        return self._domain.create_sales_order(
            so_number=so_number,
            customer_id=customer_id,
            customer_name=self._customer_name(customer_id),
            order_date=order_date,
            lines=lines,
            expected_date=expected_date,
            notes=notes,
            status=status,
        )

    def update_sales_order(
        self,
        order_id: str,
        customer_id: str,
        order_date: date,
        lines: list[dict],
        expected_date: Optional[date] = None,
        notes: str = "",
        status: Optional[SalesOrderStatus] = None,
    ) -> SalesOrder:
        return self._domain.update_sales_order(
            order_id,
            customer_id,
            self._customer_name(customer_id),
            order_date,
            lines,
            expected_date,
            notes,
            status,
        )

    def cancel_sales_order(self, order_id: str) -> SalesOrder:
        return self._domain.cancel_sales_order(order_id)

    def close_sales_order(self, order_id: str) -> SalesOrder:
        return self._domain.close_sales_order(order_id)

    def list_delivery_notes(self) -> List[DeliveryNote]:
        return self._dn_repo.list_all()

    def get_delivery_note(self, dn_id: str) -> Optional[DeliveryNote]:
        return self._dn_repo.find_by_id(dn_id)

    def create_delivery_note(
        self,
        customer_id: str,
        delivery_date: date,
        lines: list[dict],
        sales_order_id: Optional[str] = None,
        notes: str = "",
        confirm: bool = True,
    ) -> DeliveryNote:
        so_number = ""
        if sales_order_id:
            so = self._so_repo.find_by_id(sales_order_id)
            so_number = so.so_number if so else ""
        dn_number = self._counter_repo.next("dn_number")
        dn = self._domain.create_delivery_note(
            dn_number=dn_number,
            customer_id=customer_id,
            customer_name=self._customer_name(customer_id),
            delivery_date=delivery_date,
            lines=lines,
            sales_order_id=sales_order_id,
            so_number=so_number,
            notes=notes,
        )
        if confirm:
            return self.confirm_delivery_note(dn.id)
        return dn

    def confirm_delivery_note(self, dn_id: str) -> DeliveryNote:
        dn = self._dn_repo.find_by_id(dn_id)
        if not dn:
            raise ValueError("Delivery note not found")
        if dn.status == DeliveryNoteStatus.DELIVERED:
            return dn
        stock_lines = self._domain.dn_to_stock_lines(dn)
        self._inventory.apply_delivery_note_issue(
            dn.id, stock_lines, dn.delivery_date
        )
        return self._domain.confirm_delivery_note(dn_id)

    def create_sales_invoice(
        self,
        customer_account_id: str,
        store_account_id: str,
        gross_amount: float,
        discount_amount: float,
        amount_received: float,
        store_invoice_number: str,
        line_items_note: str = "",
        voucher_date: Optional[date] = None,
        reference_so_id: Optional[str] = None,
        reference_dn_id: Optional[str] = None,
        line_items: Optional[list[dict]] = None,
        invoice_discount: float = 0.0,
    ) -> Voucher:
        sales_lines = None
        note = line_items_note
        if line_items:
            sales_lines, note, grand_total = self._prepare_sales_invoice(
                customer_account_id,
                line_items,
                invoice_discount=invoice_discount,
            )
            gross_amount = grand_total
            discount_amount = 0.0
            amount_received = round(min(amount_received, grand_total), 2)

        voucher = self._accounting.create_cash_sales_invoice(
            customer_account_id=customer_account_id,
            store_account_id=store_account_id,
            gross_amount=gross_amount,
            discount_amount=discount_amount,
            amount_received=amount_received,
            store_invoice_number=store_invoice_number,
            line_items_note=note,
            voucher_date=voucher_date,
            reference_so_id=reference_so_id,
            reference_dn_id=reference_dn_id,
            sales_lines=sales_lines,
        )
        if reference_dn_id:
            dn = self._dn_repo.find_by_id(reference_dn_id)
            if dn:
                dn.voucher_id = voucher.id
                self._dn_repo.save(dn)
        elif line_items:
            self._inventory.apply_sales_movements(
                voucher.id, line_items, voucher_date
            )
        if reference_so_id and line_items:
            self._domain.mark_so_invoiced(reference_so_id, line_items)
        return voucher

    def create_direct_sale(
        self,
        customer_account_id: str,
        store_account_id: str,
        gross_amount: float,
        discount_amount: float,
        amount_received: float,
        store_invoice_number: str,
        line_items: list[dict],
        line_items_note: str = "",
        voucher_date: Optional[date] = None,
        invoice_discount: float = 0.0,
    ) -> Voucher:
        line_discount_total = round(discount_amount - invoice_discount, 2)
        if line_discount_total < 0:
            line_discount_total = 0.0
        return self.create_sales_invoice(
            customer_account_id=customer_account_id,
            store_account_id=store_account_id,
            gross_amount=gross_amount,
            discount_amount=discount_amount,
            amount_received=amount_received,
            store_invoice_number=store_invoice_number,
            line_items_note=line_items_note,
            voucher_date=voucher_date,
            line_items=line_items,
            invoice_discount=invoice_discount,
        )

    def create_sales_invoice_from_dn(
        self,
        dn_id: str,
        store_account_id: str,
        store_invoice_number: str,
        discount_amount: float = 0.0,
        amount_received: float = 0.0,
        voucher_date: Optional[date] = None,
        line_items_note: str = "",
    ) -> Voucher:
        dn = self._dn_repo.find_by_id(dn_id)
        if not dn:
            raise ValueError("Delivery note not found")
        if dn.status != DeliveryNoteStatus.DELIVERED:
            raise ValueError("Invoice can only be created from a delivered note")
        if dn.voucher_id:
            raise ValueError("This delivery note is already invoiced")
        customer_account = self._accounting.get_customer_account(dn.customer_id)
        if not customer_account:
            raise ValueError("Customer account not found")
        raw_lines = [
            {
                "product_id": line.product_id,
                "qty": line.qty_delivered,
                "rate": line.rate,
                "description": line.product_name,
            }
            for line in dn.lines
        ]
        if not line_items_note:
            line_items_note = "\n".join(
                f"{line.product_name or line.product_id}: {line.qty_delivered:g} @ {line.rate:g}"
                for line in dn.lines
            )
        return self.create_sales_invoice(
            customer_account_id=customer_account.id,
            store_account_id=store_account_id,
            gross_amount=dn.total_amount,
            discount_amount=discount_amount,
            amount_received=amount_received,
            store_invoice_number=store_invoice_number,
            line_items_note=line_items_note,
            voucher_date=voucher_date or dn.delivery_date,
            reference_so_id=dn.sales_order_id,
            reference_dn_id=dn.id,
            line_items=raw_lines,
            invoice_discount=discount_amount,
        )

    def list_sales_returns(self) -> List[SalesReturn]:
        return self._return_repo.list_all()

    def get_sales_return(self, return_id: str) -> Optional[SalesReturn]:
        return self._return_repo.find_by_id(return_id)

    def create_sales_return(
        self,
        customer_id: str,
        return_date: date,
        lines: list[dict],
        source_invoice_id: Optional[str] = None,
        source_dn_id: Optional[str] = None,
        amount_refunded: float = 0.0,
        refund_account_id: Optional[str] = None,
        notes: str = "",
    ) -> SalesReturn:
        customer_account = self._accounting.get_customer_account(customer_id)
        if not customer_account:
            raise ValueError("Customer account not found")
        return_number = self._counter_repo.next("sales_return_number")
        sales_return = self._domain.create_sales_return(
            return_number=return_number,
            customer_id=customer_id,
            customer_name=self._customer_name(customer_id),
            return_date=return_date,
            lines=lines,
            source_invoice_id=source_invoice_id,
            source_dn_id=source_dn_id,
            notes=notes,
        )
        return_amount = sales_return.total_amount
        description = f"Sales return {return_number}"
        if notes.strip():
            description = f"{description} — {notes.strip()}"
        voucher = self._accounting.create_sales_return_voucher(
            customer_account_id=customer_account.id,
            return_amount=return_amount,
            description=description,
            amount_refunded=amount_refunded,
            refund_account_id=refund_account_id,
            voucher_date=return_date,
            reference_dn_id=source_dn_id,
            source_invoice_id=source_invoice_id,
        )
        sales_return.voucher_id = voucher.id
        self._return_repo.save(sales_return)
        stock_lines = [
            {
                "product_id": line.product_id,
                "qty": line.qty,
                "description": line.product_name or "Return",
            }
            for line in sales_return.lines
        ]
        self._inventory.apply_sales_return(
            sales_return.id, stock_lines, return_date
        )
        return sales_return

    def list_sales_invoices(self) -> list[dict]:
        discount = self._accounting.get_discount_account()
        discount_id = discount.id if discount else None
        rows = []
        for voucher in self._accounting.list_vouchers_by_type(VoucherType.SALES_INVOICE):
            row = sales_row_from_voucher(voucher, discount_id)
            row["reference_so_id"] = getattr(voucher, "reference_so_id", None)
            row["reference_dn_id"] = getattr(voucher, "reference_dn_id", None)
            rows.append(row)
        rows.sort(
            key=lambda r: (r.get("sale_date") or date.min, r.get("voucher_number") or ""),
            reverse=True,
        )
        return rows

    def get_sales_invoice(self, voucher_id: str) -> Optional[dict]:
        voucher = self._accounting.get_voucher(voucher_id)
        if not voucher or voucher.voucher_type != VoucherType.SALES_INVOICE:
            return None
        discount = self._accounting.get_discount_account()
        discount_id = discount.id if discount else None
        row = sales_row_from_voucher(voucher, discount_id)
        row["reference_so_id"] = getattr(voucher, "reference_so_id", None)
        row["reference_dn_id"] = getattr(voucher, "reference_dn_id", None)
        return row

    def delete_sales_invoice(self, voucher_id: str) -> None:
        old = self._accounting.get_voucher(voucher_id)
        if not old or old.voucher_type != VoucherType.SALES_INVOICE:
            raise ValueError("Sales invoice not found")
        if old.reference_dn_id:
            raise ValueError("Cannot delete a delivery-linked sales invoice")
        if not old.reference_so_id:
            self._inventory.reverse_movements_by_reference(voucher_id)
        self._accounting.void_voucher(voucher_id)

    def _customer_name(self, customer_id: str) -> str:
        if not self._customer_service or not customer_id:
            return ""
        customer = self._customer_service.get_customer_detail(customer_id)
        return customer.customer_name if customer else ""
