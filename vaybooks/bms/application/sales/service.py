from __future__ import annotations

import logging
from copy import deepcopy
from datetime import date, datetime
from typing import List, Optional

from vaybooks.bms.application.finance.accounting.service import AccountingAppService
from vaybooks.bms.application.inventory.service import InventoryAppService
from vaybooks.bms.domain.finance.accounting.entities import Voucher
from vaybooks.bms.domain.finance.accounting.sales_parsing import (
    sales_amounts_from_lines,
)
from vaybooks.bms.domain.parties.customers.entities import Customer
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
from vaybooks.bms.domain.shared.financial_year import (
    format_invoice_number,
    peek_invoice_number,
    resolve_financial_year,
)
from vaybooks.bms.domain.shared.enums import (
    DeliveryChargePaymentStatus,
    DeliveryNoteStatus,
    DeliveryReferenceType,
    EstimateStatus,
    InvoiceDeliveryStatus,
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
from vaybooks.bms.infrastructure.repositories.finance.mongo_counter_repository import (
    MongoCounterRepository,
)

logger = logging.getLogger(__name__)


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
        crm_event_sink=None,
        commission_service=None,
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
        self._crm_event_sink = crm_event_sink
        self._commission_service = commission_service
        self._domain = SalesDomainService(
            so_repo, dn_repo, return_repo, estimate_repo, quotation_repo
        )

    def _emit_crm_event(self, event_type: str, **payload) -> None:
        """Publish a source-linked CRM event without breaking the sales posting.

        The CRM sink enforces idempotency by source type/id/event type. Keeping
        this boundary optional preserves backwards compatibility for tests and
        installations where the CRM module has not been bootstrapped yet.
        """
        sink = self._crm_event_sink
        if sink is None:
            return
        try:
            if callable(sink):
                sink(event_type, payload)
            else:
                sink.record_source_event(event_type=event_type, **payload)
        except Exception:
            logger.exception(
                "CRM event publication failed: %s source=%s",
                event_type,
                payload.get("source_id", ""),
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
        commission: Optional[dict] = None,
        commission_tags: Optional[dict] = None,
    ) -> tuple[list[dict], str, float, Optional[dict]]:
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
        tags = commission_tags
        if not tags and commission:
            agent_id = str(commission.get("agent_id") or "").strip()
            if agent_id:
                tags = {
                    "commission_agent_ids": [agent_id],
                    "sales_rep_ids": list(commission.get("sales_rep_ids") or []),
                }
        note = serialize_sales_line_items(
            sales_lines,
            invoice_discount=invoice_discount,
            tax_summary=summary,
            document_content=(
                dataclass_to_dict(document_content) if document_content else None
            ),
            commission_tags=tags,
        )
        return sales_lines, note, summary["grand_total"], tags

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
            mode = (row.get("discount_mode") or "flat").strip() or "flat"
            if "discount_input" in row:
                disc_input = float(row.get("discount_input") or 0)
            else:
                disc_input = float(row.get("discount") or 0)
            if mode in {"percent", "%", "pct"}:
                line_discount = round(
                    taxable * min(max(disc_input, 0.0), 100.0) / 100.0, 2
                )
            else:
                line_discount = round(min(max(disc_input, 0.0), taxable), 2)
            taxable = round(max(taxable - line_discount, 0.0), 2)
            gst = compute_sales_gst(
                taxable,
                gst_rate,
                business_registered=registered,
                business_state_code=business_state,
                customer_state_code=customer_state,
            )
            row["rate"] = round(rate, 2)
            row["discount"] = line_discount
            row["discount_mode"] = "percent" if mode in {"percent", "%", "pct"} else "flat"
            row["discount_input"] = round(disc_input, 2)
            row["hsn_sac"] = hsn_sac
            row["gst_rate"] = gst_rate if registered else 0.0
            row["taxable_amount"] = gst.taxable_amount
            row["cgst_amount"] = gst.cgst_amount
            row["sgst_amount"] = gst.sgst_amount
            row["igst_amount"] = gst.igst_amount
            row["utgst_amount"] = gst.utgst_amount
            enriched.append(row)
        return enriched, supply_type

    def list_estimates(self, *, location_filter: dict | None = None) -> List[Estimate]:
        if not self._estimate_repo:
            return []
        return self._estimate_repo.list_all(location_filter=location_filter)

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
        location_id: str = "",
    ) -> Estimate:
        enriched, supply_type = self._enrich_so_lines(customer_id, lines)
        location_name = self._location_name(location_id)
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
            location_id=location_id,
            location_name=location_name,
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

    def list_quotations(self, *, location_filter: dict | None = None) -> List[Quotation]:
        if not self._quotation_repo:
            return []
        return self._quotation_repo.list_all(location_filter=location_filter)

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
        location_id: str = "",
    ) -> Quotation:
        enriched, supply_type = self._enrich_so_lines(customer_id, lines)
        location_name = self._location_name(location_id)
        quotation = self._domain.create_quotation(
            quotation_number=self._counter_repo.next("quotation_number"),
            customer_id=customer_id,
            customer_name=self._customer_name(customer_id),
            quotation_date=quotation_date,
            valid_until=valid_until,
            lines=enriched,
            notes=notes,
            status=status,
            supply_type=supply_type,
            location_id=location_id,
            location_name=location_name,
            document_content=self.build_document_content(
                "quotation",
                custom_values,
                bank_account_id,
                terms_and_conditions,
            ),
        )
        self._emit_crm_event(
            "quotation_created",
            source_module="sales",
            source_type="quotation",
            source_id=quotation.id,
            customer_id=quotation.customer_id,
            occurred_at=quotation.created_at,
            status=quotation.status.value,
        )
        return quotation

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
        quotation = self._domain.update_quotation(quotation_id, **changes)
        if status in (QuotationStatus.SENT, QuotationStatus.ACCEPTED):
            self._emit_crm_event(
                "quotation_sent"
                if status == QuotationStatus.SENT
                else "quotation_confirmed",
                source_module="sales",
                source_type="quotation",
                source_id=quotation.id,
                customer_id=quotation.customer_id,
                occurred_at=quotation.updated_at,
                status=quotation.status.value,
            )
        return quotation

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

    def set_estimate_status(
        self, estimate_id: str, status: EstimateStatus
    ) -> Estimate:
        if not self._estimate_repo:
            raise ValueError("Estimate repository is not configured")
        estimate = self._estimate_repo.find_by_id(estimate_id)
        if not estimate:
            raise ValueError("Estimate not found")
        if estimate.status in (
            EstimateStatus.CANCELLED,
            EstimateStatus.EXPIRED,
            EstimateStatus.CONVERTED,
        ):
            raise ValueError(
                "Cannot change status of a cancelled, expired, or converted estimate"
            )
        if status == EstimateStatus.CONVERTED:
            raise ValueError(
                "Use Convert to Sales Order or Convert to Sales Invoice"
            )
        estimate.status = status
        estimate.updated_at = utc_now()
        return self._estimate_repo.save(estimate)

    def set_quotation_status(
        self, quotation_id: str, status: QuotationStatus
    ) -> Quotation:
        if not self._quotation_repo:
            raise ValueError("Quotation repository is not configured")
        quotation = self._quotation_repo.find_by_id(quotation_id)
        if not quotation:
            raise ValueError("Quotation not found")
        if quotation.status in (
            QuotationStatus.CANCELLED,
            QuotationStatus.EXPIRED,
            QuotationStatus.CONVERTED,
        ):
            raise ValueError(
                "Cannot change status of a cancelled, expired, or converted quotation"
            )
        if status == QuotationStatus.CONVERTED:
            raise ValueError("Use Convert to Sales Order")
        quotation.status = status
        quotation.updated_at = utc_now()
        saved = self._quotation_repo.save(quotation)
        if status in (QuotationStatus.SENT, QuotationStatus.ACCEPTED):
            self._emit_crm_event(
                "quotation_sent"
                if status == QuotationStatus.SENT
                else "quotation_confirmed",
                source_module="sales",
                source_type="quotation",
                source_id=saved.id,
                customer_id=saved.customer_id,
                occurred_at=saved.updated_at,
                status=saved.status.value,
            )
        return saved

    def convert_estimate_to_sales_order(
        self,
        estimate_id: str,
        *,
        order_date: Optional[date] = None,
        expected_date: Optional[date] = None,
    ) -> SalesOrder:
        if not self._estimate_repo:
            raise ValueError("Estimate repository is not configured")
        estimate = self._estimate_repo.find_by_id(estimate_id)
        if not estimate:
            raise ValueError("Estimate not found")
        if estimate.status != EstimateStatus.ACCEPTED:
            raise ValueError("Only an accepted estimate can be converted")
        if estimate.converted_sales_order_id or estimate.converted_invoice_id:
            raise ValueError("Estimate is already converted")
        source_values = {
            item.key: item.value for item in estimate.document_content.custom_fields
        }
        order = self.create_sales_order(
            customer_id=estimate.customer_id,
            order_date=order_date or date.today(),
            expected_date=expected_date,
            lines=[
                {
                    "product_id": line.product_id,
                    "product_name": line.product_name,
                    "qty": line.qty,
                    "rate": line.rate,
                }
                for line in estimate.lines
            ],
            notes=estimate.notes,
            status=SalesOrderStatus.CONFIRMED,
        )
        order.document_content = self.build_document_content(
            "sales_order", custom_values=source_values
        )
        self._so_repo.save(order)
        estimate.converted_sales_order_id = order.id
        estimate.status = EstimateStatus.CONVERTED
        self._estimate_repo.save(estimate)
        return order

    def convert_estimate_to_invoice(
        self,
        estimate_id: str,
        *,
        store_account_id: str,
        store_invoice_number: str,
        amount_received: float = 0.0,
        voucher_date: Optional[date] = None,
    ) -> Voucher:
        if not self._estimate_repo:
            raise ValueError("Estimate repository is not configured")
        estimate = self._estimate_repo.find_by_id(estimate_id)
        if not estimate:
            raise ValueError("Estimate not found")
        if estimate.status != EstimateStatus.ACCEPTED:
            raise ValueError("Only an accepted estimate can be converted")
        if estimate.converted_sales_order_id or estimate.converted_invoice_id:
            raise ValueError("Estimate is already converted")
        if not estimate.lines:
            raise ValueError("Estimate has no line items")
        customer_account = self._accounting.get_customer_account(estimate.customer_id)
        if not customer_account:
            raise ValueError("Customer account not found")
        source_values = {
            item.key: item.value for item in estimate.document_content.custom_fields
        }
        content = self.build_document_content(
            "sales_invoice", custom_values=source_values
        )
        raw_lines = [
            {
                "product_id": line.product_id,
                "description": line.product_name,
                "qty": line.qty,
                "rate": line.rate,
            }
            for line in estimate.lines
        ]
        voucher = self.create_sales_invoice(
            customer_account_id=customer_account.id,
            store_account_id=store_account_id,
            gross_amount=estimate.total_amount,
            discount_amount=0.0,
            amount_received=amount_received,
            store_invoice_number=store_invoice_number,
            voucher_date=voucher_date or estimate.estimate_date,
            line_items=raw_lines,
            document_content=content,
        )
        estimate.converted_invoice_id = voucher.id
        estimate.status = EstimateStatus.CONVERTED
        self._estimate_repo.save(estimate)
        return voucher

    def list_sales_orders(self, *, location_filter: dict | None = None) -> List[SalesOrder]:
        return self._so_repo.list_all(location_filter=location_filter)

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
        location_id: str = "",
        commission_agent_ids: Optional[list] = None,
        sales_rep_ids: Optional[list] = None,
    ) -> SalesOrder:
        enriched, supply_type = self._enrich_so_lines(customer_id, lines)
        so_number = self._counter_repo.next("so_number")
        location_name = self._location_name(location_id)
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
            location_id=location_id,
            location_name=location_name,
        )
        order.commission_agent_ids = [
            str(i).strip() for i in (commission_agent_ids or []) if str(i).strip()
        ]
        order.sales_rep_ids = [
            str(i).strip() for i in (sales_rep_ids or []) if str(i).strip()
        ]
        order.document_content = self.build_document_content(
            "sales_order",
            custom_values,
            bank_account_id,
            terms_and_conditions,
        )
        order = self._so_repo.save(order)
        if order.status == SalesOrderStatus.CONFIRMED:
            self._emit_crm_event(
                "order_placed",
                source_module="sales",
                source_type="sales_order",
                source_id=order.id,
                customer_id=order.customer_id,
                occurred_at=order.updated_at,
                status=order.status.value,
                amount=order.total_amount,
            )
        return order

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
        location_id: Optional[str] = None,
    ) -> SalesOrder:
        enriched, supply_type = self._enrich_so_lines(customer_id, lines)
        location_name = (
            self._location_name(location_id) if location_id is not None else None
        )
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
            location_id=location_id,
            location_name=location_name,
        )
        order.document_content = self.build_document_content(
            "sales_order",
            custom_values,
            bank_account_id,
            terms_and_conditions,
        )
        order = self._so_repo.save(order)
        if order.status == SalesOrderStatus.CONFIRMED:
            self._emit_crm_event(
                "order_placed",
                source_module="sales",
                source_type="sales_order",
                source_id=order.id,
                customer_id=order.customer_id,
                occurred_at=order.updated_at,
                status=order.status.value,
                amount=order.total_amount,
            )
        return order

    def cancel_sales_order(self, order_id: str) -> SalesOrder:
        order = self._domain.cancel_sales_order(order_id)
        self._emit_crm_event(
            "source_reversed",
            source_module="sales",
            source_type="sales_order",
            source_id=order.id,
            customer_id=order.customer_id,
            occurred_at=order.updated_at,
            status=order.status.value,
        )
        return order

    def close_sales_order(self, order_id: str) -> SalesOrder:
        return self._domain.close_sales_order(order_id)

    def list_delivery_notes(self, *, location_filter: dict | None = None) -> List[DeliveryNote]:
        return self._dn_repo.list_all(location_filter=location_filter)

    def get_delivery_note(self, dn_id: str) -> Optional[DeliveryNote]:
        return self._dn_repo.find_by_id(dn_id)

    def list_delivery_notes_by_partner(self, delivery_partner_id: str) -> List[DeliveryNote]:
        return self._dn_repo.list_by_partner(delivery_partner_id)

    def list_unpaid_delivery_charges(
        self, delivery_partner_id: str | None = None
    ) -> List[DeliveryNote]:
        """DNs with business-paid delivery charge still unpaid."""
        notes = (
            self._dn_repo.list_by_partner(delivery_partner_id)
            if delivery_partner_id
            else self._dn_repo.list_all()
        )
        unpaid = []
        for dn in notes:
            if dn.status == DeliveryNoteStatus.CANCELLED:
                continue
            ch = dn.charges
            if not ch.paid_by_us or ch.amount <= 0:
                continue
            if ch.payment_voucher_id or ch.payment_status == DeliveryChargePaymentStatus.PAID:
                continue
            unpaid.append(dn)
        return unpaid

    def list_delivery_notes_by_invoice(self, sales_invoice_id: str) -> List[DeliveryNote]:
        return self._dn_repo.list_by_invoice(sales_invoice_id)

    def invoice_delivered_qty_by_product(self, sales_invoice_id: str) -> dict[str, float]:
        totals: dict[str, float] = {}
        for dn in self._dn_repo.list_by_invoice(sales_invoice_id):
            if dn.status == DeliveryNoteStatus.CANCELLED:
                continue
            for line in dn.lines:
                totals[line.product_id] = round(
                    totals.get(line.product_id, 0.0) + line.qty_delivered, 2
                )
        return totals

    def invoice_pending_delivery_qty(self, sales_invoice_id: str) -> dict[str, float]:
        voucher = self._accounting.get_voucher(sales_invoice_id)
        if not voucher:
            return {}
        items, _, _ = parse_sales_line_items_note(voucher.description)
        delivered = self.invoice_delivered_qty_by_product(sales_invoice_id)
        pending: dict[str, float] = {}
        for item in items:
            product_id = str(item.get("product_id") or "")
            if not product_id:
                continue
            qty = float(item.get("qty") or 0)
            left = round(max(qty - delivered.get(product_id, 0.0), 0.0), 2)
            if left > 0:
                pending[product_id] = left
        return pending

    def _refresh_invoice_delivery_status(self, sales_invoice_id: str) -> None:
        voucher = self._accounting.get_voucher(sales_invoice_id)
        if not voucher or voucher.voucher_type != VoucherType.SALES_INVOICE:
            return
        items, _, _ = parse_sales_line_items_note(voucher.description)
        if not items:
            return
        delivered = self.invoice_delivered_qty_by_product(sales_invoice_id)
        total_qty = 0.0
        total_delivered = 0.0
        updated_items = []
        for item in items:
            product_id = str(item.get("product_id") or "")
            qty = float(item.get("qty") or 0)
            qty_delivered = round(delivered.get(product_id, 0.0), 2)
            item = dict(item)
            item["qty_delivered"] = qty_delivered
            updated_items.append(item)
            total_qty += qty
            total_delivered += min(qty_delivered, qty)
        if total_delivered <= 0:
            status = InvoiceDeliveryStatus.NOT_DELIVERED.value
        elif total_delivered + 0.001 >= total_qty:
            status = InvoiceDeliveryStatus.FULLY_DELIVERED.value
        else:
            status = InvoiceDeliveryStatus.PARTIALLY_DELIVERED.value
        # Rewrite description JSON preserving header line
        header = voucher.description.split("\n", 1)[0]
        invoice_discount = 0.0
        tax_summary = None
        try:
            _, rest = voucher.description.split("\n", 1)
            data = __import__("json").loads(rest.strip())
            invoice_discount = float(data.get("invoice_discount") or 0)
            tax_summary = data.get("tax_summary")
            document_content = data.get("document_content")
            commission = data.get("commission")
        except Exception:
            document_content = None
            commission = None
        voucher.description = header + "\n" + serialize_sales_line_items(
            updated_items,
            invoice_discount=invoice_discount,
            tax_summary=tax_summary,
            document_content=document_content,
            commission=commission,
        )
        voucher.delivery_status = status
        self._accounting.save_voucher(voucher)

    def create_delivery_note(
        self,
        customer_id: str,
        delivery_date: date,
        lines: list[dict],
        sales_order_id: Optional[str] = None,
        sales_invoice_id: Optional[str] = None,
        notes: str = "",
        confirm: bool = False,
        custom_values: Optional[dict] = None,
        terms_and_conditions: Optional[str] = None,
        location_id: str = "",
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
        attachments: Optional[list] = None,
        allow_override: bool = False,
        override_qty_reason: str = "",
        dn_number: Optional[str] = None,
    ) -> DeliveryNote:
        so_number = ""
        so_location_id = ""
        invoice_number = ""
        invoice_pending = None
        stock_source = ""
        if sales_order_id:
            so = self._so_repo.find_by_id(sales_order_id)
            so_number = so.so_number if so else ""
            so_location_id = so.location_id if so else ""
        if sales_invoice_id:
            voucher = self._accounting.get_voucher(sales_invoice_id)
            if not voucher or voucher.voucher_type != VoucherType.SALES_INVOICE:
                raise ValueError("Sales invoice not found")
            invoice_number = voucher.voucher_number
            invoice_pending = self.invoice_pending_delivery_qty(sales_invoice_id)
            # Invoice without DN already issued stock
            if not voucher.reference_dn_id:
                stock_source = "invoice"
        location_id = location_id or so_location_id
        if not dn_number:
            dn_number = self._counter_repo.next("dn_number")
        customer = None
        if self._customer_service:
            customer = self._customer_service.get_customer_detail(customer_id)
        if customer and not billing_address:
            billing_address = getattr(customer, "formatted_address", "") or ""
        if customer and not delivery_address:
            delivery_address = billing_address
        if customer and not contact_person:
            contact_person = getattr(customer, "contact_person", "") or ""
        if customer and not contact_phone:
            contact_phone = getattr(customer, "phone_number", "") or ""
        if customer and not gstin:
            gstin = getattr(customer, "gstin", "") or ""
        dn = self._domain.create_delivery_note(
            dn_number=dn_number,
            customer_id=customer_id,
            customer_name=self._customer_name(customer_id),
            delivery_date=delivery_date,
            lines=lines,
            sales_order_id=sales_order_id,
            so_number=so_number,
            sales_invoice_id=sales_invoice_id,
            invoice_number=invoice_number,
            notes=notes,
            location_id=location_id,
            location_name=self._location_name(location_id),
            billing_address=billing_address,
            delivery_address=delivery_address,
            contact_person=contact_person,
            contact_phone=contact_phone,
            gstin=gstin,
            expected_delivery_date=expected_delivery_date,
            delivery_partner_id=delivery_partner_id,
            delivery_partner_name=delivery_partner_name,
            vehicle_number=vehicle_number,
            driver_name=driver_name,
            driver_phone=driver_phone,
            lr_consignment_number=lr_consignment_number,
            eway_bill_number=eway_bill_number,
            number_of_packages=number_of_packages,
            gross_weight=gross_weight,
            net_weight=net_weight,
            charges=charges,
            attachments=attachments,
            allow_override=allow_override,
            override_qty_reason=override_qty_reason,
            invoice_pending=invoice_pending,
            stock_source=stock_source,
        )
        dn.document_content = self.build_document_content(
            "delivery_note",
            custom_values=custom_values,
            terms_and_conditions=terms_and_conditions,
        )
        self._dn_repo.save(dn)
        if confirm:
            # Backward-compatible: confirm=True completes dispatch+deliver (issues stock).
            return self.deliver_delivery_note(dn.id)
        return dn

    def confirm_delivery_note(self, dn_id: str) -> DeliveryNote:
        dn = self._dn_repo.find_by_id(dn_id)
        if not dn:
            raise ValueError("Delivery note not found")
        if dn.status != DeliveryNoteStatus.DRAFT:
            return dn
        saved = self._domain.confirm_delivery_note(dn_id)
        if saved.sales_invoice_id:
            self._refresh_invoice_delivery_status(saved.sales_invoice_id)
        self._post_delivery_charges_if_needed(saved.id)
        return self._dn_repo.find_by_id(saved.id) or saved

    def dispatch_delivery_note(self, dn_id: str) -> DeliveryNote:
        dn = self._dn_repo.find_by_id(dn_id)
        if not dn:
            raise ValueError("Delivery note not found")
        if dn.status == DeliveryNoteStatus.DRAFT:
            self.confirm_delivery_note(dn_id)
            dn = self._dn_repo.find_by_id(dn_id)
        if not dn.stock_issued:
            if dn.stock_source == "invoice":
                self._domain.mark_stock_issued(dn.id, stock_source="invoice")
            else:
                stock_lines = self._domain.dn_to_stock_lines(dn)
                self._inventory.apply_delivery_note_issue(
                    dn.id, stock_lines, dn.delivery_date
                )
                self._domain.mark_stock_issued(dn.id, stock_source="delivery_note")
        return self._domain.dispatch_delivery_note(dn_id)

    def deliver_delivery_note(
        self,
        dn_id: str,
        *,
        partially: bool = False,
        receiver_name: str = "",
        receiver_phone: str = "",
        receiver_acknowledgement: str = "",
        attachments: Optional[list] = None,
    ) -> DeliveryNote:
        dn = self._dn_repo.find_by_id(dn_id)
        if not dn:
            raise ValueError("Delivery note not found")
        if dn.status in (DeliveryNoteStatus.DRAFT, DeliveryNoteStatus.CONFIRMED):
            self.dispatch_delivery_note(dn_id)
        saved = self._domain.deliver_delivery_note(
            dn_id,
            partially=partially,
            receiver_name=receiver_name,
            receiver_phone=receiver_phone,
            receiver_acknowledgement=receiver_acknowledgement,
            attachments=attachments,
        )
        if saved.sales_invoice_id:
            self._refresh_invoice_delivery_status(saved.sales_invoice_id)
        return saved

    def cancel_delivery_note(self, dn_id: str) -> DeliveryNote:
        dn = self._dn_repo.find_by_id(dn_id)
        if not dn:
            raise ValueError("Delivery note not found")
        if dn.status == DeliveryNoteStatus.CANCELLED:
            return dn
        if dn.charges.payment_voucher_id and dn.charges.payment_status == DeliveryChargePaymentStatus.PAID:
            raise ValueError(
                "Cannot cancel: delivery partner payment already settled; reverse payment first"
            )
        if dn.stock_issued and dn.stock_source == "delivery_note":
            self._inventory.reverse_movements_by_reference(dn.id)
            dn.stock_issued = False
            self._dn_repo.save(dn)
        if dn.charges.expense_voucher_id and not dn.charges.payment_voucher_id:
            try:
                self._accounting.void_voucher(dn.charges.expense_voucher_id)
            except Exception:
                logger.exception("Failed to void delivery expense voucher")
            dn.charges.expense_voucher_id = None
            self._dn_repo.save(dn)
        saved = self._domain.cancel_delivery_note(dn_id)
        if saved.sales_invoice_id:
            self._refresh_invoice_delivery_status(saved.sales_invoice_id)
        return saved

    def update_delivery_note(
        self,
        dn_id: str,
        *,
        delivery_date: date,
        lines: list[dict],
        notes: str = "",
        custom_values: Optional[dict] = None,
        terms_and_conditions: Optional[str] = None,
        location_id: Optional[str] = None,
        allow_edit_delivered: bool = False,
        allow_override: bool = False,
        override_qty_reason: str = "",
        **extra,
    ) -> DeliveryNote:
        location_name = (
            self._location_name(location_id) if location_id is not None else None
        )
        dn = self._dn_repo.find_by_id(dn_id)
        invoice_pending = None
        if dn and dn.sales_invoice_id:
            # Exclude this DN's qty from pending when editing
            pending = self.invoice_pending_delivery_qty(dn.sales_invoice_id)
            for line in dn.lines:
                pending[line.product_id] = round(
                    pending.get(line.product_id, 0.0) + line.qty_delivered, 2
                )
            invoice_pending = pending
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
            location_id=location_id,
            location_name=location_name,
            allow_edit_delivered=allow_edit_delivered,
            allow_override=allow_override,
            override_qty_reason=override_qty_reason,
            invoice_pending=invoice_pending,
            **{k: v for k, v in extra.items() if v is not None},
        )

    def _post_delivery_charges_if_needed(self, dn_id: str) -> DeliveryNote:
        dn = self._dn_repo.find_by_id(dn_id)
        if not dn:
            raise ValueError("Delivery note not found")
        charges = dn.charges
        if not charges.paid_by_us or charges.amount <= 0:
            return dn
        if charges.expense_voucher_id:
            return dn
        expense_account = self._accounting.ensure_delivery_expense_account()
        partner_account = None
        if dn.delivery_partner_id:
            partner_account = self._accounting.get_delivery_partner_account(
                dn.delivery_partner_id
            )
        amount = round(charges.amount + charges.tax_amount, 2)
        if charges.payment_mode and charges.paid_from_account_id and charges.payment_status != DeliveryChargePaymentStatus.UNPAID:
            paying = self._accounting.get_account(charges.paid_from_account_id)
            if not paying:
                raise ValueError("Paid-from account not found")
            voucher = self._accounting.create_journal_entry(
                description=f"Delivery charges for {dn.dn_number}",
                lines=[
                    {
                        "account_id": expense_account.id,
                        "account_name": expense_account.account_name,
                        "debit_amount": amount,
                        "credit_amount": 0,
                        "description": "Delivery Expenses",
                    },
                    {
                        "account_id": paying.id,
                        "account_name": paying.account_name,
                        "debit_amount": 0,
                        "credit_amount": amount,
                        "description": charges.payment_reference or "Delivery charge paid",
                    },
                ],
                voucher_date=charges.payment_date or dn.delivery_date,
            )
            charges.expense_voucher_id = voucher.id
            charges.payment_voucher_id = voucher.id
            charges.payment_status = DeliveryChargePaymentStatus.PAID
            charges.partner_payable_amount = 0.0
        else:
            if not partner_account:
                raise ValueError(
                    "Select a delivery partner (or pay immediately) to record delivery charges"
                )
            voucher = self._accounting.create_journal_entry(
                description=f"Delivery charges payable for {dn.dn_number}",
                lines=[
                    {
                        "account_id": expense_account.id,
                        "account_name": expense_account.account_name,
                        "debit_amount": amount,
                        "credit_amount": 0,
                        "description": "Delivery Expenses",
                    },
                    {
                        "account_id": partner_account.id,
                        "account_name": partner_account.account_name,
                        "debit_amount": 0,
                        "credit_amount": amount,
                        "description": "Delivery Partner Payable",
                    },
                ],
                voucher_date=dn.delivery_date,
            )
            charges.expense_voucher_id = voucher.id
            charges.partner_payable_amount = amount
            charges.payment_status = DeliveryChargePaymentStatus.UNPAID
        if charges.recoverable_from_customer and charges.customer_recoverable_amount <= 0:
            charges.customer_recoverable_amount = amount
        dn.charges = charges
        dn.updated_at = datetime.utcnow()
        return self._dn_repo.save(dn)

    def update_delivery_logistics(
        self,
        dn_id: str,
        *,
        vehicle_number: str = "",
        driver_name: str = "",
        driver_phone: str = "",
        lr_consignment_number: str = "",
        eway_bill_number: str = "",
        receiver_name: str = "",
        receiver_phone: str = "",
        attachments: list | None = None,
    ) -> DeliveryNote:
        dn = self._dn_repo.find_by_id(dn_id)
        if not dn:
            raise ValueError("Delivery note not found")
        if dn.status == DeliveryNoteStatus.CANCELLED:
            raise ValueError("Cannot update a cancelled delivery note")
        if vehicle_number != dn.vehicle_number:
            dn.append_change("vehicle_number", dn.vehicle_number, vehicle_number)
        dn.vehicle_number = (vehicle_number or "").strip()
        dn.driver_name = (driver_name or "").strip()
        dn.driver_phone = (driver_phone or "").strip()
        dn.lr_consignment_number = (lr_consignment_number or "").strip()
        dn.eway_bill_number = (eway_bill_number or "").strip()
        dn.receiver_name = (receiver_name or "").strip()
        dn.receiver_phone = (receiver_phone or "").strip()
        if attachments is not None:
            dn.attachments = list(attachments)
        dn.updated_at = datetime.utcnow()
        return self._dn_repo.save(dn)

    def record_delivery_partner_payment(
        self,
        dn_id: str,
        *,
        paid_from_account_id: str,
        payment_date: Optional[date] = None,
        payment_reference: str = "",
        payment_mode: str = "",
        amount: Optional[float] = None,
    ) -> DeliveryNote:
        dn = self._dn_repo.find_by_id(dn_id)
        if not dn:
            raise ValueError("Delivery note not found")
        charges = dn.charges
        if charges.payment_voucher_id:
            raise ValueError("Delivery partner payment already recorded")
        if not charges.expense_voucher_id:
            self._post_delivery_charges_if_needed(dn_id)
            dn = self._dn_repo.find_by_id(dn_id)
            charges = dn.charges
        partner_account = self._accounting.get_delivery_partner_account(
            dn.delivery_partner_id
        )
        if not partner_account:
            raise ValueError("Delivery partner account not found")
        paying = self._accounting.get_account(paid_from_account_id)
        if not paying:
            raise ValueError("Paid-from account not found")
        pay_amount = round(float(amount if amount is not None else charges.partner_payable_amount or charges.amount), 2)
        if pay_amount <= 0:
            raise ValueError("Payment amount must be positive")
        voucher = self._accounting.create_journal_entry(
            description=f"Delivery partner payment for {dn.dn_number}",
            lines=[
                {
                    "account_id": partner_account.id,
                    "account_name": partner_account.account_name,
                    "debit_amount": pay_amount,
                    "credit_amount": 0,
                    "description": "Settle delivery partner payable",
                },
                {
                    "account_id": paying.id,
                    "account_name": paying.account_name,
                    "debit_amount": 0,
                    "credit_amount": pay_amount,
                    "description": payment_reference or "Payment",
                },
            ],
            voucher_date=payment_date or date.today(),
        )
        charges.payment_voucher_id = voucher.id
        charges.paid_from_account_id = paid_from_account_id
        charges.payment_reference = payment_reference
        charges.payment_mode = payment_mode
        charges.payment_date = payment_date or date.today()
        charges.payment_status = DeliveryChargePaymentStatus.PAID
        charges.partner_payable_amount = round(
            max((charges.partner_payable_amount or pay_amount) - pay_amount, 0.0), 2
        )
        dn.charges = charges
        return self._dn_repo.save(dn)

    def _invoice_numbering_settings(self) -> tuple[str, str, int]:
        """Return (mode, prefix, fy_start_month).

        No business service → external (manual) so callers without settings keep
        current behaviour. New BusinessProfile defaults remain ``app``.
        """
        if not self._business_service:
            return "external", "INV/{FY}/", 4
        profile = self._business_service.get_profile()
        mode = (getattr(profile, "invoice_numbering_mode", None) or "external")
        mode = str(mode).strip().lower()
        if mode not in {"app", "external"}:
            mode = "external"
        prefix = (
            getattr(profile, "invoice_number_prefix", None) or "INV/{FY}/"
        ).strip() or "INV/{FY}/"
        try:
            fy_month = int(getattr(profile, "fy_start_month", 4) or 4)
        except (TypeError, ValueError):
            fy_month = 4
        if fy_month < 1 or fy_month > 12:
            fy_month = 4
        return mode, prefix, fy_month

    def sales_invoice_numbering_mode(self) -> str:
        return self._invoice_numbering_settings()[0]

    def resolve_voucher_financial_year(
        self, voucher_date: Optional[date] = None
    ) -> str:
        _, _, fy_month = self._invoice_numbering_settings()
        return resolve_financial_year(voucher_date or date.today(), fy_month)

    def preview_next_sales_invoice_number(
        self, voucher_date: Optional[date] = None
    ) -> Optional[str]:
        """Preview the next app-mode invoice number without consuming a counter."""
        mode, prefix, fy_month = self._invoice_numbering_settings()
        if mode != "app":
            return None
        fy = resolve_financial_year(voucher_date or date.today(), fy_month)
        next_seq = self._counter_repo.peek_next_value(f"sales_invoice_number:{fy}")
        return peek_invoice_number(prefix, fy, next_seq)

    def _resolve_store_invoice_number(
        self,
        store_invoice_number: str,
        *,
        voucher_date: Optional[date],
        existing_number: Optional[str] = None,
        assign_new: bool = True,
    ) -> tuple[str, str]:
        """Return (store_invoice_number, financial_year)."""
        mode, prefix, fy_month = self._invoice_numbering_settings()
        fy = resolve_financial_year(voucher_date or date.today(), fy_month)
        if mode == "app":
            if assign_new:
                seq = self._counter_repo.ensure_and_next(f"sales_invoice_number:{fy}")
                return format_invoice_number(prefix, fy, seq), fy
            kept = (existing_number or store_invoice_number or "").strip()
            if not kept:
                raise ValueError("Store invoice number is required")
            return kept, fy
        number = (store_invoice_number or "").strip()
        if not number:
            raise ValueError("Store invoice number is required")
        return number, fy

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
        credit_applied: float = 0.0,
        advance_applied: float = 0.0,
        commission: Optional[dict] = None,
        commission_tags: Optional[dict] = None,
        location_id: str = "",
    ) -> Voucher:
        sales_lines = None
        note = line_items_note
        tags = commission_tags
        if document_content is None:
            document_content = self.build_document_content("sales_invoice")
        credit_applied = round(max(float(credit_applied or 0), 0.0), 2)
        advance_applied = round(max(float(advance_applied or 0), 0.0), 2)
        # Inherit tags from linked sales order when not provided.
        if not tags and reference_so_id:
            so = self._so_repo.find_by_id(reference_so_id)
            if so:
                tags = {
                    "commission_agent_ids": list(so.commission_agent_ids or []),
                    "sales_rep_ids": list(so.sales_rep_ids or []),
                }
        if line_items:
            sales_lines, note, grand_total, tags = (
                self._prepare_sales_invoice(
                    customer_account_id,
                    line_items,
                    invoice_discount=invoice_discount,
                    document_content=document_content,
                    commission=commission,
                    commission_tags=tags,
                )
            )
            gross_amount = grand_total
            discount_amount = 0.0
            amount_received = round(max(float(amount_received or 0), 0.0), 2)
            if not location_id:
                for raw in line_items:
                    lid = str(raw.get("location_id") or "").strip()
                    if lid:
                        location_id = lid
                        break

        resolved_number, financial_year = self._resolve_store_invoice_number(
            store_invoice_number,
            voucher_date=voucher_date,
            assign_new=True,
        )
        voucher = self._accounting.create_cash_sales_invoice(
            customer_account_id=customer_account_id,
            store_account_id=store_account_id,
            gross_amount=gross_amount,
            discount_amount=discount_amount,
            amount_received=amount_received,
            store_invoice_number=resolved_number,
            line_items_note=note,
            voucher_date=voucher_date,
            reference_so_id=reference_so_id,
            reference_dn_id=reference_dn_id,
            sales_lines=sales_lines,
            financial_year=financial_year,
            credit_applied=credit_applied,
            advance_applied=advance_applied,
            location_id=location_id,
            location_name=self._location_name(location_id),
        )
        if self._commission_service and tags:
            try:
                self._commission_service.accrue_from_invoice_voucher(
                    voucher,
                    sales_lines=sales_lines,
                    commission_agent_ids=(tags or {}).get("commission_agent_ids"),
                    sales_rep_ids=(tags or {}).get("sales_rep_ids"),
                    amount_received=amount_received,
                    location_id=location_id,
                    location_name=self._location_name(location_id),
                )
            except Exception:
                logger.exception(
                    "Commission accrual failed for invoice %s", voucher.id
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
                store_invoice_number=resolved_number,
                voucher_date=voucher.voucher_date,
                line_items=line_items,
            )
        customer = self._customer_from_account(customer_account_id)
        self._emit_crm_event(
            "invoice_created",
            source_module="finance",
            source_type="sales_invoice",
            source_id=voucher.id,
            customer_id=customer.id,
            occurred_at=voucher.voucher_date,
            status="Posted",
            amount=float(gross_amount or 0),
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
        credit_applied: float = 0.0,
        advance_applied: float = 0.0,
        commission: Optional[dict] = None,
        commission_tags: Optional[dict] = None,
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
            credit_applied=credit_applied,
            advance_applied=advance_applied,
            commission=commission,
            commission_tags=commission_tags,
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
                mode = getattr(line, "discount_mode", "flat") or "flat"
                disc_input = float(
                    getattr(line, "discount_input", None)
                    if getattr(line, "discount_input", None) is not None
                    else getattr(line, "discount", 0)
                    or 0
                )
                if mode in {"percent", "%", "pct"}:
                    line_discount = round(
                        remaining
                        * float(line.rate or 0)
                        * min(max(disc_input, 0.0), 100.0)
                        / 100.0,
                        2,
                    )
                else:
                    # Flat: proportion of remaining qty vs ordered
                    line_discount = round(
                        float(getattr(line, "discount", 0) or 0)
                        * (remaining / line.qty_ordered if line.qty_ordered else 0),
                        2,
                    )
                raw_lines.append(
                    {
                        "product_id": line.product_id,
                        "description": line.product_name,
                        "qty": remaining,
                        "rate": line.rate,
                        "discount": line_discount,
                        "discount_mode": mode,
                        "discount_input": disc_input,
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
        extra_dn_ids: Optional[List[str]] = None,
        include_delivery_charges: bool = True,
    ) -> Voucher:
        dn_ids = [dn_id] + list(extra_dn_ids or [])
        dns: List[DeliveryNote] = []
        for did in dn_ids:
            dn = self._dn_repo.find_by_id(did)
            if not dn:
                raise ValueError(f"Delivery note not found: {did}")
            if dn.status not in (
                DeliveryNoteStatus.DELIVERED,
                DeliveryNoteStatus.PARTIALLY_DELIVERED,
                DeliveryNoteStatus.DISPATCHED,
                DeliveryNoteStatus.CONFIRMED,
            ):
                raise ValueError(
                    f"Invoice can only be created from confirmed/dispatched/delivered notes ({dn.dn_number})"
                )
            if dn.voucher_id:
                raise ValueError(f"Delivery note {dn.dn_number} is already invoiced")
            dns.append(dn)
        primary = dns[0]
        if any(d.customer_id != primary.customer_id for d in dns):
            raise ValueError("All delivery notes must belong to the same customer")
        customer_account = self._accounting.get_customer_account(primary.customer_id)
        if not customer_account:
            raise ValueError("Customer account not found")
        raw_lines: list[dict] = []
        for dn in dns:
            for line in dn.lines:
                raw_lines.append(
                    {
                        "product_id": line.product_id,
                        "qty": line.qty_delivered,
                        "rate": line.rate,
                        "description": line.product_name,
                    }
                )
            if (
                include_delivery_charges
                and dn.charges.recoverable_from_customer
                and dn.charges.customer_recoverable_amount > 0
            ):
                raw_lines.append(
                    {
                        "product_id": "",
                        "qty": 1,
                        "rate": dn.charges.customer_recoverable_amount,
                        "description": "Delivery Charges",
                    }
                )
        if not line_items_note:
            line_items_note = "\n".join(
                f"{line.product_name or line.product_id}: {line.qty_delivered:g} @ {line.rate:g}"
                for dn in dns
                for line in dn.lines
            )
        source_values = {
            item.key: item.value for item in primary.document_content.custom_fields
        }
        voucher = self.create_sales_invoice(
            customer_account_id=customer_account.id,
            store_account_id=store_account_id,
            gross_amount=sum(dn.total_amount for dn in dns)
            + sum(
                dn.charges.customer_recoverable_amount
                for dn in dns
                if include_delivery_charges and dn.charges.recoverable_from_customer
            ),
            discount_amount=discount_amount,
            amount_received=amount_received,
            store_invoice_number=store_invoice_number,
            line_items_note=line_items_note,
            voucher_date=voucher_date or primary.delivery_date,
            reference_so_id=primary.sales_order_id,
            reference_dn_id=primary.id,
            line_items=raw_lines,
            invoice_discount=discount_amount,
            document_content=self.build_document_content(
                "sales_invoice", custom_values=source_values
            ),
        )
        for dn in dns:
            dn.voucher_id = voucher.id
            self._dn_repo.save(dn)
        return voucher

    def list_sales_returns(self, *, location_filter: dict | None = None) -> List[SalesReturn]:
        return self._return_repo.list_all(location_filter=location_filter)

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
        location_id: str = "",
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
            location_id=location_id,
            location_name=self._location_name(location_id),
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

        commission_reversal = 0.0
        if source_invoice is not None and self._commission_service:
            items, _, tax_summary = parse_sales_line_items_note(
                source_invoice.description or ""
            )
            invoice_taxable = float(
                (tax_summary or {}).get("taxable")
                or sum(float(i.get("taxable_amount") or 0) for i in items)
            )
            returned_taxable = 0.0
            invoiced = {
                str(i.get("product_id") or ""): {
                    "qty": float(i.get("qty") or 0),
                    "taxable": float(i.get("taxable_amount") or 0),
                }
                for i in items
                if str(i.get("product_id") or "").strip()
            }
            for line in sales_return.lines or []:
                pid = str(getattr(line, "product_id", "") or "")
                qty = float(getattr(line, "qty", 0) or 0)
                if pid not in invoiced or invoiced[pid]["qty"] <= 0:
                    continue
                share = min(qty / invoiced[pid]["qty"], 1.0)
                returned_taxable = round(
                    returned_taxable + invoiced[pid]["taxable"] * share, 2
                )
            ratio = 0.0
            if returned_taxable > 0 and invoice_taxable > 0:
                ratio = min(returned_taxable / invoice_taxable, 1.0)
            elif return_amount > 0 and invoice_taxable > 0:
                ratio = min(return_amount / invoice_taxable, 1.0)
            if ratio > 0:
                event_date = sales_return.return_date
                if hasattr(event_date, "date"):
                    event_date = event_date.date()
                reversed_entries = self._commission_service.reverse_for_return(
                    source_invoice_id=source_invoice.id,
                    return_ratio=ratio,
                    event_date=event_date,
                )
                commission_reversal = round(
                    sum(float(e.amount) for e in reversed_entries), 2
                )

        voucher = self._accounting.create_sales_return_voucher(
            customer_account_id=customer_account.id,
            return_amount=return_amount,
            description=description,
            amount_refunded=sales_return.amount_refunded,
            refund_account_id=sales_return.refund_account_id,
            voucher_date=sales_return.return_date,
            reference_dn_id=sales_return.source_dn_id,
            source_invoice_id=sales_return.source_invoice_id,
            commission_reversal=0.0,
            agent_account_id=None,
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

    def get_commission_agent_metrics(self, agent_id: str) -> dict:
        """Aggregate sales/return/commission KPIs for a commission agent."""
        agent_id = str(agent_id or "").strip()
        empty = self._empty_commission_agent_metrics()
        if not agent_id:
            return empty
        if self._commission_service:
            metrics = self._commission_service.metrics_for_party("agent", agent_id)
            empty.update(metrics)
            return empty
        return self.list_commission_agent_metrics().get(agent_id, empty)

    @staticmethod
    def _empty_commission_agent_metrics() -> dict:
        return {
            "invoice_count": 0,
            "sales_volume": 0.0,
            "taxable_volume": 0.0,
            "return_count": 0,
            "return_volume": 0.0,
            "net_sales_volume": 0.0,
            "commission_accrued": 0.0,
            "commission_reversed": 0.0,
            "commission_net": 0.0,
            "commission_paid": 0.0,
            "commission_outstanding": 0.0,
            "commission_unpaid": 0.0,
            "payable_balance": 0.0,
        }

    def list_commission_agent_metrics(self) -> dict:
        """Build commission KPIs for all agents from the accrual ledger."""
        if not self._commission_service or not self._commission_service._agent_service:
            return {}
        agents = []
        svc = self._commission_service._agent_service
        if hasattr(svc, "list_all_agents"):
            agents = svc.list_all_agents()
        elif hasattr(svc, "list_agents"):
            agents = svc.list_agents()
        by_agent = {}
        for agent in agents:
            metrics = self._empty_commission_agent_metrics()
            metrics.update(
                self._commission_service.metrics_for_party("agent", agent.id)
            )
            account = self._accounting.get_agent_account(agent.id)
            if account:
                metrics["payable_balance"] = round(
                    float(getattr(account, "current_balance", 0) or 0), 2
                )
            by_agent[agent.id] = metrics
        return by_agent

    def list_agent_commission_invoices(
        self, agent_id: str, *, unpaid_only: bool = False
    ) -> list[dict]:
        """List commission accruals for an agent, grouped by invoice."""
        from vaybooks.bms.domain.finance.accounting.sales_parsing import (
            parse_store_invoice_number,
        )

        agent_id = str(agent_id or "").strip()
        if not agent_id or not self._commission_service:
            return []
        entries = self._commission_service._accrual_repo.list_by_party(
            "agent", agent_id
        )
        by_invoice: dict[str, dict] = {}
        for entry in entries:
            inv_id = entry.source_invoice_id
            row = by_invoice.setdefault(
                inv_id,
                {
                    "invoice_id": inv_id,
                    "invoice_number": "",
                    "sale_date": entry.event_date,
                    "commission_amount": 0.0,
                    "commission_reversed": 0.0,
                    "commission_settled": 0.0,
                    "unpaid_amount": 0.0,
                    "basis": entry.basis,
                },
            )
            amt = float(entry.amount or 0)
            if entry.reversal_of_id or entry.status == "reversed":
                row["commission_reversed"] = round(
                    row["commission_reversed"] + amt, 2
                )
            elif entry.status == "paid":
                row["commission_amount"] = round(row["commission_amount"] + amt, 2)
                row["commission_settled"] = round(row["commission_settled"] + amt, 2)
            else:
                row["commission_amount"] = round(row["commission_amount"] + amt, 2)
                row["unpaid_amount"] = round(row["unpaid_amount"] + amt, 2)
            if entry.event_date and (
                not row["sale_date"] or entry.event_date < row["sale_date"]
            ):
                row["sale_date"] = entry.event_date
        rows = []
        for inv_id, row in by_invoice.items():
            voucher = self._accounting.get_voucher(inv_id)
            if voucher:
                row["invoice_number"] = (
                    parse_store_invoice_number(voucher.description or "")
                    or voucher.voucher_number
                )
            rows.append(row)
        rows.sort(key=lambda r: r.get("sale_date") or date.min, reverse=True)
        if unpaid_only:
            rows = [r for r in rows if float(r.get("unpaid_amount") or 0) > 0.009]
        return rows


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
                    "location_id": sales_return.location_id or None,
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
        location_id: Optional[str] = None,
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
        location_name = (
            self._location_name(location_id) if location_id is not None else None
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
            location_id=location_id,
            location_name=location_name,
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

    def list_sales_invoices(self, *, location_filter: dict | None = None) -> list[dict]:
        discount = self._accounting.get_discount_account()
        discount_id = discount.id if discount else None
        settlement_map = self._accounting.invoice_settlement_map()
        rows = []
        for voucher in self._accounting.list_vouchers_by_type(
            VoucherType.SALES_INVOICE, location_filter=location_filter
        ):
            row = self._accounting.enrich_sales_invoice_row(
                voucher,
                discount_account_id=discount_id,
                settlement_map=settlement_map,
            )
            row["reference_so_id"] = getattr(voucher, "reference_so_id", None)
            row["reference_dn_id"] = getattr(voucher, "reference_dn_id", None)
            row["reference_project_id"] = getattr(voucher, "reference_project_id", None)
            rows.append(row)
        rows.sort(
            key=lambda r: (r.get("sale_date") or date.min, r.get("voucher_number") or ""),
            reverse=True,
        )
        return rows

    def related_document_counts(
        self, customer_id: str, *, customer_account_id: str = ""
    ) -> dict:
        """Counts for Related Transactions — one service entry point.

        Uses repository ``count_by_customer`` / voucher account counts when
        available; missing backends return an empty dict for that key.
        """
        counts: dict = {}

        def _repo_count(repo) -> int | None:
            if repo is None:
                return None
            fn = getattr(repo, "count_by_customer", None)
            if not callable(fn):
                return None
            try:
                return int(fn(customer_id) or 0)
            except Exception:
                return None

        for key, repo in (
            ("estimates", self._estimate_repo),
            ("quotations", self._quotation_repo),
            ("sales_orders", self._so_repo),
            ("delivery_notes", self._dn_repo),
            ("sales_returns", self._return_repo),
        ):
            value = _repo_count(repo)
            if value is not None:
                counts[key] = value

        if customer_account_id:
            try:
                counts["sales_invoices"] = self._accounting.count_vouchers_for_account(
                    VoucherType.SALES_INVOICE, customer_account_id
                )
            except Exception:
                pass
            try:
                counts["receipts"] = self._accounting.count_vouchers_for_account(
                    VoucherType.RECEIPT, customer_account_id
                )
            except Exception:
                pass
        return counts

    def get_sales_invoice(self, voucher_id: str) -> Optional[dict]:
        voucher = self._accounting.get_voucher(voucher_id)
        if not voucher or voucher.voucher_type != VoucherType.SALES_INVOICE:
            return None
        discount = self._accounting.get_discount_account()
        discount_id = discount.id if discount else None
        settlement_map = self._accounting.invoice_settlement_map()
        row = self._accounting.enrich_sales_invoice_row(
            voucher,
            discount_account_id=discount_id,
            settlement_map=settlement_map,
        )
        row["reference_so_id"] = getattr(voucher, "reference_so_id", None)
        row["reference_dn_id"] = getattr(voucher, "reference_dn_id", None)
        row["reference_project_id"] = getattr(voucher, "reference_project_id", None)
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
        credit_applied: float = 0.0,
        advance_applied: float = 0.0,
        commission: Optional[dict] = None,
        commission_tags: Optional[dict] = None,
    ) -> Voucher:
        from vaybooks.bms.application.sales.commission_service import parse_commission_tags

        old = self._accounting.get_voucher(voucher_id)
        if not old or old.voucher_type != VoucherType.SALES_INVOICE:
            raise ValueError("Sales invoice not found")
        # Later settlement locks commission changes.
        if any(
            v.voucher_type == VoucherType.COMMISSION_PAYMENT
            and v.reference_invoice_id == voucher_id
            for v in self._accounting.list_vouchers_by_type(
                VoucherType.COMMISSION_PAYMENT
            )
        ):
            raise ValueError(
                "Commission was settled by a separate payment; reverse that payment first"
            )
        old_items, _, _ = parse_sales_line_items_note(old.description)
        tags = commission_tags
        if tags is None:
            tags = parse_commission_tags(old.description or "")
            if commission:
                agent_id = str(commission.get("agent_id") or "").strip()
                if agent_id:
                    tags = {
                        "commission_agent_ids": [agent_id],
                        "sales_rep_ids": list(
                            commission.get("sales_rep_ids")
                            or tags.get("sales_rep_ids")
                            or []
                        ),
                    }
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
        sales_lines, note, grand_total, tags = (
            self._prepare_sales_invoice(
                customer_account_id,
                line_items,
                invoice_discount=invoice_discount,
                document_content=content,
                commission=commission,
                commission_tags=tags,
            )
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
        from vaybooks.bms.domain.finance.accounting.sales_parsing import (
            parse_store_invoice_number,
        )

        existing_number = parse_store_invoice_number(old.description or "")
        resolved_number, financial_year = self._resolve_store_invoice_number(
            store_invoice_number,
            voucher_date=voucher_date,
            existing_number=existing_number,
            assign_new=False,
        )
        voucher = self._accounting.update_cash_sales_invoice(
            voucher_id=voucher_id,
            customer_account_id=customer_account_id,
            store_account_id=store_account_id,
            gross_amount=grand_total,
            discount_amount=0.0,
            amount_received=round(max(float(amount_received or 0), 0.0), 2),
            store_invoice_number=resolved_number,
            line_items_note=note,
            voucher_date=voucher_date,
            sales_lines=sales_lines,
            allow_erp_linked=True,
            financial_year=financial_year,
            credit_applied=round(max(float(credit_applied or 0), 0.0), 2),
            advance_applied=round(max(float(advance_applied or 0), 0.0), 2),
        )
        if self._commission_service:
            # Reverse prior accruals for this invoice, then re-accrue from tags.
            try:
                prior = self._commission_service._accrual_repo.list_by_invoice(
                    voucher_id, status="accrued"
                )
                if prior:
                    self._commission_service.reverse_for_return(
                        source_invoice_id=voucher_id,
                        return_ratio=1.0,
                        event_date=voucher_date,
                    )
                self._commission_service.accrue_from_invoice_voucher(
                    voucher,
                    sales_lines=sales_lines,
                    commission_agent_ids=(tags or {}).get("commission_agent_ids"),
                    sales_rep_ids=(tags or {}).get("sales_rep_ids"),
                    amount_received=round(max(float(amount_received or 0), 0.0), 2),
                )
            except Exception:
                logger.exception(
                    "Commission re-accrual failed for invoice %s", voucher_id
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
            store_invoice_number=resolved_number,
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
        self._emit_crm_event(
            "source_reversed",
            source_module="finance",
            source_type="sales_invoice",
            source_id=voucher_id,
            occurred_at=utc_now(),
            status="Reversed",
        )

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

    def _location_name(self, location_id: Optional[str]) -> str:
        if not location_id:
            return ""
        location = self._inventory.get_location(location_id)
        return location.name if location else ""

    def _customer_name(self, customer_id: str) -> str:
        if not self._customer_service or not customer_id:
            return ""
        customer = self._customer_service.get_customer_detail(customer_id)
        return customer.customer_name if customer else ""
