from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.purchases.entities import (
    GoodsReceipt,
    GoodsReceiptLine,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseReturn,
    PurchaseReturnLine,
)
from vaybooks.bms.domain.shared.enums import GoodsReceiptStatus, PurchaseOrderStatus


def _enum_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


class MongoPurchaseOrderRepository:
    def __init__(self, db: Database):
        self._collection = db.purchase_orders

    def _line_to_doc(self, line: PurchaseOrderLine) -> dict:
        return {
            "id": line.id,
            "product_id": line.product_id,
            "product_name": line.product_name,
            "qty_ordered": line.qty_ordered,
            "qty_received": line.qty_received,
            "rate": line.rate,
            "expense_account_id": line.expense_account_id,
        }

    def _line_from_doc(self, doc: dict) -> PurchaseOrderLine:
        return PurchaseOrderLine(
            id=doc.get("id", ""),
            product_id=doc.get("product_id", ""),
            product_name=doc.get("product_name", ""),
            qty_ordered=float(doc.get("qty_ordered") or 0),
            qty_received=float(doc.get("qty_received") or 0),
            rate=float(doc.get("rate") or 0),
            expense_account_id=doc.get("expense_account_id", ""),
        )

    def _to_doc(self, order: PurchaseOrder) -> dict:
        od = order.order_date
        ed = order.expected_date
        return {
            "_id": order.id,
            "po_number": order.po_number,
            "vendor_id": order.vendor_id,
            "vendor_name": order.vendor_name,
            "order_date": od.isoformat() if isinstance(od, date) else od,
            "expected_date": ed.isoformat() if isinstance(ed, date) else ed,
            "status": _enum_value(order.status),
            "lines": [self._line_to_doc(line) for line in order.lines],
            "notes": order.notes,
            "project_id": order.project_id,
            "created_at": order.created_at,
            "updated_at": order.updated_at,
        }

    def _from_doc(self, doc: dict) -> PurchaseOrder:
        od = doc.get("order_date")
        if isinstance(od, str):
            od = date.fromisoformat(od)
        ed = doc.get("expected_date")
        if isinstance(ed, str):
            ed = date.fromisoformat(ed)
        return PurchaseOrder(
            id=doc["_id"],
            po_number=doc["po_number"],
            vendor_id=doc["vendor_id"],
            vendor_name=doc.get("vendor_name", ""),
            order_date=od,
            expected_date=ed,
            status=PurchaseOrderStatus(doc.get("status", PurchaseOrderStatus.DRAFT.value)),
            lines=[self._line_from_doc(line) for line in doc.get("lines", [])],
            notes=doc.get("notes", ""),
            project_id=doc.get("project_id", ""),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, order: PurchaseOrder) -> PurchaseOrder:
        self._collection.replace_one({"_id": order.id}, self._to_doc(order), upsert=True)
        return order

    def find_by_id(self, order_id: str) -> Optional[PurchaseOrder]:
        doc = self._collection.find_one({"_id": order_id})
        return self._from_doc(doc) if doc else None

    def find_by_po_number(self, po_number: str) -> Optional[PurchaseOrder]:
        doc = self._collection.find_one({"po_number": po_number})
        return self._from_doc(doc) if doc else None

    def list_all(self) -> List[PurchaseOrder]:
        return [self._from_doc(d) for d in self._collection.find()]

    def delete(self, order_id: str) -> None:
        self._collection.delete_one({"_id": order_id})


class MongoGoodsReceiptRepository:
    def __init__(self, db: Database):
        self._collection = db.goods_receipts

    def _line_to_doc(self, line: GoodsReceiptLine) -> dict:
        return {
            "id": line.id,
            "product_id": line.product_id,
            "product_name": line.product_name,
            "qty_received": line.qty_received,
            "rate": line.rate,
            "landed_cost_extra": line.landed_cost_extra,
            "purchase_order_line_id": line.purchase_order_line_id,
        }

    def _line_from_doc(self, doc: dict) -> GoodsReceiptLine:
        return GoodsReceiptLine(
            id=doc.get("id", ""),
            product_id=doc.get("product_id", ""),
            product_name=doc.get("product_name", ""),
            qty_received=float(doc.get("qty_received") or 0),
            rate=float(doc.get("rate") or 0),
            landed_cost_extra=float(doc.get("landed_cost_extra") or 0),
            purchase_order_line_id=doc.get("purchase_order_line_id", ""),
        )

    def _to_doc(self, grn: GoodsReceipt) -> dict:
        rd = grn.receipt_date
        return {
            "_id": grn.id,
            "grn_number": grn.grn_number,
            "purchase_order_id": grn.purchase_order_id,
            "po_number": grn.po_number,
            "vendor_id": grn.vendor_id,
            "vendor_name": grn.vendor_name,
            "receipt_date": rd.isoformat() if isinstance(rd, date) else rd,
            "status": _enum_value(grn.status),
            "lines": [self._line_to_doc(line) for line in grn.lines],
            "freight": grn.freight,
            "duty": grn.duty,
            "other": grn.other,
            "notes": grn.notes,
            "voucher_id": grn.voucher_id,
            "created_at": grn.created_at,
            "updated_at": grn.updated_at,
        }

    def _from_doc(self, doc: dict) -> GoodsReceipt:
        rd = doc.get("receipt_date")
        if isinstance(rd, str):
            rd = date.fromisoformat(rd)
        return GoodsReceipt(
            id=doc["_id"],
            grn_number=doc["grn_number"],
            purchase_order_id=doc.get("purchase_order_id"),
            po_number=doc.get("po_number", ""),
            vendor_id=doc["vendor_id"],
            vendor_name=doc.get("vendor_name", ""),
            receipt_date=rd,
            status=GoodsReceiptStatus(doc.get("status", GoodsReceiptStatus.DRAFT.value)),
            lines=[self._line_from_doc(line) for line in doc.get("lines", [])],
            freight=float(doc.get("freight") or 0),
            duty=float(doc.get("duty") or 0),
            other=float(doc.get("other") or 0),
            notes=doc.get("notes", ""),
            voucher_id=doc.get("voucher_id"),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, grn: GoodsReceipt) -> GoodsReceipt:
        self._collection.replace_one({"_id": grn.id}, self._to_doc(grn), upsert=True)
        return grn

    def find_by_id(self, grn_id: str) -> Optional[GoodsReceipt]:
        doc = self._collection.find_one({"_id": grn_id})
        return self._from_doc(doc) if doc else None

    def find_by_grn_number(self, grn_number: str) -> Optional[GoodsReceipt]:
        doc = self._collection.find_one({"grn_number": grn_number})
        return self._from_doc(doc) if doc else None

    def list_all(self) -> List[GoodsReceipt]:
        return [self._from_doc(d) for d in self._collection.find()]

    def list_by_po(self, purchase_order_id: str) -> List[GoodsReceipt]:
        docs = self._collection.find({"purchase_order_id": purchase_order_id})
        return [self._from_doc(d) for d in docs]

    def delete(self, grn_id: str) -> None:
        self._collection.delete_one({"_id": grn_id})


class MongoPurchaseReturnRepository:
    def __init__(self, db: Database):
        self._collection = db.purchase_returns

    def _line_to_doc(self, line: PurchaseReturnLine) -> dict:
        return {
            "id": line.id,
            "product_id": line.product_id,
            "product_name": line.product_name,
            "qty": line.qty,
            "rate": line.rate,
            "expense_account_id": line.expense_account_id,
        }

    def _line_from_doc(self, doc: dict) -> PurchaseReturnLine:
        return PurchaseReturnLine(
            id=doc.get("id", ""),
            product_id=doc.get("product_id", ""),
            product_name=doc.get("product_name", ""),
            qty=float(doc.get("qty") or 0),
            rate=float(doc.get("rate") or 0),
            expense_account_id=doc.get("expense_account_id", ""),
        )

    def _to_doc(self, purchase_return: PurchaseReturn) -> dict:
        rd = purchase_return.return_date
        return {
            "_id": purchase_return.id,
            "return_number": purchase_return.return_number,
            "vendor_id": purchase_return.vendor_id,
            "vendor_name": purchase_return.vendor_name,
            "return_date": rd.isoformat() if isinstance(rd, date) else rd,
            "lines": [self._line_to_doc(line) for line in purchase_return.lines],
            "source_bill_id": purchase_return.source_bill_id,
            "source_grn_id": purchase_return.source_grn_id,
            "voucher_id": purchase_return.voucher_id,
            "notes": purchase_return.notes,
            "created_at": purchase_return.created_at,
            "updated_at": purchase_return.updated_at,
        }

    def _from_doc(self, doc: dict) -> PurchaseReturn:
        rd = doc.get("return_date")
        if isinstance(rd, str):
            rd = date.fromisoformat(rd)
        return PurchaseReturn(
            id=doc["_id"],
            return_number=doc["return_number"],
            vendor_id=doc["vendor_id"],
            vendor_name=doc.get("vendor_name", ""),
            return_date=rd,
            lines=[self._line_from_doc(line) for line in doc.get("lines", [])],
            source_bill_id=doc.get("source_bill_id"),
            source_grn_id=doc.get("source_grn_id"),
            voucher_id=doc.get("voucher_id"),
            notes=doc.get("notes", ""),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, purchase_return: PurchaseReturn) -> PurchaseReturn:
        self._collection.replace_one(
            {"_id": purchase_return.id}, self._to_doc(purchase_return), upsert=True
        )
        return purchase_return

    def find_by_id(self, return_id: str) -> Optional[PurchaseReturn]:
        doc = self._collection.find_one({"_id": return_id})
        return self._from_doc(doc) if doc else None

    def list_all(self) -> List[PurchaseReturn]:
        return [self._from_doc(d) for d in self._collection.find()]

    def delete(self, return_id: str) -> None:
        self._collection.delete_one({"_id": return_id})
