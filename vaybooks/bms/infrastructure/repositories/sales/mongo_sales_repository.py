from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.identity.location_access import merge_mongo_filters

from vaybooks.bms.domain.sales.entities import (
    DeliveryCharges,
    DeliveryNote,
    DeliveryNoteLine,
    Estimate,
    EstimateLine,
    Quotation,
    SalesOrder,
    SalesOrderLine,
    SalesReturn,
    SalesReturnLine,
)
from vaybooks.bms.domain.shared.document_customization import (
    dataclass_to_dict,
    snapshot_from_dict,
)
from vaybooks.bms.domain.shared.enums import (
    DeliveryChargePaymentStatus,
    DeliveryNoteStatus,
    DeliveryReferenceType,
    EstimateStatus,
    QuotationStatus,
    SalesOrderStatus,
    SalesReturnStatus,
)


def _enum_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


class MongoSalesOrderRepository:
    def __init__(self, db: Database):
        self._collection = db.sales_orders

    def _line_to_doc(self, line: SalesOrderLine) -> dict:
        return {
            "id": line.id,
            "product_id": line.product_id,
            "product_name": line.product_name,
            "qty_ordered": line.qty_ordered,
            "qty_delivered": line.qty_delivered,
            "qty_invoiced": line.qty_invoiced,
            "rate": line.rate,
            "discount": float(getattr(line, "discount", 0) or 0),
            "discount_mode": getattr(line, "discount_mode", "flat") or "flat",
            "discount_input": float(
                getattr(line, "discount_input", None)
                if getattr(line, "discount_input", None) is not None
                else getattr(line, "discount", 0)
                or 0
            ),
            "hsn_sac": line.hsn_sac,
            "gst_rate": line.gst_rate,
            "taxable_amount": line.taxable_amount,
            "cgst_amount": line.cgst_amount,
            "sgst_amount": line.sgst_amount,
            "igst_amount": line.igst_amount,
            "utgst_amount": line.utgst_amount,
        }

    def _line_from_doc(self, doc: dict) -> SalesOrderLine:
        return SalesOrderLine(
            id=doc.get("id", ""),
            product_id=doc.get("product_id", ""),
            product_name=doc.get("product_name", ""),
            qty_ordered=float(doc.get("qty_ordered") or 0),
            qty_delivered=float(doc.get("qty_delivered") or 0),
            qty_invoiced=float(doc.get("qty_invoiced") or 0),
            rate=float(doc.get("rate") or 0),
            discount=float(doc.get("discount") or 0),
            discount_mode=doc.get("discount_mode", "flat") or "flat",
            discount_input=float(
                doc.get("discount_input")
                if doc.get("discount_input") is not None
                else doc.get("discount")
                or 0
            ),
            hsn_sac=doc.get("hsn_sac", ""),
            gst_rate=float(doc.get("gst_rate") or 0),
            taxable_amount=float(doc.get("taxable_amount") or 0),
            cgst_amount=float(doc.get("cgst_amount") or 0),
            sgst_amount=float(doc.get("sgst_amount") or 0),
            igst_amount=float(doc.get("igst_amount") or 0),
            utgst_amount=float(doc.get("utgst_amount") or 0),
        )

    def _to_doc(self, order: SalesOrder) -> dict:
        od = order.order_date
        ed = order.expected_date
        return {
            "_id": order.id,
            "so_number": order.so_number,
            "customer_id": order.customer_id,
            "customer_name": order.customer_name,
            "order_date": od.isoformat() if isinstance(od, date) else od,
            "expected_date": ed.isoformat() if isinstance(ed, date) else ed,
            "status": _enum_value(order.status),
            "lines": [self._line_to_doc(line) for line in order.lines],
            "notes": order.notes,
            "supply_type": order.supply_type,
            "location_id": order.location_id,
            "location_name": order.location_name,
            "document_content": dataclass_to_dict(order.document_content),
            "created_at": order.created_at,
            "updated_at": order.updated_at,
        }

    def _from_doc(self, doc: dict) -> SalesOrder:
        od = doc.get("order_date")
        if isinstance(od, str):
            od = date.fromisoformat(od)
        ed = doc.get("expected_date")
        if isinstance(ed, str):
            ed = date.fromisoformat(ed)
        return SalesOrder(
            id=doc["_id"],
            so_number=doc["so_number"],
            customer_id=doc["customer_id"],
            customer_name=doc.get("customer_name", ""),
            order_date=od,
            expected_date=ed,
            status=SalesOrderStatus(doc.get("status", SalesOrderStatus.DRAFT.value)),
            lines=[self._line_from_doc(line) for line in doc.get("lines", [])],
            notes=doc.get("notes", ""),
            supply_type=doc.get("supply_type", ""),
            location_id=str(doc.get("location_id") or ""),
            location_name=str(doc.get("location_name") or ""),
            document_content=snapshot_from_dict(doc.get("document_content")),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, order: SalesOrder) -> SalesOrder:
        self._collection.replace_one({"_id": order.id}, self._to_doc(order), upsert=True)
        return order

    def find_by_id(self, order_id: str) -> Optional[SalesOrder]:
        doc = self._collection.find_one({"_id": order_id})
        return self._from_doc(doc) if doc else None

    def find_by_so_number(self, so_number: str) -> Optional[SalesOrder]:
        doc = self._collection.find_one({"so_number": so_number})
        return self._from_doc(doc) if doc else None

    def list_all(self, location_filter: dict | None = None) -> List[SalesOrder]:
        query = merge_mongo_filters(location_filter or {})
        return [self._from_doc(d) for d in self._collection.find(query)]

    def count_by_customer(self, customer_id: str) -> int:
        if not customer_id:
            return 0
        return self._collection.count_documents({"customer_id": customer_id})

    def delete(self, order_id: str) -> None:
        self._collection.delete_one({"_id": order_id})


class MongoDeliveryNoteRepository:
    def __init__(self, db: Database):
        self._collection = db.delivery_notes

    def _line_to_doc(self, line: DeliveryNoteLine) -> dict:
        return {
            "id": line.id,
            "product_id": line.product_id,
            "product_name": line.product_name,
            "description": line.description,
            "qty_delivered": line.qty_delivered,
            "rate": line.rate,
            "sales_order_line_id": line.sales_order_line_id,
            "sales_invoice_line_id": line.sales_invoice_line_id,
            "qty_ordered": line.qty_ordered,
            "qty_previously_delivered": line.qty_previously_delivered,
            "uom": line.uom,
            "batch_or_serial": line.batch_or_serial,
            "packages": line.packages,
            "weight": line.weight,
        }

    def _line_from_doc(self, doc: dict) -> DeliveryNoteLine:
        return DeliveryNoteLine(
            id=doc.get("id", ""),
            product_id=doc.get("product_id", ""),
            product_name=doc.get("product_name", ""),
            description=doc.get("description", ""),
            qty_delivered=float(doc.get("qty_delivered") or 0),
            rate=float(doc.get("rate") or 0),
            sales_order_line_id=doc.get("sales_order_line_id", ""),
            sales_invoice_line_id=doc.get("sales_invoice_line_id", ""),
            qty_ordered=float(doc.get("qty_ordered") or 0),
            qty_previously_delivered=float(doc.get("qty_previously_delivered") or 0),
            uom=doc.get("uom", ""),
            batch_or_serial=doc.get("batch_or_serial", ""),
            packages=float(doc.get("packages") or 0),
            weight=float(doc.get("weight") or 0),
        )

    @staticmethod
    def _charges_to_doc(charges: DeliveryCharges) -> dict:
        pd = charges.payment_date
        return {
            "paid_by_us": charges.paid_by_us,
            "recoverable_from_customer": charges.recoverable_from_customer,
            "amount": charges.amount,
            "tax_amount": charges.tax_amount,
            "gst_rate": charges.gst_rate,
            "payment_status": _enum_value(charges.payment_status),
            "payment_mode": charges.payment_mode,
            "paid_from_account_id": charges.paid_from_account_id,
            "payment_reference": charges.payment_reference,
            "payment_date": pd.isoformat() if isinstance(pd, date) else pd,
            "partner_payable_amount": charges.partner_payable_amount,
            "customer_recoverable_amount": charges.customer_recoverable_amount,
            "notes": charges.notes,
            "expense_voucher_id": charges.expense_voucher_id,
            "payment_voucher_id": charges.payment_voucher_id,
        }

    @staticmethod
    def _charges_from_doc(doc: Optional[dict]) -> DeliveryCharges:
        if not doc:
            return DeliveryCharges()
        payment_status = doc.get("payment_status") or DeliveryChargePaymentStatus.UNPAID.value
        try:
            payment_status = DeliveryChargePaymentStatus(payment_status)
        except ValueError:
            payment_status = DeliveryChargePaymentStatus.UNPAID
        payment_date = doc.get("payment_date")
        if isinstance(payment_date, str) and payment_date:
            payment_date = date.fromisoformat(payment_date)
        elif not isinstance(payment_date, date):
            payment_date = None
        return DeliveryCharges(
            paid_by_us=bool(doc.get("paid_by_us")),
            recoverable_from_customer=bool(doc.get("recoverable_from_customer")),
            amount=float(doc.get("amount") or 0),
            tax_amount=float(doc.get("tax_amount") or 0),
            gst_rate=float(doc.get("gst_rate") or 0),
            payment_status=payment_status,
            payment_mode=doc.get("payment_mode", ""),
            paid_from_account_id=doc.get("paid_from_account_id", ""),
            payment_reference=doc.get("payment_reference", ""),
            payment_date=payment_date,
            partner_payable_amount=float(doc.get("partner_payable_amount") or 0),
            customer_recoverable_amount=float(doc.get("customer_recoverable_amount") or 0),
            notes=doc.get("notes", ""),
            expense_voucher_id=doc.get("expense_voucher_id"),
            payment_voucher_id=doc.get("payment_voucher_id"),
        )

    def _to_doc(self, dn: DeliveryNote) -> dict:
        dd = dn.delivery_date
        ed = dn.expected_delivery_date

        def _dt(value):
            if value is None:
                return None
            if hasattr(value, "isoformat"):
                return value.isoformat()
            return value

        return {
            "_id": dn.id,
            "dn_number": dn.dn_number,
            "sales_order_id": dn.sales_order_id,
            "so_number": dn.so_number,
            "sales_invoice_id": dn.sales_invoice_id,
            "invoice_number": dn.invoice_number,
            "reference_type": _enum_value(dn.reference_type),
            "customer_id": dn.customer_id,
            "customer_name": dn.customer_name,
            "billing_address": dn.billing_address,
            "delivery_address": dn.delivery_address,
            "contact_person": dn.contact_person,
            "contact_phone": dn.contact_phone,
            "gstin": dn.gstin,
            "delivery_date": dd.isoformat() if isinstance(dd, date) else dd,
            "status": _enum_value(dn.status),
            "lines": [self._line_to_doc(line) for line in dn.lines],
            "notes": dn.notes,
            "dispatch_at": _dt(dn.dispatch_at),
            "expected_delivery_date": ed.isoformat() if isinstance(ed, date) else ed,
            "actual_delivery_at": _dt(dn.actual_delivery_at),
            "delivery_partner_id": dn.delivery_partner_id,
            "delivery_partner_name": dn.delivery_partner_name,
            "vehicle_number": dn.vehicle_number,
            "driver_name": dn.driver_name,
            "driver_phone": dn.driver_phone,
            "lr_consignment_number": dn.lr_consignment_number,
            "eway_bill_number": dn.eway_bill_number,
            "number_of_packages": dn.number_of_packages,
            "gross_weight": dn.gross_weight,
            "net_weight": dn.net_weight,
            "receiver_name": dn.receiver_name,
            "receiver_phone": dn.receiver_phone,
            "receiver_acknowledgement": dn.receiver_acknowledgement,
            "received_at": _dt(dn.received_at),
            "attachments": dn.attachments,
            "charges": self._charges_to_doc(dn.charges),
            "stock_issued": dn.stock_issued,
            "stock_source": dn.stock_source,
            "override_qty_reason": dn.override_qty_reason,
            "status_history": dn.status_history,
            "change_log": dn.change_log,
            "voucher_id": dn.voucher_id,
            "location_id": dn.location_id,
            "location_name": dn.location_name,
            "document_content": dataclass_to_dict(dn.document_content),
            "created_at": dn.created_at,
            "updated_at": dn.updated_at,
        }

    def _from_doc(self, doc: dict) -> DeliveryNote:
        dd = doc.get("delivery_date")
        if isinstance(dd, str):
            dd = date.fromisoformat(dd)
        ed = doc.get("expected_delivery_date")
        if isinstance(ed, str) and ed:
            ed = date.fromisoformat(ed)
        elif not isinstance(ed, date):
            ed = None

        def _parse_dt(value):
            if not value:
                return None
            if isinstance(value, datetime):
                return value
            if isinstance(value, str):
                try:
                    return datetime.fromisoformat(value)
                except ValueError:
                    return None
            return None

        status_raw = doc.get("status", DeliveryNoteStatus.DRAFT.value)
        try:
            status = DeliveryNoteStatus(status_raw)
        except ValueError:
            status = DeliveryNoteStatus.DRAFT
        # Legacy docs: Delivered implied stock already issued
        stock_issued = bool(doc.get("stock_issued"))
        if status == DeliveryNoteStatus.DELIVERED and "stock_issued" not in doc:
            stock_issued = True
        ref_raw = doc.get("reference_type")
        if ref_raw:
            try:
                reference_type = DeliveryReferenceType(ref_raw)
            except ValueError:
                reference_type = DeliveryReferenceType.DIRECT
        elif doc.get("sales_order_id"):
            reference_type = DeliveryReferenceType.SALES_ORDER
        elif doc.get("sales_invoice_id"):
            reference_type = DeliveryReferenceType.INVOICE
        else:
            reference_type = DeliveryReferenceType.DIRECT
        return DeliveryNote(
            id=doc["_id"],
            dn_number=doc["dn_number"],
            sales_order_id=doc.get("sales_order_id"),
            so_number=doc.get("so_number", ""),
            sales_invoice_id=doc.get("sales_invoice_id"),
            invoice_number=doc.get("invoice_number", ""),
            reference_type=reference_type,
            customer_id=doc["customer_id"],
            customer_name=doc.get("customer_name", ""),
            billing_address=doc.get("billing_address", ""),
            delivery_address=doc.get("delivery_address", ""),
            contact_person=doc.get("contact_person", ""),
            contact_phone=doc.get("contact_phone", ""),
            gstin=doc.get("gstin", ""),
            delivery_date=dd,
            status=status,
            lines=[self._line_from_doc(line) for line in doc.get("lines", [])],
            notes=doc.get("notes", ""),
            dispatch_at=_parse_dt(doc.get("dispatch_at")),
            expected_delivery_date=ed,
            actual_delivery_at=_parse_dt(doc.get("actual_delivery_at")),
            delivery_partner_id=doc.get("delivery_partner_id", ""),
            delivery_partner_name=doc.get("delivery_partner_name", ""),
            vehicle_number=doc.get("vehicle_number", ""),
            driver_name=doc.get("driver_name", ""),
            driver_phone=doc.get("driver_phone", ""),
            lr_consignment_number=doc.get("lr_consignment_number", ""),
            eway_bill_number=doc.get("eway_bill_number", ""),
            number_of_packages=float(doc.get("number_of_packages") or 0),
            gross_weight=float(doc.get("gross_weight") or 0),
            net_weight=float(doc.get("net_weight") or 0),
            receiver_name=doc.get("receiver_name", ""),
            receiver_phone=doc.get("receiver_phone", ""),
            receiver_acknowledgement=doc.get("receiver_acknowledgement", ""),
            received_at=_parse_dt(doc.get("received_at")),
            attachments=list(doc.get("attachments") or []),
            charges=self._charges_from_doc(doc.get("charges")),
            stock_issued=stock_issued,
            stock_source=doc.get("stock_source", "delivery_note" if stock_issued else ""),
            override_qty_reason=doc.get("override_qty_reason", ""),
            status_history=list(doc.get("status_history") or []),
            change_log=list(doc.get("change_log") or []),
            voucher_id=doc.get("voucher_id"),
            location_id=str(doc.get("location_id") or ""),
            location_name=str(doc.get("location_name") or ""),
            document_content=snapshot_from_dict(doc.get("document_content")),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, dn: DeliveryNote) -> DeliveryNote:
        self._collection.replace_one({"_id": dn.id}, self._to_doc(dn), upsert=True)
        return dn

    def find_by_id(self, dn_id: str) -> Optional[DeliveryNote]:
        doc = self._collection.find_one({"_id": dn_id})
        return self._from_doc(doc) if doc else None

    def find_by_dn_number(self, dn_number: str) -> Optional[DeliveryNote]:
        doc = self._collection.find_one({"dn_number": dn_number})
        return self._from_doc(doc) if doc else None

    def list_all(self, location_filter: dict | None = None) -> List[DeliveryNote]:
        query = merge_mongo_filters(location_filter or {})
        return [self._from_doc(d) for d in self._collection.find(query)]

    def count_by_customer(self, customer_id: str) -> int:
        if not customer_id:
            return 0
        return self._collection.count_documents({"customer_id": customer_id})

    def list_by_so(self, sales_order_id: str) -> List[DeliveryNote]:
        docs = self._collection.find({"sales_order_id": sales_order_id})
        return [self._from_doc(d) for d in docs]

    def list_by_invoice(self, sales_invoice_id: str) -> List[DeliveryNote]:
        docs = self._collection.find({"sales_invoice_id": sales_invoice_id})
        return [self._from_doc(d) for d in docs]

    def list_by_partner(self, delivery_partner_id: str) -> List[DeliveryNote]:
        docs = self._collection.find({"delivery_partner_id": delivery_partner_id})
        return [self._from_doc(d) for d in docs]

    def delete(self, dn_id: str) -> None:
        self._collection.delete_one({"_id": dn_id})

class MongoSalesReturnRepository:
    def __init__(self, db: Database):
        self._collection = db.sales_returns

    def _line_to_doc(self, line: SalesReturnLine) -> dict:
        return {
            "id": line.id,
            "product_id": line.product_id,
            "product_name": line.product_name,
            "qty": line.qty,
            "rate": line.rate,
        }

    def _line_from_doc(self, doc: dict) -> SalesReturnLine:
        return SalesReturnLine(
            id=doc.get("id", ""),
            product_id=doc.get("product_id", ""),
            product_name=doc.get("product_name", ""),
            qty=float(doc.get("qty") or 0),
            rate=float(doc.get("rate") or 0),
        )

    def _to_doc(self, sales_return: SalesReturn) -> dict:
        rd = sales_return.return_date
        return {
            "_id": sales_return.id,
            "return_number": sales_return.return_number,
            "customer_id": sales_return.customer_id,
            "customer_name": sales_return.customer_name,
            "return_date": rd.isoformat() if isinstance(rd, date) else rd,
            "lines": [self._line_to_doc(line) for line in sales_return.lines],
            "source_invoice_id": sales_return.source_invoice_id,
            "source_invoice_number": sales_return.source_invoice_number,
            "source_dn_id": sales_return.source_dn_id,
            "voucher_id": sales_return.voucher_id,
            "notes": sales_return.notes,
            "return_reason": sales_return.return_reason,
            "refund_option": sales_return.refund_option,
            "amount_refunded": sales_return.amount_refunded,
            "refund_account_id": sales_return.refund_account_id,
            "status": _enum_value(sales_return.status),
            "restock_items": sales_return.restock_items,
            "attachments": sales_return.attachments,
            "approved_at": sales_return.approved_at,
            "rejected_at": sales_return.rejected_at,
            "goods_received_at": sales_return.goods_received_at,
            "refund_processed_at": sales_return.refund_processed_at,
            "closed_at": sales_return.closed_at,
            "location_id": sales_return.location_id,
            "location_name": sales_return.location_name,
            "created_at": sales_return.created_at,
            "updated_at": sales_return.updated_at,
        }

    def _from_doc(self, doc: dict) -> SalesReturn:
        rd = doc.get("return_date")
        if isinstance(rd, str):
            rd = date.fromisoformat(rd)
        return SalesReturn(
            id=doc["_id"],
            return_number=doc["return_number"],
            customer_id=doc["customer_id"],
            customer_name=doc.get("customer_name", ""),
            return_date=rd,
            lines=[self._line_from_doc(line) for line in doc.get("lines", [])],
            source_invoice_id=doc.get("source_invoice_id"),
            source_invoice_number=doc.get("source_invoice_number", ""),
            source_dn_id=doc.get("source_dn_id"),
            voucher_id=doc.get("voucher_id"),
            notes=doc.get("notes", ""),
            return_reason=doc.get("return_reason", ""),
            refund_option=doc.get("refund_option", "Customer credit"),
            amount_refunded=float(doc.get("amount_refunded") or 0),
            refund_account_id=doc.get("refund_account_id"),
            status=SalesReturnStatus(
                SalesReturnStatus.PENDING.value
                if doc.get("status") == "Draft"
                else doc.get("status", SalesReturnStatus.APPROVED.value)
            ),
            restock_items=bool(doc.get("restock_items", True)),
            attachments=list(doc.get("attachments") or []),
            approved_at=doc.get("approved_at"),
            rejected_at=doc.get("rejected_at"),
            goods_received_at=doc.get("goods_received_at"),
            refund_processed_at=doc.get("refund_processed_at"),
            closed_at=doc.get("closed_at"),
            location_id=str(doc.get("location_id") or ""),
            location_name=str(doc.get("location_name") or ""),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, sales_return: SalesReturn) -> SalesReturn:
        self._collection.replace_one(
            {"_id": sales_return.id}, self._to_doc(sales_return), upsert=True
        )
        return sales_return

    def find_by_id(self, return_id: str) -> Optional[SalesReturn]:
        doc = self._collection.find_one({"_id": return_id})
        return self._from_doc(doc) if doc else None

    def list_all(self, location_filter: dict | None = None) -> List[SalesReturn]:
        query = merge_mongo_filters(location_filter or {})
        return [self._from_doc(d) for d in self._collection.find(query)]

    def count_by_customer(self, customer_id: str) -> int:
        if not customer_id:
            return 0
        return self._collection.count_documents({"customer_id": customer_id})

    def delete(self, return_id: str) -> None:
        self._collection.delete_one({"_id": return_id})


class _MongoPricedDocumentRepository:
    document_class = Estimate
    status_class = EstimateStatus
    collection_name = "estimates"
    number_field = "estimate_number"
    date_field = "estimate_date"

    def __init__(self, db: Database):
        self._collection = db[self.collection_name]

    @staticmethod
    def _line_to_doc(line: EstimateLine) -> dict:
        return {
            "id": line.id,
            "product_id": line.product_id,
            "product_name": line.product_name,
            "qty": line.qty,
            "rate": line.rate,
            "hsn_sac": line.hsn_sac,
            "gst_rate": line.gst_rate,
            "taxable_amount": line.taxable_amount,
            "cgst_amount": line.cgst_amount,
            "sgst_amount": line.sgst_amount,
            "igst_amount": line.igst_amount,
            "utgst_amount": line.utgst_amount,
        }

    @staticmethod
    def _line_from_doc(doc: dict) -> EstimateLine:
        return EstimateLine(
            id=str(doc.get("id") or ""),
            product_id=str(doc.get("product_id") or ""),
            product_name=str(doc.get("product_name") or ""),
            qty=float(doc.get("qty") or 0),
            rate=float(doc.get("rate") or 0),
            hsn_sac=str(doc.get("hsn_sac") or ""),
            gst_rate=float(doc.get("gst_rate") or 0),
            taxable_amount=float(doc.get("taxable_amount") or 0),
            cgst_amount=float(doc.get("cgst_amount") or 0),
            sgst_amount=float(doc.get("sgst_amount") or 0),
            igst_amount=float(doc.get("igst_amount") or 0),
            utgst_amount=float(doc.get("utgst_amount") or 0),
        )

    def _to_doc(self, value) -> dict:
        document_date = getattr(value, self.date_field)
        valid_until = value.valid_until
        doc = {
            "_id": value.id,
            self.number_field: getattr(value, self.number_field),
            "customer_id": value.customer_id,
            "customer_name": value.customer_name,
            self.date_field: (
                document_date.isoformat()
                if isinstance(document_date, date)
                else document_date
            ),
            "valid_until": (
                valid_until.isoformat() if isinstance(valid_until, date) else valid_until
            ),
            "status": _enum_value(value.status),
            "lines": [self._line_to_doc(line) for line in value.lines],
            "notes": value.notes,
            "supply_type": value.supply_type,
            "location_id": value.location_id,
            "location_name": value.location_name,
            "document_content": dataclass_to_dict(value.document_content),
            "created_at": value.created_at,
            "updated_at": value.updated_at,
        }
        if isinstance(value, Quotation):
            doc["converted_sales_order_id"] = value.converted_sales_order_id
        if isinstance(value, Estimate):
            doc["converted_sales_order_id"] = value.converted_sales_order_id
            doc["converted_invoice_id"] = value.converted_invoice_id
        return doc

    def _from_doc(self, doc: dict):
        document_date = doc.get(self.date_field)
        if isinstance(document_date, str):
            document_date = date.fromisoformat(document_date)
        valid_until = doc.get("valid_until")
        if isinstance(valid_until, str):
            valid_until = date.fromisoformat(valid_until)
        kwargs = {
            "id": str(doc["_id"]),
            self.number_field: str(doc.get(self.number_field) or ""),
            "customer_id": str(doc.get("customer_id") or ""),
            "customer_name": str(doc.get("customer_name") or ""),
            self.date_field: document_date,
            "valid_until": valid_until,
            "status": self.status_class(doc.get("status", self.status_class.DRAFT.value)),
            "lines": [self._line_from_doc(line) for line in doc.get("lines", [])],
            "notes": str(doc.get("notes") or ""),
            "supply_type": str(doc.get("supply_type") or ""),
            "location_id": str(doc.get("location_id") or ""),
            "location_name": str(doc.get("location_name") or ""),
            "document_content": snapshot_from_dict(doc.get("document_content")),
            "created_at": doc.get("created_at", datetime.utcnow()),
            "updated_at": doc.get("updated_at", datetime.utcnow()),
        }
        if self.document_class is Quotation:
            kwargs["converted_sales_order_id"] = doc.get("converted_sales_order_id")
        if self.document_class is Estimate:
            kwargs["converted_sales_order_id"] = doc.get("converted_sales_order_id")
            kwargs["converted_invoice_id"] = doc.get("converted_invoice_id")
        return self.document_class(**kwargs)

    def save(self, value):
        self._collection.replace_one({"_id": value.id}, self._to_doc(value), upsert=True)
        return value

    def find_by_id(self, value_id: str):
        doc = self._collection.find_one({"_id": value_id})
        return self._from_doc(doc) if doc else None

    def find_by_number(self, number: str):
        doc = self._collection.find_one({self.number_field: number})
        return self._from_doc(doc) if doc else None

    def list_all(self, location_filter: dict | None = None):
        query = merge_mongo_filters(location_filter or {})
        return [self._from_doc(doc) for doc in self._collection.find(query)]

    def count_by_customer(self, customer_id: str) -> int:
        if not customer_id:
            return 0
        return self._collection.count_documents({"customer_id": customer_id})

    def delete(self, value_id: str) -> None:
        self._collection.delete_one({"_id": value_id})


class MongoEstimateRepository(_MongoPricedDocumentRepository):
    document_class = Estimate
    status_class = EstimateStatus
    collection_name = "estimates"
    number_field = "estimate_number"
    date_field = "estimate_date"


class MongoQuotationRepository(_MongoPricedDocumentRepository):
    document_class = Quotation
    status_class = QuotationStatus
    collection_name = "quotations"
    number_field = "quotation_number"
    date_field = "quotation_date"
