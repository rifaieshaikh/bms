from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
from typing import List, Optional

from vaybooks.bms.application.accounting_app_service import AccountingAppService
from vaybooks.bms.application.inventory_app_service import InventoryAppService
from vaybooks.bms.domain.accounting.entities import Voucher
from vaybooks.bms.domain.accounting.sales_parsing import (
    sales_amounts_from_lines,
    sales_row_from_voucher,
)
from vaybooks.bms.domain.customers.entities import Customer
from vaybooks.bms.domain.sales.customer_prices import CustomerPriceEntry
from vaybooks.bms.domain.sales.entities import (
    DeliveryNote,
    Estimate,
    Quotation,
    SalesOrder,
    SalesReturn,
)
from vaybooks.bms.domain.sales.line_items import (
    apply_invoice_discount_to_lines,
    parse_sales_line_items_note,
    serialize_sales_line_items,
    tax_summary_from_lines,
)
from vaybooks.bms.domain.sales.repository import (
    DeliveryNoteRepository,
    EstimateRepository,
    QuotationRepository,
    SalesOrderRepository,
    SalesReturnRepository,
)
from vaybooks.bms.domain.sales.sales_line_resolver import (
    SalesLineResolver,
    business_is_registered,
    effective_sales_gst_rate,
)
from vaybooks.bms.domain.sales.services import SalesDomainService
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import (
    DeliveryNoteStatus,
    EstimateStatus,
    QuotationStatus,
    PartyRegistrationType,
    SalesOrderStatus,
    SalesReturnStatus,
    StockReferenceType,
    VoucherType,
)
from vaybooks.bms.domain.shared.document_customization import (
    CustomFieldValue,
    DocumentContentSnapshot,
    dataclass_to_dict,
)
from vaybooks.bms.domain.shared.india import compute_sales_gst
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
        estimate_repo: Optional[EstimateRepository] = None,
        quotation_repo: Optional[QuotationRepository] = None,
        customer_price_repo=None,
    ):
        self._so_repo = so_repo
        self._dn_repo = dn_repo
        self._return_repo = return_repo
        self._counter_repo = counter_repo
        self._accounting = accounting
        self._inventory = inventory
        self._customer_service = customer_service
        self._business_service = business_service
        self._estimate_repo = estimate_repo
        self._quotation_repo = quotation_repo
        self._customer_price_repo = customer_price_repo
        self._domain = SalesDomainService(
            so_repo, dn_repo, return_repo, estimate_repo, quotation_repo
        )

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
        document_content: Optional[DocumentContentSnapshot] = None,
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
            document_content=(
                dataclass_to_dict(document_content) if document_content else None
            ),
        )
        return sales_lines, note, summary["grand_total"]

    @staticmethod
    def _customer_is_registered(customer: Optional[Customer]) -> bool:
        if not customer:
            return False
        if customer.registration_type == PartyRegistrationType.REGISTERED:
            return True
        return bool((customer.gstin or "").strip())

    def _classify_supply_type(self, customer: Optional[Customer]) -> str:
        return "B2B" if self._customer_is_registered(customer) else "B2C"

    def build_document_content(
        self,
        document_type: str,
        custom_values: Optional[dict] = None,
        bank_account_id: Optional[str] = None,
        terms_and_conditions: Optional[str] = None,
        policies=None,
    ) -> DocumentContentSnapshot:
        if not self._business_service:
            return DocumentContentSnapshot()
        profile = self._business_service.get_profile()
        template = profile.document_templates.get(document_type)
        if not template:
            return DocumentContentSnapshot()
        values = custom_values or {}
        custom_fields = []
        for definition in sorted(
            template.custom_fields, key=lambda item: item.display_order
        ):
            value = values.get(definition.key, definition.default_value)
            if definition.required and (value is None or value == ""):
                raise ValueError(f"{definition.label} is required")
            custom_fields.append(
                CustomFieldValue(
                    key=definition.key,
                    label=definition.label,
                    field_type=definition.field_type,
                    value=value,
                    print_visible=definition.print_visible,
                )
            )
        selected_id = (
            bank_account_id
            if bank_account_id is not None
            else template.default_bank_account_id
        )
        account = next(
            (
                item
                for item in profile.bank_accounts
                if item.id == selected_id and item.is_active
            ),
            None,
        )
        return DocumentContentSnapshot(
            custom_fields=custom_fields,
            bank_account=deepcopy(account),
            terms_and_conditions=(
                terms_and_conditions
                if terms_and_conditions is not None
                else template.terms_and_conditions
            ),
            policies=deepcopy(policies if policies is not None else template.policies),
        )

    def _enrich_so_lines(
        self, customer_id: str, lines: list[dict]
    ) -> tuple[list[dict], str]:
        """Default missing rates from the product and snapshot GST per line."""
        customer = (
            self._customer_service.get_customer_detail(customer_id)
            if self._customer_service and customer_id
            else None
        )
        business = (
            self._business_service.get_profile() if self._business_service else None
        )
        registered = business_is_registered(business)
        business_state = business.state_code if business else ""
        customer_state = (customer.state_code if customer else "") or ""
        supply_type = self._classify_supply_type(customer)
        # B2C with no customer state: place of supply is the business's own
        # state (over-the-counter sale), not an inter-state supply.
        if supply_type == "B2C" and not customer_state:
            customer_state = business_state

        enriched: list[dict] = []
        for raw in lines:
            row = dict(raw)
            qty = float(row.get("qty_ordered") or row.get("qty") or 0)
            rate = float(row.get("rate") or 0)
            gst_rate = effective_sales_gst_rate(business, 0.0)
            hsn_sac = ""
            product_id = str(row.get("product_id") or "").strip()
            if product_id:
                product = self._inventory.get_product(product_id)
                if product:
                    if rate == 0:
                        rate = float(getattr(product, "selling_rate", 0) or 0)
                    if not (row.get("product_name") or "").strip():
                        row["product_name"] = product.name
                    tax_profile = product.active_tax_profile()
                    gst_rate = effective_sales_gst_rate(
                        business, tax_profile.gst_rate
                    )
                    hsn_sac = tax_profile.hsn_sac
                    if registered:
                        if rate <= 0:
                            raise ValueError(
                                f"Selling price is required for {product.name}"
                            )
                        if not hsn_sac:
                            raise ValueError(
                                f"HSN/SAC is required for {product.name}"
                            )
                        gst_periods = self._inventory.list_gst_rate_history(product.id)
                        if (
                            business.registration_type
                            == PartyRegistrationType.REGISTERED
                            and not gst_periods
                        ):
                            raise ValueError(
                                f"GST rate configuration is required for "
                                f"{product.name}"
                            )
            taxable = round(qty * rate, 2)
            gst = compute_sales_gst(
                taxable,
                gst_rate,
                business_registered=registered,
                business_state_code=business_state,
                customer_state_code=customer_state,
            )
            row["rate"] = round(rate, 2)
            row["hsn_sac"] = hsn_sac
            row["gst_rate"] = gst_rate if registered else 0.0
            row["taxable_amount"] = gst.taxable_amount
            row["cgst_amount"] = gst.cgst_amount
            row["sgst_amount"] = gst.sgst_amount
            row["igst_amount"] = gst.igst_amount
            row["utgst_amount"] = gst.utgst_amount
            enriched.append(row)
        return enriched, supply_type

    def list_estimates(self) -> List[Estimate]:
        return self._estimate_repo.list_all() if self._estimate_repo else []

    def get_estimate(self, estimate_id: str) -> Optional[Estimate]:
        return self._estimate_repo.find_by_id(estimate_id) if self._estimate_repo else None

    def create_estimate(
        self,
        customer_id: str,
        estimate_date: date,
        lines: list[dict],
        valid_until: Optional[date] = None,
        notes: str = "",
        status: EstimateStatus = EstimateStatus.DRAFT,
        custom_values: Optional[dict] = None,
        bank_account_id: Optional[str] = None,
        terms_and_conditions: Optional[str] = None,
    ) -> Estimate:
        enriched, supply_type = self._enrich_so_lines(customer_id, lines)
        return self._domain.create_estimate(
            estimate_number=self._counter_repo.next("estimate_number"),
            customer_id=customer_id,
            customer_name=self._customer_name(customer_id),
            estimate_date=estimate_date,
            valid_until=valid_until,
            lines=enriched,
            notes=notes,
            status=status,
            supply_type=supply_type,
            document_content=self.build_document_content(
                "estimate",
                custom_values,
                bank_account_id,
                terms_and_conditions,
            ),
        )

    def update_estimate(
        self,
        estimate_id: str,
        *,
        customer_id: str,
        estimate_date: date,
        lines: list[dict],
        valid_until: Optional[date] = None,
        notes: str = "",
        status: Optional[EstimateStatus] = None,
        custom_values: Optional[dict] = None,
        bank_account_id: Optional[str] = None,
        terms_and_conditions: Optional[str] = None,
    ) -> Estimate:
        enriched, supply_type = self._enrich_so_lines(customer_id, lines)
        changes = {
            "customer_id": customer_id,
            "customer_name": self._customer_name(customer_id),
            "estimate_date": estimate_date,
            "valid_until": valid_until,
            "lines": enriched,
            "notes": notes.strip(),
            "supply_type": supply_type,
            "document_content": self.build_document_content(
                "estimate",
                custom_values,
                bank_account_id,
                terms_and_conditions,
            ),
        }
        if status is not None:
            changes["status"] = status
        return self._domain.update_estimate(estimate_id, **changes)

    def list_quotations(self) -> List[Quotation]:
        return self._quotation_repo.list_all() if self._quotation_repo else []

    def get_quotation(self, quotation_id: str) -> Optional[Quotation]:
        return (
            self._quotation_repo.find_by_id(quotation_id)
            if self._quotation_repo
            else None
        )

    def create_quotation(
        self,
        customer_id: str,
        quotation_date: date,
        lines: list[dict],
        valid_until: Optional[date] = None,
        notes: str = "",
        status: QuotationStatus = QuotationStatus.DRAFT,
        custom_values: Optional[dict] = None,
        bank_account_id: Optional[str] = None,
        terms_and_conditions: Optional[str] = None,
    ) -> Quotation:
        enriched, supply_type = self._enrich_so_lines(customer_id, lines)
        return self._domain.create_quotation(
            quotation_number=self._counter_repo.next("quotation_number"),
            customer_id=customer_id,
            customer_name=self._customer_name(customer_id),
            quotation_date=quotation_date,
            valid_until=valid_until,
            lines=enriched,
            notes=notes,
            status=status,
            supply_type=supply_type,
            document_content=self.build_document_content(
                "quotation",
                custom_values,
                bank_account_id,
                terms_and_conditions,
            ),
        )

    def update_quotation(
        self,
        quotation_id: str,
        *,
        customer_id: str,
        quotation_date: date,
        lines: list[dict],
        valid_until: Optional[date] = None,
        notes: str = "",
        status: Optional[QuotationStatus] = None,
        custom_values: Optional[dict] = None,
        bank_account_id: Optional[str] = None,
        terms_and_conditions: Optional[str] = None,
    ) -> Quotation:
        enriched, supply_type = self._enrich_so_lines(customer_id, lines)
        changes = {
            "customer_id": customer_id,
            "customer_name": self._customer_name(customer_id),
            "quotation_date": quotation_date,
            "valid_until": valid_until,
            "lines": enriched,
            "notes": notes.strip(),
            "supply_type": supply_type,
            "document_content": self.build_document_content(
                "quotation",
                custom_values,
                bank_account_id,
                terms_and_conditions,
            ),
        }
        if status is not None:
            changes["status"] = status
        return self._domain.update_quotation(quotation_id, **changes)

    def convert_quotation_to_sales_order(
        self,
        quotation_id: str,
        *,
        order_date: Optional[date] = None,
        expected_date: Optional[date] = None,
    ) -> SalesOrder:
        if not self._quotation_repo:
            raise ValueError("Quotation repository is not configured")
        quotation = self._quotation_repo.find_by_id(quotation_id)
        if not quotation:
            raise ValueError("Quotation not found")
        if quotation.status != QuotationStatus.ACCEPTED:
            raise ValueError("Only an accepted quotation can be converted")
        if quotation.converted_sales_order_id:
            raise ValueError("Quotation is already converted")
        source_values = {
            item.key: item.value for item in quotation.document_content.custom_fields
        }
        order = self.create_sales_order(
            customer_id=quotation.customer_id,
            order_date=order_date or date.today(),
            expected_date=expected_date,
            lines=[
                {
                    "product_id": line.product_id,
                    "product_name": line.product_name,
                    "qty": line.qty,
                    "rate": line.rate,
                }
                for line in quotation.lines
            ],
            notes=quotation.notes,
            status=SalesOrderStatus.CONFIRMED,
        )
        order.document_content = self.build_document_content(
            "sales_order", custom_values=source_values
        )
        self._so_repo.save(order)
        quotation.converted_sales_order_id = order.id
        quotation.status = QuotationStatus.CONVERTED
        self._quotation_repo.save(quotation)
        return order

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
        custom_values: Optional[dict] = None,
        bank_account_id: Optional[str] = None,
        terms_and_conditions: Optional[str] = None,
    ) -> SalesOrder:
        enriched, supply_type = self._enrich_so_lines(customer_id, lines)
        so_number = self._counter_repo.next("so_number")
        order = self._domain.create_sales_order(
            so_number=so_number,
            customer_id=customer_id,
            customer_name=self._customer_name(customer_id),
            order_date=order_date,
            lines=enriched,
            expected_date=expected_date,
            notes=notes,
            status=status,
            supply_type=supply_type,
        )
        order.document_content = self.build_document_content(
            "sales_order",
            custom_values,
            bank_account_id,
            terms_and_conditions,
        )
        return self._so_repo.save(order)

    def update_sales_order(
        self,
        order_id: str,
        customer_id: str,
        order_date: date,
        lines: list[dict],
        expected_date: Optional[date] = None,
        notes: str = "",
        status: Optional[SalesOrderStatus] = None,
        custom_values: Optional[dict] = None,
        bank_account_id: Optional[str] = None,
        terms_and_conditions: Optional[str] = None,
    ) -> SalesOrder:
        enriched, supply_type = self._enrich_so_lines(customer_id, lines)
        order = self._domain.update_sales_order(
            order_id,
            customer_id,
            self._customer_name(customer_id),
            order_date,
            enriched,
            expected_date,
            notes,
            status,
            supply_type=supply_type,
        )
        order.document_content = self.build_document_content(
            "sales_order",
            custom_values,
            bank_account_id,
            terms_and_conditions,
        )
        return self._so_repo.save(order)

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
        custom_values: Optional[dict] = None,
        terms_and_conditions: Optional[str] = None,
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
        dn.document_content = self.build_document_content(
            "delivery_note",
            custom_values=custom_values,
            terms_and_conditions=terms_and_conditions,
        )
        self._dn_repo.save(dn)
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

    def update_delivery_note(
        self,
        dn_id: str,
        *,
        delivery_date: date,
        lines: list[dict],
        notes: str = "",
        custom_values: Optional[dict] = None,
        terms_and_conditions: Optional[str] = None,
    ) -> DeliveryNote:
        return self._domain.update_delivery_note(
            dn_id,
            delivery_date=delivery_date,
            lines=lines,
            notes=notes,
            document_content=self.build_document_content(
                "delivery_note",
                custom_values=custom_values,
                terms_and_conditions=terms_and_conditions,
            ),
        )

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
        document_content: Optional[DocumentContentSnapshot] = None,
    ) -> Voucher:
        sales_lines = None
        note = line_items_note
        if document_content is None:
            document_content = self.build_document_content("sales_invoice")
        if line_items:
            sales_lines, note, grand_total = self._prepare_sales_invoice(
                customer_account_id,
                line_items,
                invoice_discount=invoice_discount,
                document_content=document_content,
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
        if line_items:
            self._record_customer_prices_from_invoice(
                customer_account_id=customer_account_id,
                voucher_id=voucher.id,
                store_invoice_number=store_invoice_number,
                voucher_date=voucher.voucher_date,
                line_items=line_items,
            )
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

    def convert_sales_order_to_invoice(
        self,
        sales_order_id: str,
        *,
        store_account_id: str,
        store_invoice_number: str,
        amount_received: float = 0.0,
        voucher_date: Optional[date] = None,
        invoice_discount: float = 0.0,
        custom_values: Optional[dict] = None,
        bank_account_id: Optional[str] = None,
        terms_and_conditions: Optional[str] = None,
    ) -> Voucher:
        order = self._so_repo.find_by_id(sales_order_id)
        if not order:
            raise ValueError("Sales order not found")
        if order.status in (SalesOrderStatus.CANCELLED, SalesOrderStatus.CLOSED):
            raise ValueError("Cannot invoice a cancelled or closed sales order")
        if any(line.qty_delivered > 0 for line in order.lines):
            raise ValueError(
                "This order has delivery activity; create the invoice from its Delivery Note"
            )
        raw_lines = []
        for line in order.lines:
            remaining = round(line.qty_ordered - line.qty_invoiced, 2)
            if remaining > 0:
                raw_lines.append(
                    {
                        "product_id": line.product_id,
                        "description": line.product_name,
                        "qty": remaining,
                        "rate": line.rate,
                    }
                )
        if not raw_lines:
            raise ValueError("Sales order is already fully invoiced")
        customer_account = self._accounting.get_customer_account(order.customer_id)
        if not customer_account:
            raise ValueError("Customer account not found")
        source_values = {
            item.key: item.value for item in order.document_content.custom_fields
        }
        source_values.update(custom_values or {})
        content = self.build_document_content(
            "sales_invoice",
            source_values,
            bank_account_id,
            terms_and_conditions,
        )
        return self.create_sales_invoice(
            customer_account_id=customer_account.id,
            store_account_id=store_account_id,
            gross_amount=order.total_amount,
            discount_amount=invoice_discount,
            amount_received=amount_received,
            store_invoice_number=store_invoice_number,
            voucher_date=voucher_date or order.order_date,
            reference_so_id=order.id,
            line_items=raw_lines,
            invoice_discount=invoice_discount,
            document_content=content,
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
        source_values = {
            item.key: item.value for item in dn.document_content.custom_fields
        }
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
            document_content=self.build_document_content(
                "sales_invoice", custom_values=source_values
            ),
        )

    def list_sales_returns(self) -> List[SalesReturn]:
        return self._return_repo.list_all()

    def get_sales_return(self, return_id: str) -> Optional[SalesReturn]:
        return self._return_repo.find_by_id(return_id)

    def reserve_sales_return_number(self) -> str:
        """Reserve a visible return number for a new-return form."""
        return self._counter_repo.next("sales_return_number")

    def create_sales_return(
        self,
        customer_id: str,
        return_date: date,
        lines: list[dict],
        return_number: Optional[str] = None,
        source_invoice_id: Optional[str] = None,
        source_dn_id: Optional[str] = None,
        amount_refunded: float = 0.0,
        refund_account_id: Optional[str] = None,
        notes: str = "",
        return_reason: str = "",
        refund_option: str = "Customer credit",
        restock_items: bool = True,
        attachments: Optional[list[dict]] = None,
    ) -> SalesReturn:
        customer_account = self._accounting.get_customer_account(customer_id)
        if not customer_account:
            raise ValueError("Customer account not found")
        source_invoice = None
        source_invoice_number = ""
        if source_invoice_id:
            if any(
                prior.source_invoice_id == source_invoice_id
                and prior.status != SalesReturnStatus.REJECTED
                for prior in self._return_repo.list_all()
            ):
                raise ValueError(
                    "A sales return already exists for this invoice"
                )
            source_invoice = self._accounting.get_voucher(source_invoice_id)
            if (
                not source_invoice
                or source_invoice.voucher_type != VoucherType.SALES_INVOICE
            ):
                raise ValueError("Source sales invoice not found")
            source_customer_account_id = sales_amounts_from_lines(
                source_invoice.lines
            ).get("customer_account_id")
            if source_customer_account_id != customer_account.id:
                raise ValueError("Original invoice does not belong to this customer")
            source_row = self.get_sales_invoice(source_invoice_id) or {}
            source_invoice_number = (
                source_row.get("store_invoice_number")
                or source_row.get("voucher_number")
                or ""
            )
            invoice_items, _, _ = parse_sales_line_items_note(
                source_invoice.description
            )
            invoiced_by_product: dict[str, float] = {}
            for item in invoice_items:
                product_id = str(item.get("product_id") or "")
                invoiced_by_product[product_id] = round(
                    invoiced_by_product.get(product_id, 0.0)
                    + float(item.get("qty") or 0),
                    2,
                )
            already_returned: dict[str, float] = {}
            for prior in self._return_repo.list_all():
                if (
                    prior.source_invoice_id != source_invoice_id
                    or prior.status == SalesReturnStatus.REJECTED
                ):
                    continue
                for line in prior.lines:
                    already_returned[line.product_id] = round(
                        already_returned.get(line.product_id, 0.0) + line.qty, 2
                    )
            for raw in lines:
                product_id = str(raw.get("product_id") or "")
                qty = float(raw.get("qty") or 0)
                remaining = round(
                    invoiced_by_product.get(product_id, 0.0)
                    - already_returned.get(product_id, 0.0),
                    2,
                )
                if qty > remaining + 0.001:
                    raise ValueError(
                        f"Return quantity exceeds invoiced quantity for {product_id}"
                    )
        if return_number:
            if any(
                item.return_number == return_number
                for item in self._return_repo.list_all()
            ):
                raise ValueError("Return number already exists")
        else:
            return_number = self.reserve_sales_return_number()
        sales_return = self._domain.create_sales_return(
            return_number=return_number,
            customer_id=customer_id,
            customer_name=self._customer_name(customer_id),
            return_date=return_date,
            lines=lines,
            source_invoice_id=source_invoice_id,
            source_invoice_number=source_invoice_number,
            source_dn_id=source_dn_id,
            notes=notes,
            return_reason=return_reason,
            refund_option=refund_option,
            amount_refunded=amount_refunded,
            refund_account_id=refund_account_id,
            restock_items=restock_items,
            attachments=attachments,
        )
        return sales_return

    def _process_sales_return_refund(
        self,
        sales_return: SalesReturn,
        *,
        source_invoice=None,
    ) -> SalesReturn:
        if sales_return.voucher_id:
            sales_return.status = SalesReturnStatus.REFUND_PROCESSED
            sales_return.refund_processed_at = utc_now()
            self._return_repo.save(sales_return)
            return sales_return
        customer_account = self._accounting.get_customer_account(
            sales_return.customer_id
        )
        if not customer_account:
            raise ValueError("Customer account not found")
        if source_invoice is None and sales_return.source_invoice_id:
            source_invoice = self._accounting.get_voucher(
                sales_return.source_invoice_id
            )
        return_amount = sales_return.total_amount
        description = f"Sales return {sales_return.return_number}"
        detail = sales_return.return_reason or sales_return.notes
        if detail.strip():
            description = f"{description} — {detail.strip()}"
        voucher = self._accounting.create_sales_return_voucher(
            customer_account_id=customer_account.id,
            return_amount=return_amount,
            description=description,
            amount_refunded=sales_return.amount_refunded,
            refund_account_id=sales_return.refund_account_id,
            voucher_date=sales_return.return_date,
            reference_dn_id=sales_return.source_dn_id,
            source_invoice_id=sales_return.source_invoice_id,
        )
        sales_return.voucher_id = voucher.id
        sales_return.status = SalesReturnStatus.REFUND_PROCESSED
        sales_return.refund_processed_at = utc_now()
        self._return_repo.save(sales_return)
        if source_invoice and source_invoice.reference_so_id:
            self._domain.unmark_so_invoiced(
                source_invoice.reference_so_id,
                [
                    {"product_id": line.product_id, "qty": line.qty}
                    for line in sales_return.lines
                ],
            )
        return sales_return

    def approve_sales_return(self, return_id: str) -> SalesReturn:
        sales_return = self.get_sales_return(return_id)
        if not sales_return:
            raise ValueError("Sales return not found")
        if sales_return.status != SalesReturnStatus.PENDING:
            raise ValueError("Only pending returns can be approved")
        sales_return.status = SalesReturnStatus.APPROVED
        sales_return.approved_at = utc_now()
        return self._return_repo.save(sales_return)

    def reject_sales_return(self, return_id: str) -> SalesReturn:
        sales_return = self.get_sales_return(return_id)
        if not sales_return:
            raise ValueError("Sales return not found")
        if sales_return.status != SalesReturnStatus.PENDING:
            raise ValueError("Only pending returns can be rejected")
        sales_return.status = SalesReturnStatus.REJECTED
        sales_return.rejected_at = utc_now()
        return self._return_repo.save(sales_return)

    def mark_sales_return_goods_received(self, return_id: str) -> SalesReturn:
        sales_return = self.get_sales_return(return_id)
        if not sales_return:
            raise ValueError("Sales return not found")
        if sales_return.status != SalesReturnStatus.APPROVED:
            raise ValueError("Only approved returns can be marked goods received")
        # Legacy approved returns already have a voucher and were restocked by
        # the previous workflow. Do not apply their inventory movement twice.
        if sales_return.restock_items and not sales_return.voucher_id:
            stock_lines = [
                {
                    "product_id": line.product_id,
                    "qty": line.qty,
                    "description": line.product_name or "Return",
                }
                for line in sales_return.lines
            ]
            self._inventory.apply_sales_return(
                sales_return.id, stock_lines, sales_return.return_date
            )
        sales_return.status = SalesReturnStatus.GOODS_RECEIVED
        sales_return.goods_received_at = utc_now()
        return self._return_repo.save(sales_return)

    def process_sales_return_refund(self, return_id: str) -> SalesReturn:
        sales_return = self.get_sales_return(return_id)
        if not sales_return:
            raise ValueError("Sales return not found")
        if sales_return.status != SalesReturnStatus.GOODS_RECEIVED:
            raise ValueError(
                "Refund can only be processed after goods are received"
            )
        return self._process_sales_return_refund(sales_return)

    def close_sales_return(self, return_id: str) -> SalesReturn:
        sales_return = self.get_sales_return(return_id)
        if not sales_return:
            raise ValueError("Sales return not found")
        if sales_return.status != SalesReturnStatus.REFUND_PROCESSED:
            raise ValueError("Only refund-processed returns can be closed")
        sales_return.status = SalesReturnStatus.CLOSED
        sales_return.closed_at = utc_now()
        return self._return_repo.save(sales_return)

    def update_sales_return(
        self,
        return_id: str,
        *,
        customer_id: str,
        return_date: date,
        lines: list[dict],
        source_invoice_id: Optional[str] = None,
        notes: str = "",
        return_reason: str = "",
        refund_option: str = "Customer credit",
        amount_refunded: float = 0.0,
        refund_account_id: Optional[str] = None,
        restock_items: bool = True,
        attachments: Optional[list[dict]] = None,
    ) -> SalesReturn:
        customer_account = self._accounting.get_customer_account(customer_id)
        if not customer_account:
            raise ValueError("Customer account not found")
        source_invoice_number = ""
        if source_invoice_id:
            if any(
                prior.id != return_id
                and prior.source_invoice_id == source_invoice_id
                and prior.status != SalesReturnStatus.REJECTED
                for prior in self._return_repo.list_all()
            ):
                raise ValueError(
                    "A sales return already exists for this invoice"
                )
            source_invoice = self._accounting.get_voucher(source_invoice_id)
            if (
                not source_invoice
                or source_invoice.voucher_type != VoucherType.SALES_INVOICE
            ):
                raise ValueError("Source sales invoice not found")
            source_customer_account_id = sales_amounts_from_lines(
                source_invoice.lines
            ).get("customer_account_id")
            if source_customer_account_id != customer_account.id:
                raise ValueError("Original invoice does not belong to this customer")
            source_row = self.get_sales_invoice(source_invoice_id) or {}
            source_invoice_number = (
                source_row.get("store_invoice_number")
                or source_row.get("voucher_number")
                or ""
            )
            invoice_items, _, _ = parse_sales_line_items_note(
                source_invoice.description
            )
            invoiced_by_product: dict[str, float] = {}
            for item in invoice_items:
                product_id = str(item.get("product_id") or "")
                invoiced_by_product[product_id] = round(
                    invoiced_by_product.get(product_id, 0.0)
                    + float(item.get("qty") or 0),
                    2,
                )
            already_returned: dict[str, float] = {}
            for prior in self._return_repo.list_all():
                if (
                    prior.id == return_id
                    or prior.source_invoice_id != source_invoice_id
                    or prior.status == SalesReturnStatus.REJECTED
                ):
                    continue
                for line in prior.lines:
                    already_returned[line.product_id] = round(
                        already_returned.get(line.product_id, 0.0) + line.qty, 2
                    )
            for raw in lines:
                product_id = str(raw.get("product_id") or "")
                remaining = round(
                    invoiced_by_product.get(product_id, 0.0)
                    - already_returned.get(product_id, 0.0),
                    2,
                )
                if float(raw.get("qty") or 0) > remaining + 0.001:
                    raise ValueError(
                        f"Return quantity exceeds invoiced quantity for {product_id}"
                    )
        return self._domain.update_sales_return(
            return_id,
            customer_id=customer_id,
            customer_name=self._customer_name(customer_id),
            return_date=return_date,
            lines=lines,
            source_invoice_id=source_invoice_id,
            source_invoice_number=source_invoice_number,
            notes=notes,
            return_reason=return_reason,
            refund_option=refund_option,
            amount_refunded=amount_refunded,
            refund_account_id=refund_account_id,
            restock_items=restock_items,
            attachments=attachments,
        )

    def update_sales_return_details(
        self,
        return_id: str,
        *,
        return_reason: str,
        notes: str = "",
        attachments: Optional[list[dict]] = None,
    ) -> SalesReturn:
        """Update non-financial fields without changing posted accounting or stock."""
        sales_return = self.get_sales_return(return_id)
        if not sales_return:
            raise ValueError("Sales return not found")
        if sales_return.status != SalesReturnStatus.PENDING:
            raise ValueError("Only pending returns can be edited")
        if not return_reason.strip():
            raise ValueError("Return reason is required")
        sales_return.update(
            return_reason=return_reason.strip(),
            notes=notes.strip(),
            attachments=list(attachments or []),
        )
        return self._return_repo.save(sales_return)

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

    def update_sales_invoice(
        self,
        voucher_id: str,
        *,
        customer_account_id: str,
        store_account_id: str,
        store_invoice_number: str,
        line_items: list[dict],
        amount_received: float,
        voucher_date: date,
        invoice_discount: float = 0.0,
        custom_values: Optional[dict] = None,
        bank_account_id: Optional[str] = None,
        terms_and_conditions: Optional[str] = None,
    ) -> Voucher:
        old = self._accounting.get_voucher(voucher_id)
        if not old or old.voucher_type != VoucherType.SALES_INVOICE:
            raise ValueError("Sales invoice not found")
        old_items, _, _ = parse_sales_line_items_note(old.description)
        if old.reference_dn_id:
            dn = self._dn_repo.find_by_id(old.reference_dn_id)
            expected = {
                line.product_id: round(line.qty_delivered, 2) for line in dn.lines
            } if dn else {}
            proposed = {
                str(line.get("product_id") or ""): round(
                    float(line.get("qty") or 0), 2
                )
                for line in line_items
            }
            if proposed != expected:
                raise ValueError(
                    "Items and quantities on a Delivery Note-linked invoice cannot change"
                )
        content = self.build_document_content(
            "sales_invoice",
            custom_values,
            bank_account_id,
            terms_and_conditions,
        )
        sales_lines, note, grand_total = self._prepare_sales_invoice(
            customer_account_id,
            line_items,
            invoice_discount=invoice_discount,
            document_content=content,
        )
        if old.reference_so_id:
            order = self._so_repo.find_by_id(old.reference_so_id)
            if order:
                old_by_product = {
                    str(item.get("product_id") or ""): float(item.get("qty") or 0)
                    for item in old_items
                }
                for raw in line_items:
                    product_id = str(raw.get("product_id") or "")
                    proposed_qty = float(raw.get("qty") or 0)
                    so_line = next(
                        (item for item in order.lines if item.product_id == product_id),
                        None,
                    )
                    if not so_line:
                        raise ValueError("Invoice product is not on the Sales Order")
                    available = (
                        so_line.qty_ordered
                        - so_line.qty_invoiced
                        + old_by_product.get(product_id, 0.0)
                    )
                    if proposed_qty > available + 0.001:
                        raise ValueError(
                            f"Invoice quantity exceeds Sales Order quantity for {product_id}"
                        )
        voucher = self._accounting.update_cash_sales_invoice(
            voucher_id=voucher_id,
            customer_account_id=customer_account_id,
            store_account_id=store_account_id,
            gross_amount=grand_total,
            discount_amount=0.0,
            amount_received=min(amount_received, grand_total),
            store_invoice_number=store_invoice_number,
            line_items_note=note,
            voucher_date=voucher_date,
            sales_lines=sales_lines,
            allow_erp_linked=True,
        )
        if not old.reference_dn_id:
            self._inventory.reverse_movements_by_reference(voucher_id)
            self._inventory.apply_sales_movements(voucher_id, line_items, voucher_date)
        if old.reference_so_id:
            self._domain.unmark_so_invoiced(old.reference_so_id, old_items)
            self._domain.mark_so_invoiced(old.reference_so_id, line_items)
        self._record_customer_prices_from_invoice(
            customer_account_id=customer_account_id,
            voucher_id=voucher.id,
            store_invoice_number=store_invoice_number,
            voucher_date=voucher.voucher_date,
            line_items=line_items,
            replace_voucher=True,
        )
        return voucher

    def delete_sales_invoice(self, voucher_id: str) -> None:
        old = self._accounting.get_voucher(voucher_id)
        if not old or old.voucher_type != VoucherType.SALES_INVOICE:
            raise ValueError("Sales invoice not found")
        if old.reference_dn_id:
            raise ValueError("Cannot delete a delivery-linked sales invoice")
        items, _, _ = parse_sales_line_items_note(old.description)
        if not old.reference_dn_id:
            self._inventory.reverse_movements_by_reference(voucher_id)
        self._accounting.void_voucher(voucher_id)
        if old.reference_so_id:
            self._domain.unmark_so_invoiced(old.reference_so_id, items)
        if self._customer_price_repo:
            self._customer_price_repo.delete_by_voucher(voucher_id)

    def get_customer_rate(
        self, customer_id: str, product_id: str
    ) -> Optional[float]:
        if not self._customer_price_repo or not customer_id or not product_id:
            return None
        latest = self._customer_price_repo.latest(customer_id, product_id)
        if latest is None:
            return None
        return float(latest.rate)

    def list_customer_prices(self, *, limit: int = 500):
        if not self._customer_price_repo:
            return []
        return self._customer_price_repo.list_all(limit=limit)

    def list_customer_price_history(
        self, customer_id: str, product_id: str, *, limit: int = 50
    ):
        if not self._customer_price_repo:
            return []
        return self._customer_price_repo.list_for_pair(
            customer_id, product_id, limit=limit
        )

    def _record_customer_prices_from_invoice(
        self,
        *,
        customer_account_id: str,
        voucher_id: str,
        store_invoice_number: str,
        voucher_date: date,
        line_items: list[dict],
        replace_voucher: bool = False,
    ) -> None:
        if not self._customer_price_repo or not line_items:
            return
        if replace_voucher:
            self._customer_price_repo.delete_by_voucher(voucher_id)
        try:
            customer = self._customer_from_account(customer_account_id)
        except Exception:
            return
        effective = voucher_date
        if isinstance(effective, datetime):
            effective = effective.date()
        elif not isinstance(effective, date):
            effective = date.today()
        seen_products: set[str] = set()
        for raw in line_items:
            product_id = str(raw.get("product_id") or "").strip()
            if not product_id or product_id in seen_products:
                continue
            seen_products.add(product_id)
            rate = round(float(raw.get("rate") or 0), 2)
            if rate <= 0:
                continue
            latest = self._customer_price_repo.latest(customer.id, product_id)
            if latest is not None and round(float(latest.rate), 2) == rate:
                continue
            product = self._inventory.get_product(product_id)
            sku = ""
            product_name = str(raw.get("product_name") or "")
            if product is not None:
                sku = getattr(product, "sku", "") or ""
                product_name = getattr(product, "name", "") or product_name
            self._customer_price_repo.save(
                CustomerPriceEntry(
                    customer_id=customer.id,
                    customer_name=customer.customer_name or "",
                    product_id=product_id,
                    sku=sku,
                    product_name=product_name,
                    rate=rate,
                    voucher_id=voucher_id,
                    store_invoice_number=store_invoice_number or "",
                    effective_date=effective,
                )
            )

    def _customer_name(self, customer_id: str) -> str:
        if not self._customer_service or not customer_id:
            return ""
        customer = self._customer_service.get_customer_detail(customer_id)
        return customer.customer_name if customer else ""
