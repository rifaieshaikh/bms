from __future__ import annotations

from datetime import date
from typing import List, Optional

from vaybooks.bms.domain.sales.entities import (
    DeliveryNote,
    DeliveryNoteLine,
    SalesOrder,
    SalesOrderLine,
    SalesReturn,
    SalesReturnLine,
)
from vaybooks.bms.domain.sales.repository import (
    DeliveryNoteRepository,
    SalesOrderRepository,
    SalesReturnRepository,
)
from vaybooks.bms.domain.shared.enums import DeliveryNoteStatus, SalesOrderStatus
from vaybooks.bms.domain.shared.exceptions import ValidationError


class SalesDomainService:
    def __init__(
        self,
        so_repo: SalesOrderRepository,
        dn_repo: DeliveryNoteRepository,
        return_repo: SalesReturnRepository,
    ):
        self._so_repo = so_repo
        self._dn_repo = dn_repo
        self._return_repo = return_repo

    def create_sales_order(
        self,
        so_number: str,
        customer_id: str,
        customer_name: str,
        order_date: date,
        lines: List[dict],
        expected_date: Optional[date] = None,
        notes: str = "",
        status: SalesOrderStatus = SalesOrderStatus.DRAFT,
    ) -> SalesOrder:
        if not customer_id:
            raise ValidationError("Customer is required")
        if not lines:
            raise ValidationError("At least one line is required")
        so_lines = []
        for raw in lines:
            qty = float(raw.get("qty_ordered") or raw.get("qty") or 0)
            if qty <= 0:
                raise ValidationError("Ordered quantity must be positive")
            so_lines.append(
                SalesOrderLine(
                    product_id=str(raw.get("product_id") or ""),
                    product_name=(raw.get("product_name") or "").strip(),
                    qty_ordered=round(qty, 2),
                    rate=round(float(raw.get("rate") or 0), 2),
                )
            )
        order = SalesOrder(
            so_number=so_number,
            customer_id=customer_id,
            customer_name=customer_name,
            order_date=order_date,
            expected_date=expected_date,
            lines=so_lines,
            notes=notes.strip(),
            status=status,
        )
        return self._so_repo.save(order)

    def update_sales_order(
        self,
        order_id: str,
        customer_id: str,
        customer_name: str,
        order_date: date,
        lines: List[dict],
        expected_date: Optional[date] = None,
        notes: str = "",
        status: Optional[SalesOrderStatus] = None,
    ) -> SalesOrder:
        order = self._so_repo.find_by_id(order_id)
        if not order:
            raise ValidationError("Sales order not found")
        if order.status in (SalesOrderStatus.CANCELLED, SalesOrderStatus.CLOSED):
            raise ValidationError("Cannot edit a closed or cancelled sales order")
        delivered_by_product = {
            line.product_id: line.qty_delivered for line in order.lines
        }
        so_lines = []
        for raw in lines:
            product_id = str(raw.get("product_id") or "")
            qty = float(raw.get("qty_ordered") or raw.get("qty") or 0)
            if qty <= 0:
                raise ValidationError("Ordered quantity must be positive")
            already = delivered_by_product.get(product_id, 0.0)
            if qty < already - 0.001:
                raise ValidationError(
                    "Ordered quantity cannot be less than already delivered"
                )
            so_lines.append(
                SalesOrderLine(
                    product_id=product_id,
                    product_name=(raw.get("product_name") or "").strip(),
                    qty_ordered=round(qty, 2),
                    rate=round(float(raw.get("rate") or 0), 2),
                    qty_delivered=round(already, 2),
                    qty_invoiced=round(
                        float(
                            next(
                                (
                                    ol.qty_invoiced
                                    for ol in order.lines
                                    if ol.product_id == product_id
                                ),
                                0.0,
                            )
                        ),
                        2,
                    ),
                )
            )
        order.update(
            customer_id=customer_id,
            customer_name=customer_name,
            order_date=order_date,
            expected_date=expected_date,
            lines=so_lines,
            notes=notes.strip(),
        )
        if status is not None:
            order.status = status
        self._refresh_so_status(order)
        return self._so_repo.save(order)

    def cancel_sales_order(self, order_id: str) -> SalesOrder:
        order = self._so_repo.find_by_id(order_id)
        if not order:
            raise ValidationError("Sales order not found")
        if any(line.qty_delivered > 0 for line in order.lines):
            raise ValidationError("Cannot cancel a sales order with deliveries")
        order.status = SalesOrderStatus.CANCELLED
        return self._so_repo.save(order)

    def close_sales_order(self, order_id: str) -> SalesOrder:
        order = self._so_repo.find_by_id(order_id)
        if not order:
            raise ValidationError("Sales order not found")
        order.status = SalesOrderStatus.CLOSED
        return self._so_repo.save(order)

    def create_delivery_note(
        self,
        dn_number: str,
        customer_id: str,
        customer_name: str,
        delivery_date: date,
        lines: List[dict],
        sales_order_id: Optional[str] = None,
        so_number: str = "",
        notes: str = "",
    ) -> DeliveryNote:
        if not lines:
            raise ValidationError("At least one delivery line is required")
        so: Optional[SalesOrder] = None
        if sales_order_id:
            so = self._so_repo.find_by_id(sales_order_id)
            if not so:
                raise ValidationError("Sales order not found")
            if so.status == SalesOrderStatus.CANCELLED:
                raise ValidationError("Cannot deliver against a cancelled sales order")
        dn_lines: List[DeliveryNoteLine] = []
        for raw in lines:
            qty = float(raw.get("qty_delivered") or raw.get("qty") or 0)
            if qty <= 0:
                raise ValidationError("Delivered quantity must be positive")
            product_id = str(raw.get("product_id") or "")
            if so:
                so_line = next(
                    (sl for sl in so.lines if sl.product_id == product_id), None
                )
                if not so_line:
                    raise ValidationError("Product not on sales order")
                pending = so_line.qty_pending
                if qty > pending + 0.001:
                    raise ValidationError(
                        f"Cannot deliver more than pending ({pending:g}) for "
                        f"{so_line.product_name or product_id}"
                    )
            dn_lines.append(
                DeliveryNoteLine(
                    product_id=product_id,
                    product_name=(raw.get("product_name") or "").strip(),
                    qty_delivered=round(qty, 2),
                    rate=round(float(raw.get("rate") or 0), 2),
                    sales_order_line_id=str(raw.get("sales_order_line_id") or ""),
                )
            )
        dn = DeliveryNote(
            dn_number=dn_number,
            customer_id=customer_id,
            customer_name=customer_name,
            delivery_date=delivery_date,
            sales_order_id=sales_order_id,
            so_number=so_number,
            lines=dn_lines,
            notes=notes.strip(),
            status=DeliveryNoteStatus.DRAFT,
        )
        return self._dn_repo.save(dn)

    def confirm_delivery_note(self, dn_id: str) -> DeliveryNote:
        dn = self._dn_repo.find_by_id(dn_id)
        if not dn:
            raise ValidationError("Delivery note not found")
        if dn.status != DeliveryNoteStatus.DRAFT:
            raise ValidationError("Delivery note is already confirmed or cancelled")
        dn.status = DeliveryNoteStatus.DELIVERED
        saved = self._dn_repo.save(dn)
        if dn.sales_order_id:
            so = self._so_repo.find_by_id(dn.sales_order_id)
            if so:
                for dn_line in dn.lines:
                    for so_line in so.lines:
                        if so_line.product_id == dn_line.product_id:
                            so_line.qty_delivered = round(
                                so_line.qty_delivered + dn_line.qty_delivered, 2
                            )
                self._refresh_so_status(so)
                self._so_repo.save(so)
        return saved

    def cancel_delivery_note(self, dn_id: str) -> DeliveryNote:
        dn = self._dn_repo.find_by_id(dn_id)
        if not dn:
            raise ValidationError("Delivery note not found")
        if dn.status == DeliveryNoteStatus.DELIVERED:
            raise ValidationError("Cannot cancel a delivered note from domain layer")
        dn.status = DeliveryNoteStatus.CANCELLED
        return self._dn_repo.save(dn)

    def create_sales_return(
        self,
        return_number: str,
        customer_id: str,
        customer_name: str,
        return_date: date,
        lines: List[dict],
        source_invoice_id: Optional[str] = None,
        source_dn_id: Optional[str] = None,
        notes: str = "",
    ) -> SalesReturn:
        if not lines:
            raise ValidationError("At least one return line is required")
        ret_lines = []
        for raw in lines:
            qty = float(raw.get("qty") or 0)
            if qty <= 0:
                raise ValidationError("Return quantity must be positive")
            ret_lines.append(
                SalesReturnLine(
                    product_id=str(raw.get("product_id") or ""),
                    product_name=(raw.get("product_name") or "").strip(),
                    qty=round(qty, 2),
                    rate=round(float(raw.get("rate") or 0), 2),
                )
            )
        sales_return = SalesReturn(
            return_number=return_number,
            customer_id=customer_id,
            customer_name=customer_name,
            return_date=return_date,
            lines=ret_lines,
            source_invoice_id=source_invoice_id,
            source_dn_id=source_dn_id,
            notes=notes.strip(),
        )
        return self._return_repo.save(sales_return)

    def mark_so_invoiced(self, sales_order_id: str, lines: List[dict]) -> None:
        if not sales_order_id:
            return
        so = self._so_repo.find_by_id(sales_order_id)
        if not so:
            return
        for raw in lines:
            product_id = str(raw.get("product_id") or "")
            qty = float(raw.get("qty") or raw.get("qty_delivered") or 0)
            for so_line in so.lines:
                if so_line.product_id == product_id:
                    so_line.qty_invoiced = round(so_line.qty_invoiced + qty, 2)
        self._so_repo.save(so)

    def _refresh_so_status(self, order: SalesOrder) -> None:
        if order.status in (SalesOrderStatus.CANCELLED, SalesOrderStatus.CLOSED):
            return
        if not order.lines:
            order.status = SalesOrderStatus.DRAFT
            return
        total_ordered = sum(line.qty_ordered for line in order.lines)
        total_delivered = sum(line.qty_delivered for line in order.lines)
        if total_delivered <= 0:
            if order.status == SalesOrderStatus.PARTIALLY_DELIVERED:
                order.status = SalesOrderStatus.CONFIRMED
            return
        if total_delivered + 0.001 >= total_ordered:
            order.status = SalesOrderStatus.DELIVERED
        else:
            order.status = SalesOrderStatus.PARTIALLY_DELIVERED

    def dn_to_stock_lines(self, dn: DeliveryNote) -> list[dict]:
        return [
            {
                "product_id": line.product_id,
                "qty": line.qty_delivered,
                "description": line.product_name or "Delivery",
            }
            for line in dn.lines
        ]
