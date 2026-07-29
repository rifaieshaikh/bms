from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

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
from vaybooks.bms.domain.sales.repository import (
    DeliveryNoteRepository,
    EstimateRepository,
    QuotationRepository,
    SalesOrderRepository,
    SalesReturnRepository,
)
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.document_customization import DocumentContentSnapshot
from vaybooks.bms.domain.shared.enums import (
    DeliveryChargePaymentStatus,
    DeliveryNoteStatus,
    DeliveryReferenceType,
    EstimateStatus,
    QuotationStatus,
    SalesOrderStatus,
    SalesReturnStatus,
)
from vaybooks.bms.domain.shared.exceptions import ValidationError


class SalesDomainService:
    def __init__(
        self,
        so_repo: SalesOrderRepository,
        dn_repo: DeliveryNoteRepository,
        return_repo: SalesReturnRepository,
        estimate_repo: Optional[EstimateRepository] = None,
        quotation_repo: Optional[QuotationRepository] = None,
    ):
        self._so_repo = so_repo
        self._dn_repo = dn_repo
        self._return_repo = return_repo
        self._estimate_repo = estimate_repo
        self._quotation_repo = quotation_repo

    @staticmethod
    def _so_line_tax_fields(raw: dict) -> dict:
        return {
            "hsn_sac": str(raw.get("hsn_sac") or ""),
            "gst_rate": round(float(raw.get("gst_rate") or 0), 2),
            "taxable_amount": round(float(raw.get("taxable_amount") or 0), 2),
            "cgst_amount": round(float(raw.get("cgst_amount") or 0), 2),
            "sgst_amount": round(float(raw.get("sgst_amount") or 0), 2),
            "igst_amount": round(float(raw.get("igst_amount") or 0), 2),
            "utgst_amount": round(float(raw.get("utgst_amount") or 0), 2),
        }

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
        supply_type: str = "",
        location_id: str = "",
        location_name: str = "",
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
                    discount=round(max(float(raw.get("discount") or 0), 0), 2),
                    discount_mode=(raw.get("discount_mode") or "flat").strip()
                    or "flat",
                    discount_input=round(
                        float(
                            raw.get("discount_input")
                            if raw.get("discount_input") is not None
                            else raw.get("discount")
                            or 0
                        ),
                        2,
                    ),
                    **self._so_line_tax_fields(raw),
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
            supply_type=supply_type,
            location_id=(location_id or "").strip(),
            location_name=(location_name or "").strip(),
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
        supply_type: Optional[str] = None,
        location_id: Optional[str] = None,
        location_name: Optional[str] = None,
    ) -> SalesOrder:
        order = self._so_repo.find_by_id(order_id)
        if not order:
            raise ValidationError("Sales order not found")
        if order.status in (SalesOrderStatus.CANCELLED, SalesOrderStatus.CLOSED):
            raise ValidationError("Cannot edit a closed or cancelled sales order")
        committed_by_product = {
            line.product_id: max(line.qty_delivered, line.qty_invoiced)
            for line in order.lines
        }
        so_lines = []
        for raw in lines:
            product_id = str(raw.get("product_id") or "")
            qty = float(raw.get("qty_ordered") or raw.get("qty") or 0)
            if qty <= 0:
                raise ValidationError("Ordered quantity must be positive")
            already = committed_by_product.get(product_id, 0.0)
            if qty < already - 0.001:
                raise ValidationError(
                    "Ordered quantity cannot be less than already delivered or invoiced"
                )
            so_lines.append(
                SalesOrderLine(
                    product_id=product_id,
                    product_name=(raw.get("product_name") or "").strip(),
                    qty_ordered=round(qty, 2),
                    rate=round(float(raw.get("rate") or 0), 2),
                    discount=round(max(float(raw.get("discount") or 0), 0), 2),
                    discount_mode=(raw.get("discount_mode") or "flat").strip()
                    or "flat",
                    discount_input=round(
                        float(
                            raw.get("discount_input")
                            if raw.get("discount_input") is not None
                            else raw.get("discount")
                            or 0
                        ),
                        2,
                    ),
                    qty_delivered=round(
                        next(
                            (
                                line.qty_delivered
                                for line in order.lines
                                if line.product_id == product_id
                            ),
                            0.0,
                        ),
                        2,
                    ),
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
                    **self._so_line_tax_fields(raw),
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
        if supply_type is not None:
            order.supply_type = supply_type
        if location_id is not None:
            order.location_id = (location_id or "").strip()
        if location_name is not None:
            order.location_name = (location_name or "").strip()
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

    @staticmethod
    def _parse_charges(raw: Optional[dict]) -> DeliveryCharges:
        if not raw:
            return DeliveryCharges()
        payment_status = raw.get("payment_status") or DeliveryChargePaymentStatus.UNPAID
        if isinstance(payment_status, str):
            try:
                payment_status = DeliveryChargePaymentStatus(payment_status)
            except ValueError:
                payment_status = DeliveryChargePaymentStatus.UNPAID
        payment_date = raw.get("payment_date")
        if isinstance(payment_date, str) and payment_date:
            payment_date = date.fromisoformat(payment_date)
        elif not isinstance(payment_date, date):
            payment_date = None
        return DeliveryCharges(
            paid_by_us=bool(raw.get("paid_by_us")),
            recoverable_from_customer=bool(raw.get("recoverable_from_customer")),
            amount=round(float(raw.get("amount") or 0), 2),
            tax_amount=round(float(raw.get("tax_amount") or 0), 2),
            gst_rate=round(float(raw.get("gst_rate") or 0), 2),
            payment_status=payment_status,
            payment_mode=str(raw.get("payment_mode") or "").strip(),
            paid_from_account_id=str(raw.get("paid_from_account_id") or "").strip(),
            payment_reference=str(raw.get("payment_reference") or "").strip(),
            payment_date=payment_date,
            partner_payable_amount=round(
                float(raw.get("partner_payable_amount") or raw.get("amount") or 0), 2
            ),
            customer_recoverable_amount=round(
                float(
                    raw.get("customer_recoverable_amount")
                    or (
                        raw.get("amount")
                        if raw.get("recoverable_from_customer")
                        else 0
                    )
                    or 0
                ),
                2,
            ),
            notes=str(raw.get("notes") or "").strip(),
            expense_voucher_id=raw.get("expense_voucher_id"),
            payment_voucher_id=raw.get("payment_voucher_id"),
        )

    def _build_dn_lines(
        self,
        lines: List[dict],
        so: Optional[SalesOrder] = None,
        *,
        allow_override: bool = False,
        override_reason: str = "",
        invoice_pending: Optional[dict] = None,
    ) -> List[DeliveryNoteLine]:
        if not lines:
            raise ValidationError("At least one delivery line is required")
        if allow_override and not (override_reason or "").strip():
            raise ValidationError("Override reason is required when exceeding remaining quantity")
        dn_lines: List[DeliveryNoteLine] = []
        for raw in lines:
            qty = float(raw.get("qty_delivered") or raw.get("qty") or 0)
            if qty <= 0:
                raise ValidationError("Delivered quantity must be positive")
            product_id = str(raw.get("product_id") or "")
            qty_ordered = round(float(raw.get("qty_ordered") or 0), 2)
            qty_prev = round(float(raw.get("qty_previously_delivered") or 0), 2)
            if so:
                so_line = next(
                    (sl for sl in so.lines if sl.product_id == product_id), None
                )
                if not so_line:
                    raise ValidationError("Product not on sales order")
                qty_ordered = so_line.qty_ordered
                qty_prev = so_line.qty_delivered
                pending = so_line.qty_pending
                if qty > pending + 0.001 and not allow_override:
                    raise ValidationError(
                        f"Cannot deliver more than pending ({pending:g}) for "
                        f"{so_line.product_name or product_id}"
                    )
            if invoice_pending is not None:
                pending = float(invoice_pending.get(product_id, 0))
                if qty_ordered <= 0:
                    qty_ordered = round(pending + qty_prev, 2)
                if qty > pending + 0.001 and not allow_override:
                    raise ValidationError(
                        f"Cannot deliver more than invoiced pending ({pending:g}) for "
                        f"{raw.get('product_name') or product_id}"
                    )
            remaining_before = round(max(qty_ordered - qty_prev, 0.0), 2)
            if (
                qty_ordered > 0
                and qty > remaining_before + 0.001
                and not allow_override
                and so is None
                and invoice_pending is None
            ):
                raise ValidationError(
                    f"Cannot deliver more than remaining ({remaining_before:g})"
                )
            dn_lines.append(
                DeliveryNoteLine(
                    product_id=product_id,
                    product_name=(raw.get("product_name") or "").strip(),
                    description=(raw.get("description") or "").strip(),
                    qty_delivered=round(qty, 2),
                    rate=round(float(raw.get("rate") or 0), 2),
                    sales_order_line_id=str(raw.get("sales_order_line_id") or ""),
                    sales_invoice_line_id=str(raw.get("sales_invoice_line_id") or ""),
                    qty_ordered=qty_ordered,
                    qty_previously_delivered=qty_prev,
                    uom=str(raw.get("uom") or "").strip(),
                    batch_or_serial=str(raw.get("batch_or_serial") or "").strip(),
                    packages=round(float(raw.get("packages") or 0), 2),
                    weight=round(float(raw.get("weight") or 0), 2),
                )
            )
        return dn_lines

    def create_delivery_note(
        self,
        dn_number: str,
        customer_id: str,
        customer_name: str,
        delivery_date: date,
        lines: List[dict],
        sales_order_id: Optional[str] = None,
        so_number: str = "",
        sales_invoice_id: Optional[str] = None,
        invoice_number: str = "",
        reference_type: Optional[DeliveryReferenceType] = None,
        notes: str = "",
        location_id: str = "",
        location_name: str = "",
        billing_address: str = "",
        delivery_address: str = "",
        contact_person: str = "",
        contact_phone: str = "",
        gstin: str = "",
        expected_delivery_date: Optional[date] = None,
        delivery_partner_id: str = "",
        delivery_partner_name: str = "",
        vehicle_number: str = "",
        driver_name: str = "",
        driver_phone: str = "",
        lr_consignment_number: str = "",
        eway_bill_number: str = "",
        number_of_packages: float = 0.0,
        gross_weight: float = 0.0,
        net_weight: float = 0.0,
        charges: Optional[dict] = None,
        attachments: Optional[List[dict]] = None,
        allow_override: bool = False,
        override_qty_reason: str = "",
        invoice_pending: Optional[dict] = None,
        stock_source: str = "",
    ) -> DeliveryNote:
        if not customer_id:
            raise ValidationError("Customer is required")
        so: Optional[SalesOrder] = None
        if sales_order_id:
            so = self._so_repo.find_by_id(sales_order_id)
            if not so:
                raise ValidationError("Sales order not found")
            if so.status == SalesOrderStatus.CANCELLED:
                raise ValidationError("Cannot deliver against a cancelled sales order")
            so_number = so_number or so.so_number
        if reference_type is None:
            if sales_order_id:
                reference_type = DeliveryReferenceType.SALES_ORDER
            elif sales_invoice_id:
                reference_type = DeliveryReferenceType.INVOICE
            else:
                reference_type = DeliveryReferenceType.DIRECT
        dn_lines = self._build_dn_lines(
            lines,
            so,
            allow_override=allow_override,
            override_reason=override_qty_reason,
            invoice_pending=invoice_pending,
        )
        dn = DeliveryNote(
            dn_number=dn_number,
            customer_id=customer_id,
            customer_name=customer_name,
            delivery_date=delivery_date,
            sales_order_id=sales_order_id,
            so_number=so_number,
            sales_invoice_id=sales_invoice_id,
            invoice_number=invoice_number,
            reference_type=reference_type,
            lines=dn_lines,
            notes=notes.strip(),
            status=DeliveryNoteStatus.DRAFT,
            location_id=(location_id or "").strip(),
            location_name=(location_name or "").strip(),
            billing_address=(billing_address or "").strip(),
            delivery_address=(delivery_address or "").strip(),
            contact_person=(contact_person or "").strip(),
            contact_phone=(contact_phone or "").strip(),
            gstin=(gstin or "").strip(),
            expected_delivery_date=expected_delivery_date,
            delivery_partner_id=(delivery_partner_id or "").strip(),
            delivery_partner_name=(delivery_partner_name or "").strip(),
            vehicle_number=(vehicle_number or "").strip(),
            driver_name=(driver_name or "").strip(),
            driver_phone=(driver_phone or "").strip(),
            lr_consignment_number=(lr_consignment_number or "").strip(),
            eway_bill_number=(eway_bill_number or "").strip(),
            number_of_packages=round(float(number_of_packages or 0), 2),
            gross_weight=round(float(gross_weight or 0), 2),
            net_weight=round(float(net_weight or 0), 2),
            charges=self._parse_charges(charges),
            attachments=list(attachments or []),
            override_qty_reason=(override_qty_reason or "").strip(),
            stock_source=(stock_source or "").strip(),
        )
        dn.append_status(DeliveryNoteStatus.DRAFT, "Created")
        return self._dn_repo.save(dn)

    def _apply_so_delivered_qty(self, dn: DeliveryNote, *, reverse: bool = False) -> None:
        if not dn.sales_order_id:
            return
        so = self._so_repo.find_by_id(dn.sales_order_id)
        if not so:
            return
        sign = -1 if reverse else 1
        for dn_line in dn.lines:
            for so_line in so.lines:
                if so_line.product_id == dn_line.product_id:
                    so_line.qty_delivered = round(
                        max(so_line.qty_delivered + sign * dn_line.qty_delivered, 0.0), 2
                    )
        self._refresh_so_status(so)
        self._so_repo.save(so)

    def confirm_delivery_note(self, dn_id: str) -> DeliveryNote:
        dn = self._dn_repo.find_by_id(dn_id)
        if not dn:
            raise ValidationError("Delivery note not found")
        if dn.status != DeliveryNoteStatus.DRAFT:
            raise ValidationError("Only draft delivery notes can be confirmed")
        dn.status = DeliveryNoteStatus.CONFIRMED
        dn.append_status(DeliveryNoteStatus.CONFIRMED)
        dn.updated_at = utc_now()
        saved = self._dn_repo.save(dn)
        self._apply_so_delivered_qty(saved)
        return saved

    def dispatch_delivery_note(
        self, dn_id: str, *, dispatch_at: Optional[datetime] = None
    ) -> DeliveryNote:
        dn = self._dn_repo.find_by_id(dn_id)
        if not dn:
            raise ValidationError("Delivery note not found")
        if dn.status == DeliveryNoteStatus.DRAFT:
            dn = self.confirm_delivery_note(dn_id)
        if dn.status not in (
            DeliveryNoteStatus.CONFIRMED,
            DeliveryNoteStatus.PARTIALLY_DELIVERED,
        ):
            raise ValidationError("Delivery note cannot be dispatched from current status")
        dn.status = DeliveryNoteStatus.DISPATCHED
        dn.dispatch_at = dispatch_at or utc_now()
        dn.append_status(DeliveryNoteStatus.DISPATCHED)
        dn.updated_at = utc_now()
        return self._dn_repo.save(dn)

    def deliver_delivery_note(
        self,
        dn_id: str,
        *,
        partially: bool = False,
        receiver_name: str = "",
        receiver_phone: str = "",
        receiver_acknowledgement: str = "",
        received_at: Optional[datetime] = None,
        actual_delivery_at: Optional[datetime] = None,
        attachments: Optional[List[dict]] = None,
    ) -> DeliveryNote:
        dn = self._dn_repo.find_by_id(dn_id)
        if not dn:
            raise ValidationError("Delivery note not found")
        if dn.status == DeliveryNoteStatus.CANCELLED:
            raise ValidationError("Cannot deliver a cancelled note")
        if dn.status == DeliveryNoteStatus.DRAFT:
            dn = self.confirm_delivery_note(dn_id)
        if dn.status == DeliveryNoteStatus.CONFIRMED:
            dn = self.dispatch_delivery_note(dn_id)
        new_status = (
            DeliveryNoteStatus.PARTIALLY_DELIVERED
            if partially
            else DeliveryNoteStatus.DELIVERED
        )
        dn.status = new_status
        if receiver_name:
            dn.receiver_name = receiver_name.strip()
        if receiver_phone:
            dn.receiver_phone = receiver_phone.strip()
        if receiver_acknowledgement:
            dn.receiver_acknowledgement = receiver_acknowledgement.strip()
        dn.received_at = received_at or utc_now()
        dn.actual_delivery_at = actual_delivery_at or dn.received_at
        if attachments is not None:
            dn.attachments = list(attachments)
        dn.append_status(new_status)
        dn.updated_at = utc_now()
        return self._dn_repo.save(dn)

    def update_delivery_note(
        self,
        dn_id: str,
        *,
        delivery_date: date,
        lines: List[dict],
        notes: str = "",
        document_content: Optional[DocumentContentSnapshot] = None,
        location_id: Optional[str] = None,
        location_name: Optional[str] = None,
        allow_edit_delivered: bool = False,
        billing_address: Optional[str] = None,
        delivery_address: Optional[str] = None,
        contact_person: Optional[str] = None,
        contact_phone: Optional[str] = None,
        gstin: Optional[str] = None,
        expected_delivery_date: Optional[date] = None,
        delivery_partner_id: Optional[str] = None,
        delivery_partner_name: Optional[str] = None,
        vehicle_number: Optional[str] = None,
        driver_name: Optional[str] = None,
        driver_phone: Optional[str] = None,
        lr_consignment_number: Optional[str] = None,
        eway_bill_number: Optional[str] = None,
        number_of_packages: Optional[float] = None,
        gross_weight: Optional[float] = None,
        net_weight: Optional[float] = None,
        charges: Optional[dict] = None,
        attachments: Optional[List[dict]] = None,
        allow_override: bool = False,
        override_qty_reason: str = "",
        invoice_pending: Optional[dict] = None,
        dn_number: Optional[str] = None,
    ) -> DeliveryNote:
        dn = self._dn_repo.find_by_id(dn_id)
        if not dn:
            raise ValidationError("Delivery note not found")
        editable = dn.status == DeliveryNoteStatus.DRAFT or (
            allow_edit_delivered
            and dn.status
            in (
                DeliveryNoteStatus.CONFIRMED,
                DeliveryNoteStatus.DISPATCHED,
                DeliveryNoteStatus.DELIVERED,
                DeliveryNoteStatus.PARTIALLY_DELIVERED,
            )
        )
        if not editable:
            raise ValidationError("Only draft Delivery Notes can be edited")
        if dn.status != DeliveryNoteStatus.DRAFT and dn.stock_issued:
            raise ValidationError(
                "Cannot edit a delivery note after stock has been issued; cancel instead"
            )
        so = (
            self._so_repo.find_by_id(dn.sales_order_id) if dn.sales_order_id else None
        )
        dn_lines = self._build_dn_lines(
            lines,
            so,
            allow_override=allow_override,
            override_reason=override_qty_reason,
            invoice_pending=invoice_pending,
        )
        if dn_number and dn_number != dn.dn_number:
            dn.append_change("dn_number", dn.dn_number, dn_number)
            dn.dn_number = dn_number
        if vehicle_number is not None and vehicle_number != dn.vehicle_number:
            dn.append_change("vehicle_number", dn.vehicle_number, vehicle_number)
        if delivery_partner_id is not None and delivery_partner_id != dn.delivery_partner_id:
            dn.append_change(
                "delivery_partner_id", dn.delivery_partner_id, delivery_partner_id
            )
        dn.delivery_date = delivery_date
        dn.lines = dn_lines
        dn.notes = notes.strip()
        if document_content is not None:
            dn.document_content = document_content
        if location_id is not None:
            dn.location_id = (location_id or "").strip()
        if location_name is not None:
            dn.location_name = (location_name or "").strip()
        if billing_address is not None:
            dn.billing_address = billing_address.strip()
        if delivery_address is not None:
            dn.delivery_address = delivery_address.strip()
        if contact_person is not None:
            dn.contact_person = contact_person.strip()
        if contact_phone is not None:
            dn.contact_phone = contact_phone.strip()
        if gstin is not None:
            dn.gstin = gstin.strip()
        if expected_delivery_date is not None:
            dn.expected_delivery_date = expected_delivery_date
        if delivery_partner_id is not None:
            dn.delivery_partner_id = delivery_partner_id.strip()
        if delivery_partner_name is not None:
            dn.delivery_partner_name = delivery_partner_name.strip()
        if vehicle_number is not None:
            dn.vehicle_number = vehicle_number.strip()
        if driver_name is not None:
            dn.driver_name = driver_name.strip()
        if driver_phone is not None:
            dn.driver_phone = driver_phone.strip()
        if lr_consignment_number is not None:
            dn.lr_consignment_number = lr_consignment_number.strip()
        if eway_bill_number is not None:
            dn.eway_bill_number = eway_bill_number.strip()
        if number_of_packages is not None:
            dn.number_of_packages = round(float(number_of_packages or 0), 2)
        if gross_weight is not None:
            dn.gross_weight = round(float(gross_weight or 0), 2)
        if net_weight is not None:
            dn.net_weight = round(float(net_weight or 0), 2)
        if charges is not None:
            dn.append_change("charges", dn.charges.amount, charges.get("amount"))
            dn.charges = self._parse_charges(charges)
        if attachments is not None:
            dn.attachments = list(attachments)
        if override_qty_reason:
            dn.override_qty_reason = override_qty_reason.strip()
        dn.updated_at = utc_now()
        return self._dn_repo.save(dn)

    def cancel_delivery_note(self, dn_id: str, *, reverse_so_qty: bool = True) -> DeliveryNote:
        dn = self._dn_repo.find_by_id(dn_id)
        if not dn:
            raise ValidationError("Delivery note not found")
        if dn.status == DeliveryNoteStatus.CANCELLED:
            return dn
        if dn.charges.payment_voucher_id and dn.charges.payment_status == DeliveryChargePaymentStatus.PAID:
            raise ValidationError(
                "Cannot cancel: delivery partner payment already settled; reverse payment first"
            )
        was_confirmed = dn.status != DeliveryNoteStatus.DRAFT
        dn.status = DeliveryNoteStatus.CANCELLED
        dn.append_status(DeliveryNoteStatus.CANCELLED)
        dn.updated_at = utc_now()
        saved = self._dn_repo.save(dn)
        if reverse_so_qty and was_confirmed:
            self._apply_so_delivered_qty(saved, reverse=True)
        return saved

    def mark_stock_issued(self, dn_id: str, *, stock_source: str = "delivery_note") -> DeliveryNote:
        dn = self._dn_repo.find_by_id(dn_id)
        if not dn:
            raise ValidationError("Delivery note not found")
        dn.stock_issued = True
        dn.stock_source = stock_source
        dn.updated_at = utc_now()
        return self._dn_repo.save(dn)

    def create_sales_return(
        self,
        return_number: str,
        customer_id: str,
        customer_name: str,
        return_date: date,
        lines: List[dict],
        source_invoice_id: Optional[str] = None,
        source_invoice_number: str = "",
        source_dn_id: Optional[str] = None,
        notes: str = "",
        return_reason: str = "",
        refund_option: str = "Customer credit",
        amount_refunded: float = 0.0,
        refund_account_id: Optional[str] = None,
        restock_items: bool = True,
        attachments: Optional[List[dict]] = None,
        location_id: str = "",
        location_name: str = "",
    ) -> SalesReturn:
        ret_lines = self._sales_return_lines(lines)
        sales_return = SalesReturn(
            return_number=return_number,
            customer_id=customer_id,
            customer_name=customer_name,
            return_date=return_date,
            lines=ret_lines,
            source_invoice_id=source_invoice_id,
            source_invoice_number=source_invoice_number,
            source_dn_id=source_dn_id,
            notes=notes.strip(),
            return_reason=return_reason.strip(),
            refund_option=refund_option,
            amount_refunded=round(float(amount_refunded or 0), 2),
            refund_account_id=refund_account_id,
            status=SalesReturnStatus.PENDING,
            restock_items=bool(restock_items),
            attachments=list(attachments or []),
            location_id=(location_id or "").strip(),
            location_name=(location_name or "").strip(),
        )
        return self._return_repo.save(sales_return)

    def update_sales_return(
        self,
        return_id: str,
        *,
        customer_id: str,
        customer_name: str,
        return_date: date,
        lines: List[dict],
        source_invoice_id: Optional[str] = None,
        source_invoice_number: str = "",
        notes: str = "",
        return_reason: str = "",
        refund_option: str = "Customer credit",
        amount_refunded: float = 0.0,
        refund_account_id: Optional[str] = None,
        restock_items: bool = True,
        attachments: Optional[List[dict]] = None,
        location_id: Optional[str] = None,
        location_name: Optional[str] = None,
    ) -> SalesReturn:
        current = self._return_repo.find_by_id(return_id)
        if not current:
            raise ValidationError("Sales return not found")
        if current.status != SalesReturnStatus.PENDING:
            raise ValidationError("Only pending returns can be edited")
        current.update(
            customer_id=customer_id,
            customer_name=customer_name,
            return_date=return_date,
            lines=self._sales_return_lines(lines),
            source_invoice_id=source_invoice_id,
            source_invoice_number=source_invoice_number,
            notes=notes.strip(),
            return_reason=return_reason.strip(),
            refund_option=refund_option,
            amount_refunded=round(float(amount_refunded or 0), 2),
            refund_account_id=refund_account_id,
            restock_items=bool(restock_items),
            attachments=list(attachments or []),
        )
        current.source_invoice_id = source_invoice_id
        current.refund_account_id = refund_account_id
        if location_id is not None:
            current.location_id = (location_id or "").strip()
        if location_name is not None:
            current.location_name = (location_name or "").strip()
        return self._return_repo.save(current)

    @staticmethod
    def _sales_return_lines(lines: List[dict]) -> List[SalesReturnLine]:
        if not lines:
            raise ValidationError("At least one return line is required")
        result = []
        for raw in lines:
            qty = float(raw.get("qty") or 0)
            if qty <= 0:
                raise ValidationError("Return quantity must be positive")
            result.append(
                SalesReturnLine(
                    product_id=str(raw.get("product_id") or ""),
                    product_name=(raw.get("product_name") or "").strip(),
                    qty=round(qty, 2),
                    rate=round(float(raw.get("rate") or 0), 2),
                )
            )
        return result

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

    def unmark_so_invoiced(self, sales_order_id: str, lines: List[dict]) -> None:
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
                    so_line.qty_invoiced = round(
                        max(so_line.qty_invoiced - qty, 0.0), 2
                    )
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
                "location_id": dn.location_id or None,
            }
            for line in dn.lines
        ]

    @staticmethod
    def _priced_lines(lines: List[dict]) -> List[EstimateLine]:
        if not lines:
            raise ValidationError("At least one line is required")
        result: List[EstimateLine] = []
        for raw in lines:
            qty = float(raw.get("qty") or raw.get("qty_ordered") or 0)
            if qty <= 0:
                raise ValidationError("Quantity must be positive")
            result.append(
                EstimateLine(
                    product_id=str(raw.get("product_id") or ""),
                    product_name=str(raw.get("product_name") or "").strip(),
                    qty=round(qty, 2),
                    rate=round(float(raw.get("rate") or 0), 2),
                    **SalesDomainService._so_line_tax_fields(raw),
                )
            )
        return result

    def create_estimate(
        self,
        *,
        estimate_number: str,
        customer_id: str,
        customer_name: str,
        estimate_date: date,
        lines: List[dict],
        valid_until: Optional[date] = None,
        notes: str = "",
        status: EstimateStatus = EstimateStatus.DRAFT,
        supply_type: str = "",
        document_content: Optional[DocumentContentSnapshot] = None,
        location_id: str = "",
        location_name: str = "",
    ) -> Estimate:
        from vaybooks.bms.domain.shared.party_location import require_location_id

        if not self._estimate_repo:
            raise ValidationError("Estimate repository is not configured")
        if not customer_id:
            raise ValidationError("Customer is required")
        location_id = require_location_id(location_id)
        estimate = Estimate(
            estimate_number=estimate_number,
            customer_id=customer_id,
            customer_name=customer_name,
            estimate_date=estimate_date,
            valid_until=valid_until,
            status=status,
            lines=self._priced_lines(lines),
            notes=notes.strip(),
            supply_type=supply_type,
            location_id=location_id,
            location_name=(location_name or "").strip(),
            document_content=document_content or DocumentContentSnapshot(),
        )
        return self._estimate_repo.save(estimate)

    def update_estimate(self, estimate_id: str, **changes) -> Estimate:
        if not self._estimate_repo:
            raise ValidationError("Estimate repository is not configured")
        estimate = self._estimate_repo.find_by_id(estimate_id)
        if not estimate:
            raise ValidationError("Estimate not found")
        if estimate.status in (
            EstimateStatus.CANCELLED,
            EstimateStatus.EXPIRED,
            EstimateStatus.CONVERTED,
        ):
            raise ValidationError("Cannot edit a cancelled, expired, or converted estimate")
        lines = changes.pop("lines", None)
        if lines is not None:
            changes["lines"] = self._priced_lines(lines)
        estimate.update(**changes)
        return self._estimate_repo.save(estimate)

    def create_quotation(
        self,
        *,
        quotation_number: str,
        customer_id: str,
        customer_name: str,
        quotation_date: date,
        lines: List[dict],
        valid_until: Optional[date] = None,
        notes: str = "",
        status: QuotationStatus = QuotationStatus.DRAFT,
        supply_type: str = "",
        document_content: Optional[DocumentContentSnapshot] = None,
        location_id: str = "",
        location_name: str = "",
    ) -> Quotation:
        from vaybooks.bms.domain.shared.party_location import require_location_id

        if not self._quotation_repo:
            raise ValidationError("Quotation repository is not configured")
        if not customer_id:
            raise ValidationError("Customer is required")
        location_id = require_location_id(location_id)
        quotation = Quotation(
            quotation_number=quotation_number,
            customer_id=customer_id,
            customer_name=customer_name,
            quotation_date=quotation_date,
            valid_until=valid_until,
            status=status,
            lines=self._priced_lines(lines),
            notes=notes.strip(),
            supply_type=supply_type,
            location_id=location_id,
            location_name=(location_name or "").strip(),
            document_content=document_content or DocumentContentSnapshot(),
        )
        return self._quotation_repo.save(quotation)

    def update_quotation(self, quotation_id: str, **changes) -> Quotation:
        if not self._quotation_repo:
            raise ValidationError("Quotation repository is not configured")
        quotation = self._quotation_repo.find_by_id(quotation_id)
        if not quotation:
            raise ValidationError("Quotation not found")
        terminal = (
            QuotationStatus.CONVERTED,
            QuotationStatus.CANCELLED,
            QuotationStatus.EXPIRED,
        )
        if quotation.status in terminal:
            raise ValidationError("Cannot edit this quotation")
        lines = changes.pop("lines", None)
        if lines is not None:
            changes["lines"] = self._priced_lines(lines)
        quotation.update(**changes)
        return self._quotation_repo.save(quotation)
