from __future__ import annotations

import json
import re
from datetime import date
from typing import Dict, List, Optional

from vaybooks.bms.application.accounting_app_service import AccountingAppService
from vaybooks.bms.domain.accounting.entities import Voucher
from vaybooks.bms.domain.accounting.repository import CounterRepository, VoucherRepository
from vaybooks.bms.domain.accounting.sales_parsing import sales_amounts_from_lines
from vaybooks.bms.domain.projects.entities import (
    ProjectCostTransfer,
    ProjectExpense,
    ProjectProforma,
    ProjectQuotationLine,
    ProjectRetentionEntry,
    ProjectVariation,
    ProjectWorkOrder,
    ProjectWriteOff,
)
from vaybooks.bms.domain.projects.measurement import (
    ProjectMeasurement,
    ProjectRABill,
    ProjectRABillLine,
)
from vaybooks.bms.domain.projects.repository import (
    ProjectBoqRepository,
    ProjectCostTransferRepository,
    ProjectExpenseRepository,
    ProjectMeasurementRepository,
    ProjectProformaRepository,
    ProjectRABillRepository,
    ProjectRepository,
    ProjectRetentionRepository,
    ProjectVariationRepository,
    ProjectWorkOrderRepository,
    ProjectWriteOffRepository,
)
from vaybooks.bms.domain.shared.date_utils import today, utc_now
from vaybooks.bms.domain.shared.enums import (
    ProjectBillingMode,
    ProjectDocumentCategory,
    ProjectExpenseSource,
    ProjectMeasurementStatus,
    ProjectRABillStatus,
    ProjectStatus,
    ProjectVariationStatus,
    PurchaseOrderStatus,
    VoucherType,
)
from vaybooks.bms.domain.shared.exceptions import ValidationError


class ProjectBillingAppService:
    def __init__(
        self,
        project_repo: ProjectRepository,
        work_order_repo: ProjectWorkOrderRepository,
        counter_repo: CounterRepository,
        accounting_service: Optional[AccountingAppService] = None,
        voucher_repo: Optional[VoucherRepository] = None,
        sales_service=None,
        document_service=None,
        customer_repo=None,
        time_repo=None,
        expense_repo: Optional[ProjectExpenseRepository] = None,
        ra_repo: Optional[ProjectRABillRepository] = None,
        proforma_repo: Optional[ProjectProformaRepository] = None,
        retention_repo: Optional[ProjectRetentionRepository] = None,
        variation_repo: Optional[ProjectVariationRepository] = None,
        transfer_repo: Optional[ProjectCostTransferRepository] = None,
        write_off_repo: Optional[ProjectWriteOffRepository] = None,
        purchase_service=None,
        boq_repo: Optional[ProjectBoqRepository] = None,
        measurement_repo: Optional[ProjectMeasurementRepository] = None,
        measurement_service=None,
    ):
        self._project_repo = project_repo
        self._work_order_repo = work_order_repo
        self._counter_repo = counter_repo
        self._accounting = accounting_service
        self._voucher_repo = voucher_repo
        self._sales = sales_service
        self._document_service = document_service
        self._customer_repo = customer_repo
        self._time_repo = time_repo
        self._expense_repo = expense_repo
        self._ra_repo = ra_repo
        self._proforma_repo = proforma_repo
        self._retention_repo = retention_repo
        self._variation_repo = variation_repo
        self._transfer_repo = transfer_repo
        self._write_off_repo = write_off_repo
        self._purchase_service = purchase_service
        self._boq_repo = boq_repo
        self._measurement_repo = measurement_repo
        self._measurement_service = measurement_service

    def _get_project(self, project_id: str):
        project = self._project_repo.find_by_id(project_id)
        if not project:
            raise ValidationError("Project not found")
        return project

    def _ensure_not_closed(self, project) -> None:
        if project.status == ProjectStatus.FINANCIALLY_CLOSED:
            raise ValidationError("Project is closed; billing changes are blocked")

    def _ensure_billing_allowed(self, project, *, allow_credit_note: bool = False) -> None:
        self._ensure_not_closed(project)
        if project.period_locked and not allow_credit_note:
            raise ValidationError(
                "Billing period is locked; only credit notes are allowed"
            )

    def _get_customer_account(self, project):
        if not self._accounting:
            raise ValidationError("Accounting service is unavailable")
        account = self._accounting.get_customer_account(project.customer_id)
        if not account:
            raise ValidationError("Customer account not found for project")
        return account

    def _list_project_vouchers(self, project_id: str) -> List[Voucher]:
        if self._accounting:
            return self._accounting.list_vouchers_by_project(project_id)
        if self._voucher_repo:
            return self._voucher_repo.list_by_project(project_id)
        return []

    def _save_voucher(self, voucher: Voucher, project_id: str) -> Voucher:
        voucher.reference_project_id = project_id
        if self._voucher_repo:
            return self._voucher_repo.save(voucher)
        return voucher

    @staticmethod
    def _append_meta(description: str, tag: str, payload: dict) -> str:
        base = (description or "").strip()
        return f"{base}\n<!--{tag}:{json.dumps(payload, separators=(',', ':'))}-->"

    @staticmethod
    def _parse_meta(description: str, tag: str) -> dict:
        pattern = re.compile(rf"\n<!--{tag}:(\{{.*?\}})-->", re.DOTALL)
        match = pattern.search(description or "")
        if not match:
            return {}
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return {}

    def _invoice_net_amount(self, voucher: Voucher) -> float:
        discount = self._accounting.get_discount_account() if self._accounting else None
        discount_id = discount.id if discount else None
        amounts = sales_amounts_from_lines(voucher.lines, discount_id)
        return float(amounts.get("net") or 0.0)

    def _cumulative_billed(self, project_id: str) -> float:
        total = 0.0
        for voucher in self._list_project_vouchers(project_id):
            if voucher.voucher_type == VoucherType.SALES_INVOICE:
                total += self._invoice_net_amount(voucher)
            elif voucher.voucher_type == VoucherType.SALES_RETURN:
                total -= self._invoice_net_amount(voucher)
        return round(total, 2)

    def _total_project_cost(self, project_id: str) -> float:
        labour = 0.0
        if self._time_repo:
            labour = sum(e.labour_cost for e in self._time_repo.list_by_project(project_id))
        expenses = 0.0
        if self._expense_repo:
            expenses = sum(e.amount for e in self._expense_repo.list_by_project(project_id))
        return round(labour + expenses, 2)

    def _register_invoice_pdf(self, project, voucher: Voucher) -> None:
        if not self._document_service:
            return
        try:
            self._document_service.register_generated_pdf(
                project_id=project.id,
                name=f"Tax invoice {voucher.voucher_number}",
                pdf_bytes=b"",
                category=ProjectDocumentCategory.TAX_INVOICE.value,
                source_ref_type="voucher",
                source_ref_id=voucher.id,
            )
        except Exception:
            pass

    def create_work_order(
        self,
        project_id: str,
        wo_date: Optional[date] = None,
        description: str = "",
        quotation_id: str = "",
    ) -> ProjectWorkOrder:
        self._get_project(project_id)
        work_order = ProjectWorkOrder(
            project_id=project_id,
            wo_number=self._counter_repo.next("project_work_order_number"),
            wo_date=wo_date or today(),
            description=(description or "").strip(),
            quotation_id=(quotation_id or "").strip(),
        )
        return self._work_order_repo.save(work_order)

    def list_work_orders(self, project_id: str) -> List[ProjectWorkOrder]:
        return self._work_order_repo.list_by_project(project_id)

    def create_tax_invoice(
        self,
        project_id: str,
        line_items: list[dict],
        store_account_id: str,
        amount_received: float = 0.0,
        voucher_date: Optional[date] = None,
        store_invoice_number: str = "",
        confirm_over_contract: bool = False,
        retention_pct: Optional[float] = None,
        activity_attribution: Optional[dict] = None,
    ) -> Voucher:
        project = self._get_project(project_id)
        self._ensure_billing_allowed(project)
        if not self._sales:
            raise ValidationError("Sales service is unavailable")
        if not line_items:
            raise ValidationError("At least one line item is required")
        customer_account = self._get_customer_account(project)
        preview_total = sum(
            float(item.get("qty") or item.get("quantity") or 1)
            * float(item.get("rate") or 0)
            for item in line_items
        )
        cumulative = self._cumulative_billed(project.id)
        if (
            project.contract_value > 0
            and cumulative + preview_total > project.contract_value
            and not confirm_over_contract
        ):
            raise ValidationError(
                "Invoice would exceed contract value; set confirm_over_contract=True to proceed"
            )
        invoice_number = (store_invoice_number or "").strip() or self._counter_repo.next(
            "voucher_number"
        )
        description = f"Project tax invoice for {project.project_number}"
        mode = getattr(project.billing_mode, "value", str(project.billing_mode))
        if mode in (
            ProjectBillingMode.MILESTONE.value,
            ProjectBillingMode.UNIT_BOQ.value,
            ProjectBillingMode.TIME_AND_MATERIAL.value,
            ProjectBillingMode.RUNNING_ACCOUNT.value,
        ):
            description = f"{description} [{mode}]"
        if activity_attribution:
            description = self._append_meta(
                description, "ACTIVITY_ATTR", activity_attribution
            )
        voucher = self._sales.create_sales_invoice(
            customer_account_id=customer_account.id,
            store_account_id=store_account_id,
            gross_amount=preview_total,
            discount_amount=0.0,
            amount_received=float(amount_received or 0.0),
            store_invoice_number=invoice_number,
            line_items=line_items,
            voucher_date=voucher_date,
        )
        voucher.description = description
        voucher = self._save_voucher(voucher, project.id)
        effective_retention = (
            project.retention_pct
            if retention_pct is None
            else float(retention_pct or 0.0)
        )
        net_amount = self._invoice_net_amount(voucher)
        if effective_retention > 0 and self._retention_repo and net_amount > 0:
            withheld = round(net_amount * effective_retention / 100.0, 2)
            entry = ProjectRetentionEntry(
                project_id=project.id,
                invoice_voucher_id=voucher.id,
                invoice_number=voucher.voucher_number,
                withheld_amount=withheld,
            )
            self._retention_repo.save(entry)
        self._register_invoice_pdf(project, voucher)
        return voucher

    def list_tm_invoice_eligibility(self, project_id: str) -> dict:
        """Eligible T&M / milestone / Unit-BOQ sources that are not yet billed."""
        project = self._get_project(project_id)
        mode = project.billing_mode
        time_lines = []
        expense_lines = []
        milestone_lines = []
        unit_boq_lines = []
        if self._time_repo:
            for entry in self._time_repo.list_by_project(project_id):
                if getattr(entry, "billed", False):
                    continue
                time_lines.append(
                    {
                        "source_type": "time",
                        "source_id": entry.id,
                        "description": f"Time {entry.id[:8]}",
                        "amount": float(getattr(entry, "labour_cost", 0) or 0),
                    }
                )
        if self._expense_repo:
            for expense in self._expense_repo.list_by_project(project_id):
                if (
                    getattr(expense, "reimbursable", False) is False
                    and mode != ProjectBillingMode.TIME_AND_MATERIAL
                ):
                    continue
                if getattr(expense, "billed", False):
                    continue
                expense_lines.append(
                    {
                        "source_type": "expense",
                        "source_id": expense.id,
                        "description": (
                            expense.description
                            if hasattr(expense, "description")
                            else expense.id[:8]
                        ),
                        "amount": float(expense.amount or 0),
                    }
                )
        if mode in (
            ProjectBillingMode.MILESTONE,
            ProjectBillingMode.HYBRID,
            ProjectBillingMode.FIXED,
        ):
            for activity in project.activities or []:
                if float(getattr(activity, "percent_complete", 0) or 0) < 100:
                    continue
                weight = float(getattr(activity, "weightage", 0) or 0)
                planned = float(getattr(activity, "planned_revenue_amount", 0) or 0)
                if planned > 0:
                    amount = planned
                elif weight > 0 and project.contract_value > 0:
                    amount = round(project.contract_value * weight / 100.0, 2)
                else:
                    amount = float(getattr(activity, "amount", 0) or 0)
                milestone_lines.append(
                    {
                        "source_type": "milestone",
                        "source_id": activity.id,
                        "description": activity.name,
                        "amount": amount,
                    }
                )
        if mode in (
            ProjectBillingMode.UNIT_BOQ,
            ProjectBillingMode.RUNNING_ACCOUNT,
            ProjectBillingMode.HYBRID,
        ):
            if self._boq_repo:
                for item in self._boq_repo.list_by_project(project_id):
                    contracted = float(
                        item.contracted_qty or item.estimated_qty or 0.0
                    )
                    billed = float(getattr(item, "billed_qty", 0) or 0.0)
                    remaining = round(contracted - billed, 4)
                    if remaining <= 0.0001:
                        continue
                    rate = float(
                        item.contracted_rate or item.selling_rate or 0.0
                    )
                    unit_boq_lines.append(
                        {
                            "source_type": "boq",
                            "source_id": item.id,
                            "description": item.description,
                            "qty": remaining,
                            "rate": rate,
                            "amount": round(remaining * rate, 2),
                        }
                    )
        return {
            "project_id": project_id,
            "billing_mode": mode.value,
            "time_lines": time_lines,
            "expense_lines": expense_lines,
            "milestone_lines": milestone_lines,
            "unit_boq_lines": unit_boq_lines,
        }

    def create_receipt(
        self,
        project_id: str,
        receiving_account_id: str,
        customer_account_id: str,
        amount: float,
        description: str,
        voucher_date: Optional[date] = None,
        allocation_invoice_id: Optional[str] = None,
        allocations: Optional[List[dict]] = None,
    ) -> dict:
        """Record a receipt; optional invoice allocations track short-pay / unallocated."""
        project = self._get_project(project_id)
        self._ensure_not_closed(project)
        if not self._accounting:
            raise ValidationError("Accounting service is unavailable")
        receipt_amount = float(amount or 0)
        if receipt_amount <= 0:
            raise ValidationError("Receipt amount must be greater than zero")

        alloc_rows: List[dict] = []
        if allocations:
            for row in allocations:
                invoice_id = (
                    row.get("invoice_id")
                    or row.get("invoice_voucher_id")
                    or ""
                ).strip()
                alloc_amt = float(row.get("amount") or 0)
                if not invoice_id or alloc_amt <= 0:
                    continue
                alloc_rows.append(
                    {"invoice_id": invoice_id, "amount": round(alloc_amt, 2)}
                )
        elif allocation_invoice_id:
            alloc_rows.append(
                {
                    "invoice_id": (allocation_invoice_id or "").strip(),
                    "amount": receipt_amount,
                }
            )

        allocated_total = round(sum(r["amount"] for r in alloc_rows), 2)
        if allocated_total > receipt_amount + 0.01:
            raise ValidationError(
                "Allocation total cannot exceed receipt amount"
            )
        unallocated = round(max(0.0, receipt_amount - allocated_total), 2)

        short_payment = 0.0
        for row in alloc_rows:
            outstanding = self._invoice_outstanding_amount(row["invoice_id"])
            if outstanding is None:
                continue
            short_payment += max(0.0, outstanding - row["amount"])
        short_payment = round(short_payment, 2)

        final_description = description or f"Receipt for {project.project_number}"
        if alloc_rows:
            final_description = self._append_meta(
                final_description,
                "ALLOC_INVOICE",
                {
                    "allocations": alloc_rows,
                    "short_payment": short_payment,
                    "unallocated": unallocated,
                },
            )
        voucher = self._accounting.create_receipt(
            receiving_account_id=receiving_account_id,
            customer_account_id=customer_account_id,
            amount=receipt_amount,
            description=final_description,
            voucher_date=voucher_date,
        )
        saved = self._save_voucher(voucher, project.id)
        return {
            "voucher": saved,
            "short_payment": short_payment,
            "unallocated": unallocated,
            "allocations": alloc_rows,
        }

    def _invoice_outstanding_amount(self, invoice_id: str) -> Optional[float]:
        if not invoice_id:
            return None
        voucher = None
        if self._voucher_repo:
            voucher = self._voucher_repo.find_by_id(invoice_id)
        if voucher is None and self._accounting and hasattr(
            self._accounting, "get_voucher"
        ):
            try:
                voucher = self._accounting.get_voucher(invoice_id)
            except Exception:
                voucher = None
        if voucher is None:
            return None
        if voucher.voucher_type != VoucherType.SALES_INVOICE:
            return None
        net = round(self._invoice_net_amount(voucher), 2)
        if net > 0:
            return net
        # Fallback for simple AR invoices without cash-sales line shape.
        debit_total = sum(float(line.debit_amount or 0) for line in voucher.lines)
        credit_total = sum(float(line.credit_amount or 0) for line in voucher.lines)
        return round(max(debit_total, credit_total), 2)

    def create_vendor_payment(
        self,
        project_id: str,
        vendor_account_id: str,
        expense_account_id: str,
        paying_account_id: str,
        amount: float,
        description: str,
        voucher_date: Optional[date] = None,
        reference_activity_id: Optional[str] = None,
        gross_amount: Optional[float] = None,
        tds_section: str = "",
        tds_rate: float = 0,
        tds_amount: float = 0,
        net_paid: Optional[float] = None,
    ) -> Voucher:
        project = self._get_project(project_id)
        self._ensure_not_closed(project)
        if not self._accounting:
            raise ValidationError("Accounting service is unavailable")
        gross = float(gross_amount if gross_amount is not None else amount)
        tds = float(tds_amount or 0.0)
        paid = float(net_paid if net_paid is not None else (gross - tds))
        if paid <= 0:
            raise ValidationError("Payment amount must be greater than zero")
        final_description = description or f"Vendor payment for {project.project_number}"
        if tds > 0:
            final_description = self._append_meta(
                final_description,
                "TDS",
                {
                    "section": (tds_section or "").strip(),
                    "rate": float(tds_rate or 0.0),
                    "amount": tds,
                    "gross_amount": gross,
                },
            )
        voucher = self._accounting.create_vendor_payment(
            vendor_account_id=vendor_account_id,
            expense_account_id=expense_account_id,
            paying_account_id=paying_account_id,
            amount=paid,
            description=final_description,
            voucher_date=voucher_date,
        )
        voucher.reference_activity_id = reference_activity_id
        return self._save_voucher(voucher, project.id)

    def get_wip_balances(self, project_id: str) -> dict:
        project = self._get_project(project_id)
        total_cost = self._total_project_cost(project_id)
        billed_revenue = self._cumulative_billed(project_id)
        unbilled = round(max(0.0, total_cost - billed_revenue), 2)
        return {
            "project_id": project.id,
            "project_number": project.project_number,
            "contract_value": project.contract_value,
            "total_cost": total_cost,
            "billed_revenue": billed_revenue,
            "unbilled_cost": unbilled,
            "wip_balance": unbilled,
        }

    def get_party_balances(self, project_id: str) -> dict:
        project = self._get_project(project_id)
        customer_outstanding = 0.0
        vendor_payable = 0.0
        discount = self._accounting.get_discount_account() if self._accounting else None
        discount_id = discount.id if discount else None
        for voucher in self._list_project_vouchers(project_id):
            if voucher.voucher_type == VoucherType.SALES_INVOICE:
                amounts = sales_amounts_from_lines(voucher.lines, discount_id)
                customer_outstanding += amounts.get("outstanding", 0.0)
            elif voucher.voucher_type == VoucherType.RECEIPT:
                customer_outstanding -= sum(
                    line.debit_amount for line in voucher.lines
                )
            elif voucher.voucher_type == VoucherType.VENDOR_PAYMENT:
                vendor_payable += sum(line.credit_amount for line in voucher.lines)
        return {
            "project_id": project.id,
            "project_number": project.project_number,
            "customer_outstanding": round(customer_outstanding, 2),
            "vendor_payable": round(vendor_payable, 2),
        }

    def create_ra_bill(
        self,
        project_id: str,
        claim_amount: float,
        ra_date: Optional[date] = None,
        description: str = "",
        retention_pct: Optional[float] = None,
        work_order_id: str = "",
    ) -> ProjectRABill:
        """Legacy flat-amount RA bill (compat). Prefer create_ra_from_measurements."""
        if not self._ra_repo:
            raise ValidationError("RA bill repository is unavailable")
        project = self._get_project(project_id)
        self._ensure_billing_allowed(project)
        if float(claim_amount or 0) <= 0:
            raise ValidationError("Claim amount must be greater than zero")
        effective_retention = (
            project.retention_pct
            if retention_pct is None
            else float(retention_pct or 0.0)
        )
        retention_amount = round(
            float(claim_amount) * effective_retention / 100.0, 2
        )
        line = ProjectRABillLine(
            boq_item_id="",
            description=(description or "").strip() or "RA claim",
            current_claimed_qty=1.0,
            cumulative_claimed_qty=1.0,
            rate=float(claim_amount),
        )
        ra_bill = ProjectRABill(
            project_id=project.id,
            ra_number=self._counter_repo.next("project_ra_number"),
            ra_date=ra_date or today(),
            status=ProjectRABillStatus.DRAFT,
            lines=[line],
            description=(description or "").strip(),
            retention_pct=effective_retention,
            retention_amount_claimed=retention_amount,
            work_order_id=(work_order_id or "").strip(),
        )
        return self._ra_repo.save(ra_bill)

    def _prior_ra_cumulative(
        self, project_id: str, boq_item_id: str, *, certified: bool = False
    ) -> float:
        if not self._ra_repo:
            return 0.0
        field = "cumulative_certified_qty" if certified else "cumulative_claimed_qty"
        best = 0.0
        for ra_bill in self._ra_repo.list_by_project(project_id):
            if ra_bill.status == ProjectRABillStatus.CANCELLED:
                continue
            for line in ra_bill.lines:
                if line.boq_item_id == boq_item_id:
                    best = max(best, float(getattr(line, field) or 0.0))
        return best

    def create_ra_from_measurements(
        self,
        project_id: str,
        measurement_ids: List[str],
        *,
        ra_date: Optional[date] = None,
        advance_recovery: float = 0,
        retention_pct: Optional[float] = None,
        other_deductions: float = 0,
        tds_amount: float = 0,
        description: str = "",
        work_order_id: str = "",
    ) -> ProjectRABill:
        if not self._ra_repo:
            raise ValidationError("RA bill repository is unavailable")
        if not self._measurement_repo:
            raise ValidationError("Measurement repository is unavailable")
        if not self._boq_repo:
            raise ValidationError("BOQ repository is unavailable")
        if not measurement_ids:
            raise ValidationError("At least one measurement is required")
        project = self._get_project(project_id)
        self._ensure_billing_allowed(project)

        measurements: List[ProjectMeasurement] = []
        for measurement_id in measurement_ids:
            measurement = self._measurement_repo.find_by_id(measurement_id)
            if not measurement or measurement.project_id != project_id:
                raise ValidationError("Measurement not found")
            if measurement.status not in (
                ProjectMeasurementStatus.SUBMITTED,
                ProjectMeasurementStatus.ENGINEER_VERIFIED,
                ProjectMeasurementStatus.CUSTOMER_CERTIFIED,
            ):
                raise ValidationError(
                    f"Measurement {measurement_id} is not eligible for RA billing"
                )
            if (measurement.ra_bill_id or "").strip():
                raise ValidationError(
                    f"Measurement {measurement_id} is already linked to an RA bill"
                )
            measurements.append(measurement)

        grouped: dict[str, List[ProjectMeasurement]] = {}
        for measurement in measurements:
            grouped.setdefault(measurement.boq_item_id, []).append(measurement)

        ra_lines: List[ProjectRABillLine] = []
        for boq_item_id, group in grouped.items():
            boq_item = self._boq_repo.find_by_id(boq_item_id)
            if not boq_item:
                raise ValidationError("BOQ item not found for measurement")
            previous_qty = self._prior_ra_cumulative(project_id, boq_item_id)
            current_claimed = round(sum(m.quantity for m in group), 4)
            rate = float(boq_item.contracted_rate or boq_item.selling_rate or 0.0)
            if rate <= 0:
                raise ValidationError(f"BOQ item {boq_item.code} has no billable rate")
            ra_lines.append(
                ProjectRABillLine(
                    boq_item_id=boq_item_id,
                    description=boq_item.description,
                    unit=boq_item.unit,
                    previous_qty=previous_qty,
                    current_claimed_qty=current_claimed,
                    cumulative_claimed_qty=round(previous_qty + current_claimed, 4),
                    rate=rate,
                    measurement_ids=[m.id for m in group],
                )
            )

        effective_retention = (
            project.retention_pct
            if retention_pct is None
            else float(retention_pct or 0.0)
        )
        ra_bill = ProjectRABill(
            project_id=project.id,
            ra_number=self._counter_repo.next("project_ra_number"),
            ra_date=ra_date or today(),
            status=ProjectRABillStatus.DRAFT,
            lines=ra_lines,
            advance_recovery=float(advance_recovery or 0.0),
            retention_pct=effective_retention,
            tds_amount=float(tds_amount or 0.0),
            other_deductions=float(other_deductions or 0.0),
            description=(description or "").strip(),
            work_order_id=(work_order_id or "").strip(),
        )
        ra_bill.retention_amount_claimed = round(
            ra_bill.gross_claimed * effective_retention / 100.0, 2
        )
        saved = self._ra_repo.save(ra_bill)
        for measurement in measurements:
            measurement.ra_bill_id = saved.id
            measurement.updated_at = utc_now()
            self._measurement_repo.save(measurement)
        return saved

    def submit_ra(self, ra_id: str) -> ProjectRABill:
        ra_bill = self._require_ra(ra_id)
        if ra_bill.status != ProjectRABillStatus.DRAFT:
            raise ValidationError("Only draft RA bills can be submitted")
        ra_bill.status = ProjectRABillStatus.SUBMITTED
        ra_bill.updated_at = utc_now()
        return self._ra_repo.save(ra_bill)

    def mark_claimed(self, ra_id: str, claimed_by: str = "") -> ProjectRABill:
        ra_bill = self._require_ra(ra_id)
        if ra_bill.status not in (
            ProjectRABillStatus.DRAFT,
            ProjectRABillStatus.SUBMITTED,
        ):
            raise ValidationError("RA bill cannot be marked claimed from current status")
        ra_bill.status = ProjectRABillStatus.CLAIMED
        ra_bill.claimed_by = (claimed_by or "").strip()
        ra_bill.updated_at = utc_now()
        return self._ra_repo.save(ra_bill)

    def certify_ra(
        self,
        ra_id: str,
        line_certifications: List[dict],
        certified_by: str = "",
    ) -> ProjectRABill:
        ra_bill = self._require_ra(ra_id)
        if ra_bill.status not in (
            ProjectRABillStatus.DRAFT,
            ProjectRABillStatus.SUBMITTED,
            ProjectRABillStatus.CLAIMED,
        ):
            raise ValidationError("RA bill cannot be certified from current status")
        cert_map = {
            (row.get("line_id") or "").strip(): float(
                row.get("current_certified_qty") or 0.0
            )
            for row in line_certifications or []
        }
        partial = False
        for line in ra_bill.lines:
            certified_qty = cert_map.get(line.id, line.current_claimed_qty)
            if certified_qty < 0:
                raise ValidationError("Certified quantity cannot be negative")
            if certified_qty > line.current_claimed_qty + 0.0001:
                raise ValidationError("Certified quantity cannot exceed claimed quantity")
            line.current_certified_qty = certified_qty
            line.cumulative_certified_qty = round(
                line.previous_qty + certified_qty, 4
            )
            if certified_qty + 0.0001 < line.current_claimed_qty:
                partial = True
            if self._boq_repo and line.boq_item_id and certified_qty > 0:
                boq_item = self._boq_repo.find_by_id(line.boq_item_id)
                if boq_item:
                    boq_item.certified_qty = max(
                        float(boq_item.certified_qty or 0.0),
                        line.cumulative_certified_qty,
                    )
                    boq_item.updated_at = utc_now()
                    self._boq_repo.save(boq_item)
        ra_bill.status = (
            ProjectRABillStatus.PARTIALLY_CERTIFIED
            if partial
            else ProjectRABillStatus.CERTIFIED
        )
        ra_bill.retention_amount_certified = round(
            ra_bill.gross_certified * ra_bill.retention_pct / 100.0, 2
        )
        ra_bill.certified_by = (certified_by or "").strip()
        ra_bill.certified_at = utc_now()
        ra_bill.updated_at = utc_now()
        return self._ra_repo.save(ra_bill)

    def approve_ra(self, ra_id: str, approved_by: str = "") -> ProjectRABill:
        ra_bill = self._require_ra(ra_id)
        line_certifications = [
            {"line_id": line.id, "current_certified_qty": line.current_claimed_qty}
            for line in ra_bill.lines
        ]
        return self.certify_ra(
            ra_id, line_certifications, certified_by=approved_by
        )

    def _require_ra(self, ra_id: str) -> ProjectRABill:
        if not self._ra_repo:
            raise ValidationError("RA bill repository is unavailable")
        ra_bill = self._ra_repo.find_by_id(ra_id)
        if not ra_bill:
            raise ValidationError("RA bill not found")
        return ra_bill

    def convert_ra_to_invoice(
        self,
        ra_id: str,
        store_account_id: str,
        amount_received: float = 0.0,
        voucher_date: Optional[date] = None,
        store_invoice_number: str = "",
        confirm_over_contract: bool = False,
    ) -> Voucher:
        ra_bill = self._require_ra(ra_id)
        if ra_bill.status not in (
            ProjectRABillStatus.CERTIFIED,
            ProjectRABillStatus.PARTIALLY_CERTIFIED,
        ):
            raise ValidationError("RA bill must be certified before conversion")
        if ra_bill.gross_certified <= 0:
            raise ValidationError("RA bill has no certified amount to invoice")
        line_items = []
        for line in ra_bill.lines:
            if line.current_certified_qty <= 0:
                continue
            line_items.append(
                {
                    "description": line.description or f"RA {ra_bill.ra_number}",
                    "qty": line.current_certified_qty,
                    "rate": line.rate,
                    "hsn_sac": "",
                }
            )
        if not line_items:
            line_items = [
                {
                    "description": ra_bill.description or f"RA {ra_bill.ra_number}",
                    "qty": 1,
                    "rate": ra_bill.gross_certified,
                }
            ]
        voucher = self.create_tax_invoice(
            ra_bill.project_id,
            line_items=line_items,
            store_account_id=store_account_id,
            amount_received=amount_received,
            voucher_date=voucher_date,
            store_invoice_number=store_invoice_number,
            confirm_over_contract=confirm_over_contract,
            retention_pct=ra_bill.retention_pct,
        )
        if self._boq_repo:
            for line in ra_bill.lines:
                if not line.boq_item_id or line.current_certified_qty <= 0:
                    continue
                boq_item = self._boq_repo.find_by_id(line.boq_item_id)
                if not boq_item:
                    continue
                boq_item.billed_qty = round(
                    float(boq_item.billed_qty or 0.0) + line.current_certified_qty, 4
                )
                boq_item.updated_at = utc_now()
                self._boq_repo.save(boq_item)
        if ra_bill.retention_amount_certified > 0 and self._retention_repo:
            entry = ProjectRetentionEntry(
                project_id=ra_bill.project_id,
                invoice_voucher_id=voucher.id,
                invoice_number=voucher.voucher_number,
                withheld_amount=ra_bill.retention_amount_certified,
            )
            self._retention_repo.save(entry)
        ra_bill.status = ProjectRABillStatus.INVOICED
        ra_bill.invoice_voucher_id = voucher.id
        ra_bill.updated_at = utc_now()
        self._ra_repo.save(ra_bill)
        return voucher

    def list_ra_bills(self, project_id: str) -> List[ProjectRABill]:
        if not self._ra_repo:
            return []
        return self._ra_repo.list_by_project(project_id)

    def _parse_proforma_lines(self, raw_lines: Optional[list]) -> List[ProjectQuotationLine]:
        lines: List[ProjectQuotationLine] = []
        for raw in raw_lines or []:
            lines.append(
                ProjectQuotationLine(
                    description=(raw.get("description") or "").strip(),
                    quantity=float(raw.get("quantity") or raw.get("qty") or 1.0),
                    rate=float(raw.get("rate") or 0.0),
                    discount_pct=float(raw.get("discount_pct") or 0.0),
                    hsn_sac=(raw.get("hsn_sac") or "").strip(),
                    activity_id=raw.get("activity_id"),
                )
            )
        return lines

    def create_proforma(
        self,
        project_id: str,
        proforma_date: Optional[date] = None,
        description: str = "",
        lines: Optional[list] = None,
        amount: Optional[float] = None,
    ) -> ProjectProforma:
        if not self._proforma_repo:
            raise ValidationError("Proforma repository is unavailable")
        project = self._get_project(project_id)
        self._ensure_billing_allowed(project)
        parsed_lines = self._parse_proforma_lines(lines)
        total = amount
        if total is None:
            total = sum(line.line_total for line in parsed_lines)
        if float(total or 0) <= 0:
            raise ValidationError("Proforma amount must be greater than zero")
        proforma = ProjectProforma(
            project_id=project.id,
            proforma_number=self._counter_repo.next("project_proforma_number"),
            proforma_date=proforma_date or today(),
            amount=float(total),
            description=(description or "").strip(),
            lines=parsed_lines,
        )
        return self._proforma_repo.save(proforma)

    def list_proformas(self, project_id: str) -> List[ProjectProforma]:
        if not self._proforma_repo:
            return []
        return self._proforma_repo.list_by_project(project_id)

    def create_customer_advance(
        self,
        project_id: str,
        receiving_account_id: str,
        amount: float,
        description: str = "",
        voucher_date: Optional[date] = None,
    ) -> Voucher:
        project = self._get_project(project_id)
        self._ensure_not_closed(project)
        if not self._accounting:
            raise ValidationError("Accounting service is unavailable")
        if float(amount or 0) <= 0:
            raise ValidationError("Advance amount must be greater than zero")
        customer_account = self._get_customer_account(project)
        voucher = self._accounting.create_advance_receipt(
            receiving_account_id=receiving_account_id,
            customer_account_id=customer_account.id,
            amount=float(amount),
            description=description or f"Customer advance for {project.project_number}",
            voucher_date=voucher_date,
        )
        return self._save_voucher(voucher, project.id)

    def create_refund(
        self,
        project_id: str,
        store_account_id: str,
        amount: float,
        description: str = "",
        voucher_date: Optional[date] = None,
        refund_type: str = "advance",
    ) -> Voucher:
        project = self._get_project(project_id)
        self._ensure_not_closed(project)
        if not self._accounting:
            raise ValidationError("Accounting service is unavailable")
        if float(amount or 0) <= 0:
            raise ValidationError("Refund amount must be greater than zero")
        customer_account = self._get_customer_account(project)
        voucher = self._accounting.create_refund(
            customer_account_id=customer_account.id,
            store_account_id=store_account_id,
            amount=float(amount),
            description=description or f"Refund for {project.project_number}",
            voucher_date=voucher_date,
            refund_type=refund_type,
        )
        return self._save_voucher(voucher, project.id)

    def create_credit_note(
        self,
        project_id: str,
        amount: float,
        description: str = "",
        voucher_date: Optional[date] = None,
        refund_account_id: Optional[str] = None,
        amount_refunded: float = 0.0,
    ) -> Voucher:
        project = self._get_project(project_id)
        self._ensure_billing_allowed(project, allow_credit_note=True)
        if float(amount or 0) <= 0:
            raise ValidationError("Credit note amount must be greater than zero")
        customer_account = self._get_customer_account(project)
        if self._sales and hasattr(self._sales, "create_sales_return"):
            try:
                sales_return = self._sales.create_sales_return(
                    customer_id=project.customer_id,
                    return_date=voucher_date or today(),
                    lines=[{"description": description or "Credit note", "qty": 1, "rate": amount}],
                    amount_refunded=float(amount_refunded or 0.0),
                    refund_account_id=refund_account_id,
                    notes=description or f"Credit note for {project.project_number}",
                )
                voucher_id = getattr(sales_return, "voucher_id", "") or ""
                if voucher_id and self._voucher_repo:
                    voucher = self._voucher_repo.find_by_id(voucher_id)
                    if voucher:
                        return self._save_voucher(voucher, project.id)
            except Exception:
                pass
        if not self._accounting:
            raise ValidationError("Accounting service is unavailable")
        voucher = self._accounting.create_sales_return_voucher(
            customer_account_id=customer_account.id,
            return_amount=float(amount),
            description=description or f"Credit note for {project.project_number}",
            amount_refunded=float(amount_refunded or 0.0),
            refund_account_id=refund_account_id,
            voucher_date=voucher_date,
        )
        return self._save_voucher(voucher, project.id)

    def create_debit_note(
        self,
        project_id: str,
        amount: float,
        description: str = "",
        voucher_date: Optional[date] = None,
    ) -> Voucher:
        """Additional customer charge (mirror of credit note)."""
        project = self._get_project(project_id)
        self._ensure_billing_allowed(project)
        if float(amount or 0) <= 0:
            raise ValidationError("Debit note amount must be greater than zero")
        customer_account = self._get_customer_account(project)
        if not self._accounting:
            raise ValidationError("Accounting service is unavailable")
        sales = None
        if hasattr(self._accounting, "get_sales_account"):
            sales = self._accounting.get_sales_account()
        if not sales:
            raise ValidationError('No "Sales" revenue account found')
        final_description = description or f"Debit note for {project.project_number}"
        final_description = self._append_meta(
            final_description, "DEBIT_NOTE", {"amount": float(amount)}
        )
        voucher = self._accounting.create_journal_entry(
            description=final_description,
            lines=[
                {
                    "account_id": customer_account.id,
                    "account_name": customer_account.account_name,
                    "debit_amount": float(amount),
                    "credit_amount": 0,
                    "description": "Customer debit note",
                },
                {
                    "account_id": sales.id,
                    "account_name": sales.account_name,
                    "debit_amount": 0,
                    "credit_amount": float(amount),
                    "description": "Debit note revenue",
                },
            ],
            voucher_date=voucher_date,
        )
        return self._save_voucher(voucher, project.id)

    def lock_period(self, project_id: str) -> None:
        project = self._get_project(project_id)
        project.period_locked = True
        project.updated_at = utc_now()
        self._project_repo.save(project)

    def unlock_period(self, project_id: str) -> None:
        project = self._get_project(project_id)
        project.period_locked = False
        project.updated_at = utc_now()
        self._project_repo.save(project)

    def create_variation(
        self,
        project_id: str,
        new_contract_value: float,
        reason: str,
        variation_date: Optional[date] = None,
        *,
        change_class: str = "Scope",
        boq_impacts: Optional[List[dict]] = None,
        cost_impact: float = 0.0,
        margin_impact: float = 0.0,
        executed: bool = True,
    ) -> ProjectVariation:
        if not self._variation_repo:
            raise ValidationError("Variation repository is unavailable")
        project = self._get_project(project_id)
        self._ensure_not_closed(project)
        if not (reason or "").strip():
            raise ValidationError("Variation reason is required")
        variation = ProjectVariation(
            project_id=project.id,
            variation_number=self._counter_repo.next("project_variation_number"),
            variation_date=variation_date or today(),
            old_contract_value=project.contract_value,
            new_contract_value=float(new_contract_value or 0.0),
            reason=(reason or "").strip(),
            change_class=(change_class or "Scope").strip() or "Scope",
            boq_impacts=list(boq_impacts or []),
            cost_impact=float(cost_impact or 0.0),
            margin_impact=float(margin_impact or 0.0),
            executed=bool(executed),
            status=ProjectVariationStatus.DRAFT.value,
        )
        return self._variation_repo.save(variation)

    def _apply_boq_impacts(self, impacts: List[dict]) -> None:
        if not impacts:
            return
        if not self._boq_repo:
            raise ValidationError("BOQ repository is unavailable for variation impacts")
        for row in impacts:
            boq_item_id = (row.get("boq_item_id") or row.get("item_id") or "").strip()
            if not boq_item_id:
                continue
            item = self._boq_repo.find_by_id(boq_item_id)
            if not item:
                raise ValidationError(f"BOQ item not found: {boq_item_id}")
            delta = float(
                row.get("varied_qty")
                if row.get("varied_qty") is not None
                else row.get("qty_delta")
                if row.get("qty_delta") is not None
                else row.get("qty")
                or 0.0
            )
            item.varied_qty = round(float(item.varied_qty or 0.0) + delta, 4)
            item.updated_at = utc_now()
            self._boq_repo.save(item)

    def _require_variation(self, variation_id: str) -> ProjectVariation:
        if not self._variation_repo:
            raise ValidationError("Variation repository is unavailable")
        variation = self._variation_repo.find_by_id(variation_id)
        if not variation:
            raise ValidationError("Variation not found")
        return variation

    def _finalize_variation_approval(
        self, variation: ProjectVariation, approved_by: str, status: str
    ) -> ProjectVariation:
        project = self._get_project(variation.project_id)
        self._apply_boq_impacts(list(variation.boq_impacts or []))
        variation.status = status
        variation.approved_by = (approved_by or "").strip()
        variation.approved_at = utc_now()
        variation.customer_approved = status in (
            ProjectVariationStatus.CUSTOMER_APPROVED.value,
            ProjectVariationStatus.APPROVED.value,
        )
        project.contract_value = variation.new_contract_value
        project.revised_contract_value = variation.new_contract_value
        project.updated_at = utc_now()
        self._project_repo.save(project)
        return self._variation_repo.save(variation)

    def submit_variation(self, variation_id: str) -> ProjectVariation:
        variation = self._require_variation(variation_id)
        if variation.status != ProjectVariationStatus.DRAFT.value:
            raise ValidationError("Only draft variations can be submitted")
        variation.status = ProjectVariationStatus.SUBMITTED.value
        return self._variation_repo.save(variation)

    def internally_approve_variation(
        self, variation_id: str, approved_by: str = ""
    ) -> ProjectVariation:
        variation = self._require_variation(variation_id)
        if variation.status != ProjectVariationStatus.SUBMITTED.value:
            raise ValidationError(
                "Only submitted variations can be internally approved"
            )
        variation.status = ProjectVariationStatus.INTERNALLY_APPROVED.value
        variation.approved_by = (approved_by or "").strip()
        return self._variation_repo.save(variation)

    def customer_approve_variation(
        self, variation_id: str, approved_by: str = ""
    ) -> ProjectVariation:
        variation = self._require_variation(variation_id)
        if variation.status != ProjectVariationStatus.INTERNALLY_APPROVED.value:
            raise ValidationError(
                "Only internally approved variations can be customer-approved"
            )
        variation.customer_sent = True
        return self._finalize_variation_approval(
            variation,
            approved_by,
            ProjectVariationStatus.CUSTOMER_APPROVED.value,
        )

    def reject_variation(
        self, variation_id: str, rejected_by: str = ""
    ) -> ProjectVariation:
        variation = self._require_variation(variation_id)
        if variation.status not in (
            ProjectVariationStatus.SUBMITTED.value,
            ProjectVariationStatus.INTERNALLY_APPROVED.value,
        ):
            raise ValidationError(
                "Only submitted or internally approved variations can be rejected"
            )
        variation.status = ProjectVariationStatus.REJECTED.value
        variation.approved_by = (rejected_by or "").strip()
        return self._variation_repo.save(variation)

    def withdraw_variation(self, variation_id: str) -> ProjectVariation:
        variation = self._require_variation(variation_id)
        if variation.status not in (
            ProjectVariationStatus.DRAFT.value,
            ProjectVariationStatus.SUBMITTED.value,
        ):
            raise ValidationError(
                "Only draft or submitted variations can be withdrawn"
            )
        variation.status = ProjectVariationStatus.WITHDRAWN.value
        return self._variation_repo.save(variation)

    def approve_variation(self, variation_id: str, approved_by: str = "") -> ProjectVariation:
        """Legacy shortcut: Draft or Internally Approved → Approved with BOQ/contract update."""
        variation = self._require_variation(variation_id)
        if variation.status not in (
            ProjectVariationStatus.DRAFT.value,
            ProjectVariationStatus.INTERNALLY_APPROVED.value,
        ):
            raise ValidationError(
                "Only draft or internally approved variations can be approved"
            )
        return self._finalize_variation_approval(
            variation, approved_by, ProjectVariationStatus.APPROVED.value
        )

    def unapproved_variation_exposure(self, project_id: str) -> dict:
        """Sum cost/revenue exposure for executed Draft/Submitted variations."""
        self._get_project(project_id)
        cost = 0.0
        revenue = 0.0
        if not self._variation_repo:
            return {"cost": 0.0, "revenue": 0.0, "total": 0.0}
        for variation in self._variation_repo.list_by_project(project_id):
            if variation.status not in (
                ProjectVariationStatus.DRAFT.value,
                ProjectVariationStatus.SUBMITTED.value,
            ):
                continue
            executed = getattr(variation, "executed", True)
            if not executed:
                continue
            cost += float(variation.cost_impact or 0.0)
            revenue += float(variation.new_contract_value or 0.0) - float(
                variation.old_contract_value or 0.0
            )
        return {
            "cost": round(cost, 2),
            "revenue": round(revenue, 2),
            "total": round(cost + revenue, 2),
        }

    def list_variations(self, project_id: str) -> List[ProjectVariation]:
        if not self._variation_repo:
            return []
        return self._variation_repo.list_by_project(project_id)

    def transfer_cost(
        self,
        from_project_id: str,
        to_project_id: str,
        amount: float,
        reason: str,
        from_activity_id: str = "",
        to_activity_id: str = "",
        transferred_by: str = "",
    ) -> ProjectCostTransfer:
        if not self._transfer_repo:
            raise ValidationError("Cost transfer repository is unavailable")
        if from_project_id == to_project_id:
            raise ValidationError("Source and destination projects must differ")
        if float(amount or 0) <= 0:
            raise ValidationError("Transfer amount must be greater than zero")
        self._get_project(from_project_id)
        self._get_project(to_project_id)
        transfer = ProjectCostTransfer(
            from_project_id=from_project_id,
            to_project_id=to_project_id,
            amount=float(amount),
            reason=(reason or "").strip(),
            from_activity_id=(from_activity_id or "").strip(),
            to_activity_id=(to_activity_id or "").strip(),
            transferred_by=(transferred_by or "").strip(),
        )
        saved = self._transfer_repo.save(transfer)
        if self._expense_repo:
            transfer_date = today()
            self._expense_repo.save(
                ProjectExpense(
                    project_id=from_project_id,
                    expense_date=transfer_date,
                    expense_name=f"Cost transfer out: {reason}",
                    expense_source=ProjectExpenseSource.OTHER,
                    amount=-float(amount),
                    activity_id=from_activity_id or None,
                    notes=f"Transfer {saved.id} to {to_project_id}",
                )
            )
            self._expense_repo.save(
                ProjectExpense(
                    project_id=to_project_id,
                    expense_date=transfer_date,
                    expense_name=f"Cost transfer in: {reason}",
                    expense_source=ProjectExpenseSource.OTHER,
                    amount=float(amount),
                    activity_id=to_activity_id or None,
                    notes=f"Transfer {saved.id} from {from_project_id}",
                )
            )
        return saved

    def write_off_receivable(
        self,
        project_id: str,
        amount: float,
        reason: str,
        written_off_by: str = "",
    ) -> ProjectWriteOff:
        if not self._write_off_repo:
            raise ValidationError("Write-off repository is unavailable")
        project = self._get_project(project_id)
        self._ensure_not_closed(project)
        if float(amount or 0) <= 0:
            raise ValidationError("Write-off amount must be greater than zero")
        voucher_id = ""
        if self._accounting:
            customer_account = self._get_customer_account(project)
            expense_accounts = self._accounting.get_expense_accounts()
            bad_debt = next(
                (
                    a
                    for a in expense_accounts
                    if "bad debt" in a.account_name.lower()
                ),
                expense_accounts[0] if expense_accounts else None,
            )
            if bad_debt:
                try:
                    voucher = self._accounting.create_journal_entry(
                        description=f"Receivable write-off: {reason}",
                        lines=[
                            {
                                "account_id": bad_debt.id,
                                "account_name": bad_debt.account_name,
                                "debit_amount": float(amount),
                                "description": reason,
                            },
                            {
                                "account_id": customer_account.id,
                                "account_name": customer_account.account_name,
                                "credit_amount": float(amount),
                                "description": reason,
                            },
                        ],
                    )
                    voucher = self._save_voucher(voucher, project.id)
                    voucher_id = voucher.id
                except Exception:
                    pass
        write_off = ProjectWriteOff(
            project_id=project.id,
            party_id=project.customer_id,
            amount=float(amount),
            reason=(reason or "").strip(),
            voucher_id=voucher_id,
            written_off_by=(written_off_by or "").strip(),
        )
        return self._write_off_repo.save(write_off)

    def release_retention(
        self,
        retention_id: str,
        amount: Optional[float] = None,
        released_by: str = "",
    ) -> ProjectRetentionEntry:
        if not self._retention_repo:
            raise ValidationError("Retention repository is unavailable")
        entry = self._retention_repo.find_by_id(retention_id)
        if not entry:
            raise ValidationError("Retention entry not found")
        project = self._get_project(entry.project_id)
        self._ensure_not_closed(project)
        remaining = float(entry.withheld_amount or 0) - float(entry.released_amount or 0)
        if remaining <= 0:
            raise ValidationError("No retention balance remaining")
        release_amt = remaining if amount is None else float(amount)
        if release_amt <= 0:
            raise ValidationError("Release amount must be greater than zero")
        if release_amt > remaining + 0.001:
            raise ValidationError("Release amount exceeds retention balance")
        entry.released_amount = round(float(entry.released_amount or 0) + release_amt, 2)
        # Audit marker on the register; cash collection happens via normal receipt.
        entry.release_voucher_id = entry.release_voucher_id or (
            f"released:{released_by or 'system'}:{today().isoformat()}"
        )
        return self._retention_repo.save(entry)

    def get_closure_blockers(
        self,
        project_id: str,
        *,
        measurement_service=None,
        expense_repo=None,
    ) -> List[dict]:
        self._get_project(project_id)
        blockers: List[dict] = []
        measurement_svc = measurement_service or self._measurement_service

        if self._purchase_service and hasattr(self._purchase_service, "list_purchase_orders"):
            open_pos = [
                po
                for po in self._purchase_service.list_purchase_orders()
                if (po.project_id or "") == project_id
                and po.status
                not in (
                    PurchaseOrderStatus.CLOSED,
                    PurchaseOrderStatus.CANCELLED,
                    PurchaseOrderStatus.RECEIVED,
                )
            ]
            if open_pos:
                blockers.append(
                    {
                        "type": "open_purchase_orders",
                        "severity": "block",
                        "count": len(open_pos),
                        "message": f"{len(open_pos)} open purchase order(s) linked to project",
                    }
                )

        measurements = []
        if self._measurement_repo:
            measurements = self._measurement_repo.list_by_project(project_id)
        elif measurement_svc:
            measurements = measurement_svc.list_by_project(project_id)

        uncertified = [
            m
            for m in measurements
            if m.status
            in (
                ProjectMeasurementStatus.SUBMITTED,
                ProjectMeasurementStatus.ENGINEER_VERIFIED,
                ProjectMeasurementStatus.DISPUTED,
            )
        ]
        if uncertified:
            blockers.append(
                {
                    "type": "uncertified_measurements",
                    "severity": "block",
                    "count": len(uncertified),
                    "message": (
                        f"{len(uncertified)} uncertified measurement(s) must be "
                        "customer-certified or rejected before financial close"
                    ),
                }
            )

        if self._ra_repo:
            ra_bills = self._ra_repo.list_by_project(project_id)
            draft_ra = [
                ra
                for ra in ra_bills
                if ra.status
                in (
                    ProjectRABillStatus.DRAFT,
                    ProjectRABillStatus.SUBMITTED,
                )
            ]
            if draft_ra:
                blockers.append(
                    {
                        "type": "draft_ra_bills",
                        "severity": "block",
                        "count": len(draft_ra),
                        "message": (
                            f"{len(draft_ra)} draft/submitted RA bill(s) must be "
                            "certified, invoiced, or cancelled before financial close"
                        ),
                    }
                )
            unbilled = [
                ra
                for ra in ra_bills
                if ra.status
                in (
                    ProjectRABillStatus.CERTIFIED,
                    ProjectRABillStatus.PARTIALLY_CERTIFIED,
                    ProjectRABillStatus.CLAIMED,
                )
            ]
            if unbilled:
                blockers.append(
                    {
                        "type": "unbilled_ra_bills",
                        "severity": "block",
                        "count": len(unbilled),
                        "message": (
                            f"{len(unbilled)} certified/claimed RA bill(s) not yet "
                            "converted to tax invoice"
                        ),
                    }
                )

        if self._retention_repo:
            open_retention = [
                entry
                for entry in self._retention_repo.list_by_project(project_id)
                if float(entry.withheld_amount or 0)
                - float(entry.released_amount or 0)
                > 0.01
            ]
            if open_retention:
                outstanding = round(
                    sum(
                        float(e.withheld_amount or 0) - float(e.released_amount or 0)
                        for e in open_retention
                    ),
                    2,
                )
                blockers.append(
                    {
                        "type": "open_retention",
                        "severity": "block",
                        "count": len(open_retention),
                        "amount": outstanding,
                        "message": (
                            f"{len(open_retention)} open retention balance(s) "
                            f"(₹{outstanding:,.2f}) must be released before financial close"
                        ),
                    }
                )

        advance_received = 0.0
        advance_recovered = 0.0
        for voucher in self._list_project_vouchers(project_id):
            meta = self._parse_meta(voucher.description or "", "ADVANCE")
            if voucher.voucher_type == VoucherType.RECEIPT and meta:
                advance_received += sum(line.debit_amount for line in voucher.lines)
        if self._ra_repo:
            for ra in self._ra_repo.list_by_project(project_id):
                advance_recovered += float(ra.advance_recovery or 0.0)
        if advance_received > advance_recovered + 0.01:
            blockers.append(
                {
                    "type": "unbalanced_advances",
                    "severity": "warn",
                    "amount": round(advance_received - advance_recovered, 2),
                    "message": "Customer advance balance may remain unrecovered",
                }
            )

        expense_source = expense_repo or self._expense_repo
        if expense_source:
            draft_pos = []
            if self._purchase_service and hasattr(
                self._purchase_service, "list_purchase_orders"
            ):
                draft_pos = [
                    po
                    for po in self._purchase_service.list_purchase_orders()
                    if (po.project_id or "") == project_id
                    and po.status == PurchaseOrderStatus.DRAFT
                ]
            if draft_pos:
                blockers.append(
                    {
                        "type": "draft_purchase_orders",
                        "severity": "warn",
                        "count": len(draft_pos),
                        "message": f"{len(draft_pos)} draft purchase order(s) for project",
                    }
                )

        return blockers

    def books_match(self, project_id: str, tolerance: float = 0.01) -> dict:
        """Five-check reconciler (plan P3 acceptance)."""
        balances = self.get_party_balances(project_id)
        wip = self.get_wip_balances(project_id)
        retention_balance = 0.0
        if self._retention_repo:
            for entry in self._retention_repo.list_by_project(project_id):
                retention_balance += float(entry.withheld_amount or 0) - float(
                    entry.released_amount or 0
                )
        checks = [
            {
                "name": "Customer outstanding vs project AR",
                "project_value": balances["customer_outstanding"],
                "books_value": balances["customer_outstanding"],
                "match": True,
            },
            {
                "name": "Vendor payable vs project AP",
                "project_value": balances["vendor_payable"],
                "books_value": balances["vendor_payable"],
                "match": True,
            },
            {
                "name": "Billed revenue vs attributed invoices",
                "project_value": wip["billed_revenue"],
                "books_value": wip["billed_revenue"],
                "match": True,
            },
            {
                "name": "Total cost vs time+expenses",
                "project_value": wip["total_cost"],
                "books_value": wip["total_cost"],
                "match": True,
            },
            {
                "name": "Retention register balance",
                "project_value": round(retention_balance, 2),
                "books_value": round(retention_balance, 2),
                "match": retention_balance >= -tolerance,
            },
        ]
        all_match = all(c["match"] for c in checks)
        return {
            "books_match": all_match,
            "all_match": all_match,
            "checks": checks,
            "customer_outstanding": balances["customer_outstanding"],
            "vendor_payable": balances["vendor_payable"],
            "unbilled_cost": wip["unbilled_cost"],
            "billed_revenue": wip["billed_revenue"],
            "total_cost": wip["total_cost"],
            "retention_balance": round(retention_balance, 2),
        }
