from __future__ import annotations

import json
import re
from typing import Dict, List, Optional

from vaybooks.bms.application.projects.profitability.service import (
    ProjectProfitabilityService,
)
from vaybooks.bms.domain.projects.repository import (
    ProjectBoqRepository,
    ProjectBudgetRepository,
    ProjectDocumentRepository,
    ProjectExpenseRepository,
    ProjectMeasurementRepository,
    ProjectQuotationRepository,
    ProjectRepository,
    ProjectRetentionRepository,
    ProjectRABillRepository,
    ProjectCostTransferRepository,
    ProjectVariationRepository,
    ProjectWriteOffRepository,
    ProjectTimeEntryRepository,
)
from vaybooks.bms.domain.finance.accounting.repository import VoucherRepository
from vaybooks.bms.domain.finance.accounting.sales_parsing import sales_amounts_from_lines
from vaybooks.bms.domain.shared.enums import ProjectStatus, VoucherType
from vaybooks.bms.domain.shared.exceptions import ValidationError


class ProjectReportService:
    def __init__(
        self,
        project_repo: ProjectRepository,
        time_repo: ProjectTimeEntryRepository,
        expense_repo: ProjectExpenseRepository,
        profitability_service: Optional[ProjectProfitabilityService] = None,
        quotation_repo: Optional[ProjectQuotationRepository] = None,
        document_repo: Optional[ProjectDocumentRepository] = None,
        voucher_repo: Optional[VoucherRepository] = None,
        ra_repo: Optional[ProjectRABillRepository] = None,
        retention_repo: Optional[ProjectRetentionRepository] = None,
        transfer_repo: Optional[ProjectCostTransferRepository] = None,
        write_off_repo: Optional[ProjectWriteOffRepository] = None,
        variation_repo: Optional[ProjectVariationRepository] = None,
        boq_repo: Optional[ProjectBoqRepository] = None,
        budget_repo: Optional[ProjectBudgetRepository] = None,
        measurement_repo: Optional[ProjectMeasurementRepository] = None,
        billing_service=None,
        purchase_service=None,
    ):
        self._project_repo = project_repo
        self._time_repo = time_repo
        self._expense_repo = expense_repo
        self._quotation_repo = quotation_repo
        self._document_repo = document_repo
        self._voucher_repo = voucher_repo
        self._ra_repo = ra_repo
        self._retention_repo = retention_repo
        self._transfer_repo = transfer_repo
        self._write_off_repo = write_off_repo
        self._variation_repo = variation_repo
        self._boq_repo = boq_repo
        self._budget_repo = budget_repo
        self._measurement_repo = measurement_repo
        self._billing = billing_service
        self._purchase = purchase_service
        self._profitability = profitability_service or ProjectProfitabilityService(
            project_repo,
            time_repo,
            expense_repo,
        )

    def portfolio_summary(
        self,
        status: Optional[ProjectStatus] = None,
        billed_by_project: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> List[dict]:
        return self._profitability.portfolio_summary(
            status=status,
            billed_by_project=billed_by_project,
        )

    def activity_profitability(
        self,
        project_id: str,
        billed_by_activity: Optional[Dict[str, float]] = None,
    ) -> List[dict]:
        profitability = self._profitability.get_project_profitability(
            project_id,
            billed_by_activity=billed_by_activity,
        )
        return [
            {
                "activity_id": row.activity_id,
                "activity_name": row.activity_name,
                "parent_activity_id": row.parent_activity_id,
                "person_hours": row.person_hours,
                "labour_cost": row.labour_cost,
                "other_cost": row.other_cost,
                "total_cost": row.total_cost,
                "planned_revenue": row.planned_revenue,
                "billed_revenue": row.billed_revenue,
                "budget_margin": row.budget_margin,
                "budget_mph": row.budget_mph,
                "billed_margin": row.billed_margin,
                "billed_mph": row.billed_mph,
            }
            for row in profitability.activity_rows
        ]

    def man_hours_by_worker(self, project_id: str) -> List[dict]:
        if not self._project_repo.find_by_id(project_id):
            raise ValidationError("Project not found")
        totals: Dict[str, dict] = {}
        for entry in self._time_repo.list_by_project(project_id):
            bucket = totals.setdefault(
                entry.worker_id or entry.worker_name,
                {
                    "worker_id": entry.worker_id,
                    "worker_name": entry.worker_name,
                    "person_hours": 0.0,
                    "labour_cost": 0.0,
                },
            )
            bucket["person_hours"] += entry.duration_minutes / 60.0
            bucket["labour_cost"] += entry.labour_cost
        rows = list(totals.values())
        for row in rows:
            row["person_hours"] = round(row["person_hours"], 2)
            row["labour_cost"] = round(row["labour_cost"], 2)
        return sorted(rows, key=lambda r: r["worker_name"])

    def unallocated_costs(self, project_id: str) -> dict:
        if not self._project_repo.find_by_id(project_id):
            raise ValidationError("Project not found")
        expenses = self._expense_repo.list_by_project(project_id)
        unallocated = [e for e in expenses if not e.activity_id]
        total = sum(e.amount for e in unallocated)
        return {
            "project_id": project_id,
            "unallocated_cost": round(total, 2),
            "expense_count": len(unallocated),
            "expenses": [
                {
                    "expense_id": e.id,
                    "expense_date": e.expense_date,
                    "expense_name": e.expense_name,
                    "amount": e.amount,
                    "vendor_name": e.vendor_name,
                }
                for e in unallocated
            ],
        }

    def _project_vouchers(self, project_id: str):
        if self._billing:
            return self._billing._list_project_vouchers(project_id)
        if self._voucher_repo:
            return self._voucher_repo.list_by_project(project_id)
        return []

    def billing_register(self, project_id: str) -> dict:
        project = self._project_repo.find_by_id(project_id)
        if not project:
            raise ValidationError("Project not found")
        rows = []
        for voucher in self._project_vouchers(project_id):
            if voucher.voucher_type not in (
                VoucherType.SALES_INVOICE,
                VoucherType.RECEIPT,
                VoucherType.SALES_RETURN,
                VoucherType.ADVANCE,
                VoucherType.REFUND,
            ):
                continue
            amounts = sales_amounts_from_lines(voucher.lines)
            rows.append(
                {
                    "voucher_id": voucher.id,
                    "voucher_number": voucher.voucher_number,
                    "voucher_type": voucher.voucher_type.value,
                    "voucher_date": voucher.voucher_date,
                    "description": voucher.description,
                    "gross": amounts.get("gross", 0.0),
                    "net": amounts.get("net", 0.0),
                    "collected": amounts.get("collected", 0.0),
                    "outstanding": amounts.get("outstanding", 0.0),
                }
            )
        rows.sort(key=lambda r: r.get("voucher_date") or "", reverse=True)
        return {
            "project_id": project.id,
            "project_number": project.project_number,
            "rows": rows,
            "total_invoiced": round(
                sum(r["net"] for r in rows if r["voucher_type"] == VoucherType.SALES_INVOICE.value),
                2,
            ),
        }

    def customer_outstanding(self, project_id: str) -> dict:
        if self._billing:
            balances = self._billing.get_party_balances(project_id)
            return {
                "project_id": project_id,
                "customer_outstanding": balances["customer_outstanding"],
            }
        return {"project_id": project_id, "customer_outstanding": 0.0}

    def vendor_payables(self, project_id: str) -> dict:
        if self._billing:
            balances = self._billing.get_party_balances(project_id)
            return {
                "project_id": project_id,
                "vendor_payable": balances["vendor_payable"],
            }
        return {"project_id": project_id, "vendor_payable": 0.0}

    def wip_unbilled(self, project_id: str) -> dict:
        if self._billing:
            return self._billing.get_wip_balances(project_id)
        project = self._project_repo.find_by_id(project_id)
        if not project:
            raise ValidationError("Project not found")
        return {"project_id": project_id, "unbilled_cost": 0.0}

    def retention_register(self, project_id: str) -> List[dict]:
        if not self._retention_repo:
            return []
        if not self._project_repo.find_by_id(project_id):
            raise ValidationError("Project not found")
        return [
            {
                "entry_id": entry.id,
                "invoice_voucher_id": entry.invoice_voucher_id,
                "invoice_number": entry.invoice_number,
                "withheld_amount": entry.withheld_amount,
                "released_amount": entry.released_amount,
                "outstanding_retention": round(
                    entry.withheld_amount - entry.released_amount, 2
                ),
                "created_at": entry.created_at,
            }
            for entry in self._retention_repo.list_by_project(project_id)
        ]

    def collections_outstanding(self, project_id: str) -> dict:
        outstanding = self.customer_outstanding(project_id)["customer_outstanding"]
        receipts = 0.0
        for voucher in self._project_vouchers(project_id):
            if voucher.voucher_type == VoucherType.RECEIPT:
                receipts += sum(line.debit_amount for line in voucher.lines)
        return {
            "project_id": project_id,
            "customer_outstanding": outstanding,
            "total_receipts": round(receipts, 2),
        }

    def po_committed(self, project_id: str) -> List[dict]:
        if not self._project_repo.find_by_id(project_id):
            raise ValidationError("Project not found")
        if not self._purchase:
            return []
        from vaybooks.bms.domain.shared.enums import PurchaseOrderStatus

        rows: List[dict] = []
        for po in self._purchase.list_purchase_orders():
            if getattr(po, "project_id", "") != project_id:
                continue
            if po.status in (
                PurchaseOrderStatus.CLOSED,
                PurchaseOrderStatus.CANCELLED,
                PurchaseOrderStatus.RECEIVED,
            ):
                continue
            open_amount = 0.0
            for line in po.lines:
                pending = getattr(line, "qty_pending", None)
                if pending is None:
                    pending = max(
                        float(line.qty_ordered or 0) - float(line.qty_received or 0),
                        0.0,
                    )
                open_amount += float(pending) * float(line.rate or 0)
            rows.append(
                {
                    "po_id": po.id,
                    "po_number": po.po_number,
                    "vendor_name": po.vendor_name,
                    "status": po.status.value,
                    "open_amount": round(open_amount, 2),
                    "expected_date": po.expected_date,
                    "order_date": po.order_date,
                }
            )
        return rows

    def transfers(self, project_id: str) -> List[dict]:
        if not self._transfer_repo:
            return []
        if not self._project_repo.find_by_id(project_id):
            raise ValidationError("Project not found")
        return [
            {
                "transfer_id": t.id,
                "from_project_id": t.from_project_id,
                "to_project_id": t.to_project_id,
                "amount": t.amount,
                "reason": t.reason,
                "from_activity_id": t.from_activity_id,
                "to_activity_id": t.to_activity_id,
                "transferred_by": t.transferred_by,
                "created_at": t.created_at,
            }
            for t in self._transfer_repo.list_by_project(project_id)
        ]

    def write_offs(self, project_id: str) -> List[dict]:
        if not self._write_off_repo:
            return []
        if not self._project_repo.find_by_id(project_id):
            raise ValidationError("Project not found")
        return [
            {
                "write_off_id": w.id,
                "party_id": w.party_id,
                "amount": w.amount,
                "reason": w.reason,
                "voucher_id": w.voucher_id,
                "written_off_by": w.written_off_by,
                "created_at": w.created_at,
            }
            for w in self._write_off_repo.list_by_project(project_id)
        ]

    def tds_deducted(self, project_id: str) -> List[dict]:
        if not self._project_repo.find_by_id(project_id):
            raise ValidationError("Project not found")
        rows = []
        pattern = re.compile(r"\n<!--TDS:(\{.*?\})-->", re.DOTALL)
        for voucher in self._project_vouchers(project_id):
            if voucher.voucher_type != VoucherType.VENDOR_PAYMENT:
                continue
            match = pattern.search(voucher.description or "")
            if not match:
                continue
            try:
                payload = json.loads(match.group(1))
            except json.JSONDecodeError:
                continue
            rows.append(
                {
                    "voucher_id": voucher.id,
                    "voucher_number": voucher.voucher_number,
                    "voucher_date": voucher.voucher_date,
                    "tds_section": payload.get("section", ""),
                    "tds_rate": payload.get("rate", 0.0),
                    "tds_amount": payload.get("amount", 0.0),
                    "gross_amount": payload.get("gross_amount", 0.0),
                }
            )
        return rows

    def at_risk(self, project_id: Optional[str] = None) -> List[dict]:
        projects = (
            [self._project_repo.find_by_id(project_id)]
            if project_id
            else self._project_repo.list_all()
        )
        rows = []
        for project in projects:
            if not project or project.status in (
                ProjectStatus.FINANCIALLY_CLOSED,
                ProjectStatus.CANCELLED,
            ):
                continue
            wip = self.wip_unbilled(project.id)
            outstanding = self.customer_outstanding(project.id)
            over_contract = (
                project.contract_value > 0
                and wip.get("billed_revenue", 0) > project.contract_value
            )
            high_unbilled = wip.get("unbilled_cost", 0) > project.contract_value * 0.1
            if over_contract or high_unbilled or outstanding["customer_outstanding"] > 0:
                rows.append(
                    {
                        "project_id": project.id,
                        "project_number": project.project_number,
                        "contract_value": project.contract_value,
                        "billed_revenue": wip.get("billed_revenue", 0.0),
                        "unbilled_cost": wip.get("unbilled_cost", 0.0),
                        "customer_outstanding": outstanding["customer_outstanding"],
                        "over_contract": over_contract,
                        "high_unbilled": high_unbilled,
                    }
                )
        return rows

    def variations_log(self, project_id: str) -> List[dict]:
        if not self._variation_repo:
            return []
        if not self._project_repo.find_by_id(project_id):
            raise ValidationError("Project not found")
        return [
            {
                "variation_id": v.id,
                "variation_number": v.variation_number,
                "variation_date": v.variation_date,
                "old_contract_value": v.old_contract_value,
                "new_contract_value": v.new_contract_value,
                "delta": round(v.new_contract_value - v.old_contract_value, 2),
                "reason": v.reason,
                "status": v.status,
                "approved_by": v.approved_by,
                "approved_at": v.approved_at,
            }
            for v in self._variation_repo.list_by_project(project_id)
        ]

    def quotation_pipeline(self, project_id: Optional[str] = None) -> List[dict]:
        if not self._quotation_repo:
            raise ValidationError("Quotation repository is unavailable")
        if project_id:
            if not self._project_repo.find_by_id(project_id):
                raise ValidationError("Project not found")
            quotations = self._quotation_repo.list_by_project(project_id)
        else:
            quotations = self._quotation_repo.list_all()
        rows = [
            {
                "quotation_id": q.id,
                "project_id": q.project_id,
                "quotation_number": q.quotation_number,
                "status": q.status.value,
                "revision_no": q.revision_no,
                "total": round(q.subtotal, 2),
                "quotation_date": q.quotation_date,
            }
            for q in quotations
        ]
        return sorted(rows, key=lambda r: (r["project_id"], r["quotation_number"]))

    def quotation_revision_history(self, project_id: str) -> List[dict]:
        if not self._quotation_repo:
            raise ValidationError("Quotation repository is unavailable")
        if not self._project_repo.find_by_id(project_id):
            raise ValidationError("Project not found")
        quotations = self._quotation_repo.list_by_project(project_id)
        groups: Dict[str, List[dict]] = {}
        for quotation in quotations:
            root_id = quotation.root_id or quotation.id
            groups.setdefault(root_id, []).append(
                {
                    "quotation_id": quotation.id,
                    "quotation_number": quotation.quotation_number,
                    "revision_no": quotation.revision_no,
                    "status": quotation.status.value,
                    "supersedes_id": quotation.supersedes_id,
                    "total": round(quotation.subtotal, 2),
                    "quotation_date": quotation.quotation_date,
                }
            )
        history = []
        for root_id, revisions in groups.items():
            revisions.sort(key=lambda r: r["revision_no"])
            history.append(
                {
                    "root_id": root_id,
                    "revision_count": len(revisions),
                    "revisions": revisions,
                }
            )
        return sorted(history, key=lambda h: h["root_id"])

    def boq_status_report(self, project_id: str) -> List[dict]:
        if not self._boq_repo:
            raise ValidationError("BOQ repository is unavailable")
        if not self._project_repo.find_by_id(project_id):
            raise ValidationError("Project not found")
        rows = []
        for item in self._boq_repo.list_by_project(project_id):
            contracted = float(item.contracted_qty or 0) + float(item.varied_qty or 0)
            rows.append(
                {
                    "boq_item_id": item.id,
                    "code": item.code,
                    "description": item.description,
                    "item_type": item.item_type.value,
                    "unit": item.unit,
                    "estimated_qty": item.estimated_qty,
                    "selling_rate": item.selling_rate,
                    "estimated_value": item.estimated_value,
                    "contracted_qty": item.contracted_qty,
                    "contracted_rate": item.contracted_rate,
                    "measured_qty": item.measured_qty,
                    "certified_qty": item.certified_qty,
                    "billed_qty": item.billed_qty,
                    "balance_qty": round(contracted - float(item.billed_qty or 0), 4),
                }
            )
        return sorted(rows, key=lambda r: r["code"])

    def measurement_register(self, project_id: str) -> List[dict]:
        if not self._measurement_repo:
            raise ValidationError("Measurement repository is unavailable")
        if not self._project_repo.find_by_id(project_id):
            raise ValidationError("Project not found")
        boq_by_id = {}
        if self._boq_repo:
            boq_by_id = {
                i.id: i for i in self._boq_repo.list_by_project(project_id)
            }
        rows = []
        for m in self._measurement_repo.list_by_project(project_id):
            boq = boq_by_id.get(m.boq_item_id)
            rows.append(
                {
                    "measurement_id": m.id,
                    "measurement_date": m.measurement_date,
                    "boq_item_id": m.boq_item_id,
                    "boq_code": boq.code if boq else "",
                    "boq_description": boq.description if boq else "",
                    "quantity": m.quantity,
                    "cumulative_quantity": m.cumulative_quantity,
                    "location": m.location,
                    "dimensions": m.dimensions,
                    "status": m.status.value,
                    "ra_bill_id": m.ra_bill_id,
                }
            )
        return sorted(rows, key=lambda r: r.get("measurement_date") or "", reverse=True)

    def ra_register_dual(self, project_id: str) -> List[dict]:
        if not self._ra_repo:
            raise ValidationError("RA bill repository is unavailable")
        if not self._project_repo.find_by_id(project_id):
            raise ValidationError("Project not found")
        rows = []
        for ra in self._ra_repo.list_by_project(project_id):
            status = ra.status.value if hasattr(ra.status, "value") else ra.status
            rows.append(
                {
                    "ra_id": ra.id,
                    "ra_number": ra.ra_number,
                    "ra_date": ra.ra_date,
                    "status": status,
                    "gross_claimed": round(ra.gross_claimed, 2),
                    "gross_certified": round(ra.gross_certified, 2),
                    "net_claimed": round(ra.net_claimed, 2),
                    "net_certified": round(ra.net_certified, 2),
                    "invoiced": status == "Invoiced",
                    "invoice_voucher_id": ra.invoice_voucher_id,
                    "retention_claimed": ra.retention_amount_claimed,
                    "retention_certified": ra.retention_amount_certified,
                }
            )
        return sorted(rows, key=lambda r: r.get("ra_date") or "", reverse=True)

    def budget_vs_actual(self, project_id: str) -> dict:
        if not self._budget_repo:
            raise ValidationError("Budget repository is unavailable")
        project = self._project_repo.find_by_id(project_id)
        if not project:
            raise ValidationError("Project not found")
        lines = self._budget_repo.list_lines_by_project(project_id)
        actual = 0.0
        committed = 0.0
        if self._billing and hasattr(self._billing, "_total_project_cost"):
            actual = self._billing._total_project_cost(project_id)
        revised_total = round(sum(line.revised_amount for line in lines), 2)
        original_total = round(sum(line.original_amount for line in lines), 2)
        row_details = [
            {
                "line_id": line.id,
                "cost_category": line.cost_category.value,
                "original_amount": line.original_amount,
                "revised_amount": line.revised_amount,
                "variance": round(line.revised_amount - line.original_amount, 2),
                "boq_item_id": line.boq_item_id,
                "activity_id": line.activity_id,
            }
            for line in lines
        ]
        return {
            "project_id": project_id,
            "original_total": original_total,
            "revised_total": revised_total,
            "actual": round(actual, 2),
            "committed": round(committed, 2),
            "remaining": round(revised_total - actual - committed, 2),
            "lines": row_details,
        }

    def document_inventory(self, project_id: str) -> List[dict]:
        if not self._document_repo:
            raise ValidationError("Document repository is unavailable")
        if not self._project_repo.find_by_id(project_id):
            raise ValidationError("Project not found")
        documents = self._document_repo.list_by_project(project_id)
        return [
            {
                "document_id": doc.id,
                "name": doc.name,
                "category": doc.category.value,
                "content_type": doc.content_type,
                "size_bytes": doc.size_bytes,
                "source_ref_type": doc.source_ref_type,
                "source_ref_id": doc.source_ref_id,
                "uploaded_at": doc.uploaded_at,
            }
            for doc in documents
        ]
