from __future__ import annotations

from datetime import date
from typing import List, Optional

from vaybooks.bms.domain.purchases.entities import (
    GoodsReceipt,
    GoodsReceiptLine,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseReturn,
    PurchaseReturnLine,
)
from vaybooks.bms.domain.purchases.repository import (
    GoodsReceiptRepository,
    PurchaseOrderRepository,
    PurchaseReturnRepository,
)
from vaybooks.bms.domain.shared.enums import (
    GoodsReceiptStatus,
    PurchaseOrderStatus,
)
from vaybooks.bms.domain.shared.exceptions import ValidationError


def _allocate_landed_extras_by_value(
    lines: List[GoodsReceiptLine], freight: float, duty: float, other: float
) -> None:
    """Allocate header freight/duty/other to lines proportionally by line value."""
    extras = round(freight + duty + other, 2)
    if extras <= 0 or not lines:
        return
    base_total = sum(round(line.qty_received * line.rate, 2) for line in lines)
    if base_total <= 0:
        per_line = round(extras / len(lines), 2)
        for line in lines:
            line.landed_cost_extra = round(line.landed_cost_extra + per_line, 2)
        return
    allocated = 0.0
    for idx, line in enumerate(lines):
        base = round(line.qty_received * line.rate, 2)
        if idx == len(lines) - 1:
            share = round(extras - allocated, 2)
        else:
            share = round(extras * base / base_total, 2)
            allocated += share
        line.landed_cost_extra = round(line.landed_cost_extra + share, 2)


class PurchaseDomainService:
    def __init__(
        self,
        po_repo: PurchaseOrderRepository,
        grn_repo: GoodsReceiptRepository,
        return_repo: PurchaseReturnRepository,
    ):
        self._po_repo = po_repo
        self._grn_repo = grn_repo
        self._return_repo = return_repo

    def create_purchase_order(
        self,
        po_number: str,
        vendor_id: str,
        vendor_name: str,
        order_date: date,
        lines: List[dict],
        expected_date: Optional[date] = None,
        notes: str = "",
        status: PurchaseOrderStatus = PurchaseOrderStatus.DRAFT,
        project_id: str = "",
    ) -> PurchaseOrder:
        if not vendor_id:
            raise ValidationError("Vendor is required")
        if not lines:
            raise ValidationError("At least one line is required")
        po_lines = []
        for raw in lines:
            qty = float(raw.get("qty_ordered") or raw.get("qty") or 0)
            if qty <= 0:
                raise ValidationError("Ordered quantity must be positive")
            po_lines.append(
                PurchaseOrderLine(
                    product_id=str(raw.get("product_id") or ""),
                    product_name=(raw.get("product_name") or "").strip(),
                    qty_ordered=round(qty, 2),
                    rate=round(float(raw.get("rate") or 0), 2),
                    expense_account_id=str(raw.get("expense_account_id") or ""),
                )
            )
        order = PurchaseOrder(
            po_number=po_number,
            vendor_id=vendor_id,
            vendor_name=vendor_name,
            order_date=order_date,
            expected_date=expected_date,
            lines=po_lines,
            notes=notes.strip(),
            status=status,
            project_id=(project_id or "").strip(),
        )
        return self._po_repo.save(order)

    def update_purchase_order(
        self,
        order_id: str,
        vendor_id: str,
        vendor_name: str,
        order_date: date,
        lines: List[dict],
        expected_date: Optional[date] = None,
        notes: str = "",
        status: Optional[PurchaseOrderStatus] = None,
    ) -> PurchaseOrder:
        order = self._po_repo.find_by_id(order_id)
        if not order:
            raise ValidationError("Purchase order not found")
        if order.status in (PurchaseOrderStatus.CANCELLED, PurchaseOrderStatus.CLOSED):
            raise ValidationError("Cannot edit a closed or cancelled purchase order")
        received_by_product = {
            line.product_id: line.qty_received for line in order.lines
        }
        po_lines = []
        for raw in lines:
            product_id = str(raw.get("product_id") or "")
            qty = float(raw.get("qty_ordered") or raw.get("qty") or 0)
            if qty <= 0:
                raise ValidationError("Ordered quantity must be positive")
            already = received_by_product.get(product_id, 0.0)
            if qty < already - 0.001:
                raise ValidationError(
                    "Ordered quantity cannot be less than already received"
                )
            po_lines.append(
                PurchaseOrderLine(
                    product_id=product_id,
                    product_name=(raw.get("product_name") or "").strip(),
                    qty_ordered=round(qty, 2),
                    rate=round(float(raw.get("rate") or 0), 2),
                    expense_account_id=str(raw.get("expense_account_id") or ""),
                    qty_received=round(already, 2),
                )
            )
        order.update(
            vendor_id=vendor_id,
            vendor_name=vendor_name,
            order_date=order_date,
            expected_date=expected_date,
            lines=po_lines,
            notes=notes.strip(),
        )
        if status is not None:
            order.status = status
        self._refresh_po_status(order)
        return self._po_repo.save(order)

    def cancel_purchase_order(self, order_id: str) -> PurchaseOrder:
        order = self._po_repo.find_by_id(order_id)
        if not order:
            raise ValidationError("Purchase order not found")
        if any(line.qty_received > 0 for line in order.lines):
            raise ValidationError("Cannot cancel a purchase order with receipts")
        order.status = PurchaseOrderStatus.CANCELLED
        return self._po_repo.save(order)

    def close_purchase_order(self, order_id: str) -> PurchaseOrder:
        order = self._po_repo.find_by_id(order_id)
        if not order:
            raise ValidationError("Purchase order not found")
        order.status = PurchaseOrderStatus.CLOSED
        return self._po_repo.save(order)

    def create_grn(
        self,
        grn_number: str,
        vendor_id: str,
        vendor_name: str,
        receipt_date: date,
        lines: List[dict],
        purchase_order_id: Optional[str] = None,
        po_number: str = "",
        freight: float = 0.0,
        duty: float = 0.0,
        other: float = 0.0,
        notes: str = "",
        allow_over_receive: bool = False,
    ) -> GoodsReceipt:
        if not lines:
            raise ValidationError("At least one receipt line is required")
        po: Optional[PurchaseOrder] = None
        if purchase_order_id:
            po = self._po_repo.find_by_id(purchase_order_id)
            if not po:
                raise ValidationError("Purchase order not found")
            if po.status == PurchaseOrderStatus.CANCELLED:
                raise ValidationError("Cannot receive against a cancelled PO")
        grn_lines: List[GoodsReceiptLine] = []
        for raw in lines:
            qty = float(raw.get("qty_received") or raw.get("qty") or 0)
            if qty <= 0:
                raise ValidationError("Received quantity must be positive")
            product_id = str(raw.get("product_id") or "")
            if po:
                po_line = next(
                    (pl for pl in po.lines if pl.product_id == product_id), None
                )
                if not po_line:
                    raise ValidationError("Product not on purchase order")
                pending = po_line.qty_pending
                if not allow_over_receive and qty > pending + 0.001:
                    raise ValidationError(
                        f"Cannot receive more than pending ({pending:g}) for {po_line.product_name or product_id}"
                    )
            grn_lines.append(
                GoodsReceiptLine(
                    product_id=product_id,
                    product_name=(raw.get("product_name") or "").strip(),
                    qty_received=round(qty, 2),
                    rate=round(float(raw.get("rate") or 0), 2),
                    landed_cost_extra=round(float(raw.get("landed_cost_extra") or 0), 2),
                    purchase_order_line_id=str(raw.get("purchase_order_line_id") or ""),
                )
            )
        _allocate_landed_extras_by_value(
            grn_lines, freight, duty, other
        )
        grn = GoodsReceipt(
            grn_number=grn_number,
            vendor_id=vendor_id,
            vendor_name=vendor_name,
            receipt_date=receipt_date,
            purchase_order_id=purchase_order_id,
            po_number=po_number,
            lines=grn_lines,
            freight=round(max(freight, 0.0), 2),
            duty=round(max(duty, 0.0), 2),
            other=round(max(other, 0.0), 2),
            notes=notes.strip(),
            status=GoodsReceiptStatus.DRAFT,
        )
        return self._grn_repo.save(grn)

    def confirm_grn_received(self, grn_id: str) -> GoodsReceipt:
        grn = self._grn_repo.find_by_id(grn_id)
        if not grn:
            raise ValidationError("Goods receipt not found")
        if grn.status != GoodsReceiptStatus.DRAFT:
            raise ValidationError("Goods receipt is already confirmed or cancelled")
        grn.status = GoodsReceiptStatus.RECEIVED
        saved = self._grn_repo.save(grn)
        if grn.purchase_order_id:
            po = self._po_repo.find_by_id(grn.purchase_order_id)
            if po:
                for grn_line in grn.lines:
                    for po_line in po.lines:
                        if po_line.product_id == grn_line.product_id:
                            po_line.qty_received = round(
                                po_line.qty_received + grn_line.qty_received, 2
                            )
                self._refresh_po_status(po)
                self._po_repo.save(po)
        return saved

    def cancel_grn(self, grn_id: str) -> GoodsReceipt:
        grn = self._grn_repo.find_by_id(grn_id)
        if not grn:
            raise ValidationError("Goods receipt not found")
        if grn.status == GoodsReceiptStatus.RECEIVED:
            raise ValidationError("Cannot cancel a received GRN from domain layer")
        grn.status = GoodsReceiptStatus.CANCELLED
        return self._grn_repo.save(grn)

    def create_purchase_return(
        self,
        return_number: str,
        vendor_id: str,
        vendor_name: str,
        return_date: date,
        lines: List[dict],
        source_bill_id: Optional[str] = None,
        source_grn_id: Optional[str] = None,
        notes: str = "",
    ) -> PurchaseReturn:
        if not lines:
            raise ValidationError("At least one return line is required")
        ret_lines = []
        for raw in lines:
            qty = float(raw.get("qty") or 0)
            if qty <= 0:
                raise ValidationError("Return quantity must be positive")
            ret_lines.append(
                PurchaseReturnLine(
                    product_id=str(raw.get("product_id") or ""),
                    product_name=(raw.get("product_name") or "").strip(),
                    qty=round(qty, 2),
                    rate=round(float(raw.get("rate") or 0), 2),
                    expense_account_id=str(raw.get("expense_account_id") or ""),
                )
            )
        purchase_return = PurchaseReturn(
            return_number=return_number,
            vendor_id=vendor_id,
            vendor_name=vendor_name,
            return_date=return_date,
            lines=ret_lines,
            source_bill_id=source_bill_id,
            source_grn_id=source_grn_id,
            notes=notes.strip(),
        )
        return self._return_repo.save(purchase_return)

    def _refresh_po_status(self, order: PurchaseOrder) -> None:
        if order.status in (PurchaseOrderStatus.CANCELLED, PurchaseOrderStatus.CLOSED):
            return
        if not order.lines:
            order.status = PurchaseOrderStatus.DRAFT
            return
        total_ordered = sum(line.qty_ordered for line in order.lines)
        total_received = sum(line.qty_received for line in order.lines)
        if total_received <= 0:
            if order.status == PurchaseOrderStatus.PARTIALLY_RECEIVED:
                order.status = PurchaseOrderStatus.SENT
            return
        if total_received + 0.001 >= total_ordered:
            order.status = PurchaseOrderStatus.RECEIVED
        else:
            order.status = PurchaseOrderStatus.PARTIALLY_RECEIVED

    def grn_to_stock_lines(self, grn: GoodsReceipt) -> list[dict]:
        return [
            {
                "product_id": line.product_id,
                "qty": line.qty_received,
                "rate": line.unit_cost,
                "description": line.product_name or "GRN receive",
            }
            for line in grn.lines
        ]

    def grn_to_landed_cost_lines(self, grn: GoodsReceipt) -> list[dict]:
        return [
            {
                "product_id": line.product_id,
                "qty": line.qty_received,
                "unit_cost": line.unit_cost,
            }
            for line in grn.lines
        ]
