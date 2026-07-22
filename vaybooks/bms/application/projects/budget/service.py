from __future__ import annotations

from datetime import date
from typing import List, Optional

from vaybooks.bms.domain.projects.budget import (
    ProjectBudgetHeader,
    ProjectBudgetLine,
    ProjectBudgetRevision,
)
from vaybooks.bms.domain.projects.cash_flow import ProjectCashFlowPlan
from vaybooks.bms.domain.projects.repository import (
    ProjectBudgetRepository,
    ProjectExpenseRepository,
    ProjectRepository,
    ProjectTimeEntryRepository,
)
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import (
    ProjectBudgetStatus,
    ProjectCostCategory,
    PurchaseOrderStatus,
    VoucherType,
)
from vaybooks.bms.domain.shared.exceptions import ValidationError

_CLOSED_PO_STATUSES = {
    PurchaseOrderStatus.CLOSED,
    PurchaseOrderStatus.CANCELLED,
    PurchaseOrderStatus.RECEIVED,
}


class ProjectBudgetAppService:
    def __init__(
        self,
        budget_repo: ProjectBudgetRepository,
        project_repo: ProjectRepository,
        expense_repo: Optional[ProjectExpenseRepository] = None,
        time_repo: Optional[ProjectTimeEntryRepository] = None,
        purchase_service=None,
        cash_flow_repo=None,
        billing_service=None,
    ):
        self._budget_repo = budget_repo
        self._project_repo = project_repo
        self._expense_repo = expense_repo
        self._time_repo = time_repo
        self._purchase_service = purchase_service
        self._cash_flow_repo = cash_flow_repo
        self._billing_service = billing_service

    def _get_project(self, project_id: str):
        project = self._project_repo.find_by_id(project_id)
        if not project:
            raise ValidationError("Project not found")
        return project

    def get_or_create_header(self, project_id: str) -> ProjectBudgetHeader:
        self._get_project(project_id)
        if hasattr(self._budget_repo, "find_header_by_project"):
            header = self._budget_repo.find_header_by_project(project_id)
            if header:
                return header
            header = ProjectBudgetHeader(project_id=project_id)
            return self._budget_repo.save_header(header)
        return ProjectBudgetHeader(project_id=project_id)

    def _ensure_editable(self, project_id: str) -> ProjectBudgetHeader:
        header = self.get_or_create_header(project_id)
        if header.status == ProjectBudgetStatus.APPROVED:
            raise ValidationError(
                "Approved budget is frozen; use revise to change amounts"
            )
        return header

    def list_lines(self, project_id: str) -> List[ProjectBudgetLine]:
        self._get_project(project_id)
        return self._budget_repo.list_lines_by_project(project_id)

    def add_line(
        self,
        project_id: str,
        cost_category,
        amount: float,
        *,
        boq_item_id: str = "",
        activity_id: str = "",
        notes: str = "",
    ) -> ProjectBudgetLine:
        self._ensure_editable(project_id)
        if isinstance(cost_category, str):
            cost_category = ProjectCostCategory(cost_category)
        amt = float(amount or 0.0)
        if amt < 0:
            raise ValidationError("Budget amount cannot be negative")
        line = ProjectBudgetLine(
            project_id=project_id,
            cost_category=cost_category,
            original_amount=amt,
            revised_amount=amt,
            boq_item_id=(boq_item_id or "").strip(),
            activity_id=(activity_id or "").strip(),
            notes=(notes or "").strip(),
        )
        return self._budget_repo.save_line(line)

    def submit_budget(self, project_id: str) -> ProjectBudgetHeader:
        header = self.get_or_create_header(project_id)
        if header.status == ProjectBudgetStatus.APPROVED:
            raise ValidationError("Budget already approved")
        if not self.list_lines(project_id):
            raise ValidationError("Add budget lines before submit")
        header.status = ProjectBudgetStatus.SUBMITTED
        header.updated_at = utc_now()
        if hasattr(self._budget_repo, "save_header"):
            return self._budget_repo.save_header(header)
        return header

    def approve_budget(
        self, project_id: str, *, approved_by: str = ""
    ) -> ProjectBudgetHeader:
        header = self.get_or_create_header(project_id)
        if header.status == ProjectBudgetStatus.APPROVED:
            return header
        if not self.list_lines(project_id):
            raise ValidationError("Cannot approve empty budget")
        header.status = ProjectBudgetStatus.APPROVED
        header.approved_at = utc_now()
        header.approved_by = (approved_by or "").strip()
        header.updated_at = utc_now()
        if hasattr(self._budget_repo, "save_header"):
            return self._budget_repo.save_header(header)
        return header

    def _snapshot_lines(self, project_id: str) -> List[dict]:
        return [
            {
                "id": line.id,
                "cost_category": line.cost_category.value,
                "original_amount": line.original_amount,
                "revised_amount": line.revised_amount,
                "boq_item_id": line.boq_item_id,
                "activity_id": line.activity_id,
                "notes": line.notes,
            }
            for line in self._budget_repo.list_lines_by_project(project_id)
        ]

    def revise_line(
        self,
        line_id: str,
        revised_amount: float,
        reason: str = "",
        revised_by: str = "",
        *,
        forecast_eac: float | None = None,
        forecast_etc: float | None = None,
    ) -> ProjectBudgetLine:
        line = self._budget_repo.find_line_by_id(line_id)
        if not line:
            raise ValidationError("Budget line not found")
        amt = float(revised_amount or 0.0)
        if amt < 0:
            raise ValidationError("Revised amount cannot be negative")
        line.revised_amount = amt
        if forecast_eac is not None:
            line.forecast_eac = float(forecast_eac or 0.0)
        if forecast_etc is not None:
            line.forecast_etc = float(forecast_etc or 0.0)
        elif forecast_eac is not None:
            line.forecast_etc = max(float(forecast_eac or 0.0) - amt, 0.0)
        line.updated_at = utc_now()
        saved = self._budget_repo.save_line(line)
        self._budget_repo.save_revision(
            ProjectBudgetRevision(
                project_id=line.project_id,
                reason=(reason or "").strip() or "Budget revision",
                revised_by=(revised_by or "").strip(),
                lines_snapshot=self._snapshot_lines(line.project_id),
                forecast_eac=float(saved.forecast_eac or 0.0),
                forecast_etc=float(saved.forecast_etc or 0.0),
            )
        )
        return saved

    def revise_many(
        self,
        project_id: str,
        updates: List[dict],
        reason: str,
        revised_by: str = "",
    ) -> List[ProjectBudgetLine]:
        self._get_project(project_id)
        if not updates:
            raise ValidationError("At least one budget update is required")
        saved_lines: List[ProjectBudgetLine] = []
        for row in updates:
            line_id = (row.get("line_id") or "").strip()
            if not line_id:
                raise ValidationError("line_id is required for each update")
            line = self._budget_repo.find_line_by_id(line_id)
            if not line or line.project_id != project_id:
                raise ValidationError("Budget line not found")
            amt = float(row.get("revised_amount") or 0.0)
            if amt < 0:
                raise ValidationError("Revised amount cannot be negative")
            line.revised_amount = amt
            if row.get("forecast_eac") is not None:
                line.forecast_eac = float(row.get("forecast_eac") or 0.0)
            if row.get("forecast_etc") is not None:
                line.forecast_etc = float(row.get("forecast_etc") or 0.0)
            line.updated_at = utc_now()
            saved_lines.append(self._budget_repo.save_line(line))
        self._budget_repo.save_revision(
            ProjectBudgetRevision(
                project_id=project_id,
                reason=(reason or "").strip() or "Budget revision",
                revised_by=(revised_by or "").strip(),
                lines_snapshot=self._snapshot_lines(project_id),
            )
        )
        return saved_lines

    def _actual_spend(self, project_id: str) -> float:
        expenses = 0.0
        labour = 0.0
        if self._expense_repo:
            expenses = sum(e.amount for e in self._expense_repo.list_by_project(project_id))
        if self._time_repo:
            labour = sum(e.labour_cost for e in self._time_repo.list_by_project(project_id))
        return round(expenses + labour, 2)

    def _committed_spend(self, project_id: str) -> float:
        if not self._purchase_service or not hasattr(
            self._purchase_service, "list_purchase_orders"
        ):
            return 0.0
        total = 0.0
        for po in self._purchase_service.list_purchase_orders():
            if (po.project_id or "") != project_id:
                continue
            if po.status in _CLOSED_PO_STATUSES:
                continue
            total += float(po.total_amount or 0.0)
        return round(total, 2)

    def budget_summary(self, project_id: str) -> dict:
        self._get_project(project_id)
        lines = self._budget_repo.list_lines_by_project(project_id)
        original_total = round(sum(line.original_amount for line in lines), 2)
        revised_total = round(sum(line.revised_amount for line in lines), 2)
        actual = self._actual_spend(project_id)
        committed = self._committed_spend(project_id)
        remaining = round(revised_total - actual - committed, 2)
        forecast_eac = round(
            sum(float(line.forecast_eac or 0.0) for line in lines), 2
        )
        forecast_etc = round(
            sum(float(line.forecast_etc or 0.0) for line in lines), 2
        )
        return {
            "project_id": project_id,
            "original_total": original_total,
            "revised_total": revised_total,
            "actual": actual,
            "committed": committed,
            "remaining": remaining,
            "forecast_eac": forecast_eac,
            "forecast_etc": forecast_etc,
            "line_count": len(lines),
        }

    def check_over_budget(self, project_id: str, additional_amount: float) -> dict:
        project = self._get_project(project_id)
        summary = self.budget_summary(project_id)
        additional = float(additional_amount or 0.0)
        projected = summary["actual"] + summary["committed"] + additional
        over = projected > summary["revised_total"] + 0.001
        hard_block = bool(project.hard_budget_check and over)
        message = ""
        if over:
            message = (
                f"Budget exceeded by {round(projected - summary['revised_total'], 2):.2f}; "
                f"revised total {summary['revised_total']:.2f}, "
                f"projected spend {projected:.2f}"
            )
        return {
            "over": over,
            "hard_block": hard_block,
            "message": message,
            "summary": summary,
        }

    def add_cash_flow_plan(
        self,
        project_id: str,
        period_start: date,
        period_end: date,
        cash_in_planned: float,
        cash_out_planned: float,
        *,
        notes: str = "",
    ) -> ProjectCashFlowPlan:
        self._get_project(project_id)
        if self._cash_flow_repo is None:
            raise ValidationError("Cash flow repository is unavailable")
        if period_end < period_start:
            raise ValidationError("period_end must be on or after period_start")
        cash_in = float(cash_in_planned or 0.0)
        cash_out = float(cash_out_planned or 0.0)
        if cash_in < 0 or cash_out < 0:
            raise ValidationError("Cash flow amounts cannot be negative")
        plan = ProjectCashFlowPlan(
            project_id=project_id,
            period_start=period_start,
            period_end=period_end,
            cash_in_planned=cash_in,
            cash_out_planned=cash_out,
            notes=(notes or "").strip(),
        )
        return self._cash_flow_repo.save(plan)

    def list_cash_flow_plans(self, project_id: str) -> List[ProjectCashFlowPlan]:
        self._get_project(project_id)
        if self._cash_flow_repo is None:
            return []
        return self._cash_flow_repo.list_by_project(project_id)

    def _receipt_cash_in(self, project_id: str) -> float:
        """Stub actual cash-in from billing receipts when available."""
        if self._billing_service is None:
            return 0.0
        total = 0.0
        try:
            if hasattr(self._billing_service, "_list_project_vouchers"):
                for voucher in self._billing_service._list_project_vouchers(project_id):
                    vtype = voucher.voucher_type
                    if hasattr(vtype, "value"):
                        is_receipt = vtype == VoucherType.RECEIPT
                    else:
                        is_receipt = str(vtype) == VoucherType.RECEIPT.value
                    if is_receipt:
                        total += sum(
                            float(line.debit_amount or 0.0) for line in voucher.lines
                        )
        except Exception:
            return 0.0
        return round(total, 2)

    def cash_flow_vs_actual(self, project_id: str) -> dict:
        self._get_project(project_id)
        plans = self.list_cash_flow_plans(project_id)
        cash_in_planned = round(sum(p.cash_in_planned for p in plans), 2)
        cash_out_planned = round(sum(p.cash_out_planned for p in plans), 2)
        cash_in_actual = self._receipt_cash_in(project_id)
        cash_out_actual = 0.0
        if self._expense_repo:
            try:
                cash_out_actual = round(
                    sum(e.amount for e in self._expense_repo.list_by_project(project_id)),
                    2,
                )
            except Exception:
                cash_out_actual = 0.0
        return {
            "project_id": project_id,
            "plan_count": len(plans),
            "cash_in_planned": cash_in_planned,
            "cash_out_planned": cash_out_planned,
            "cash_in_actual": cash_in_actual,
            "cash_out_actual": cash_out_actual,
            "net_planned": round(cash_in_planned - cash_out_planned, 2),
            "net_actual": round(cash_in_actual - cash_out_actual, 2),
            "plans": [
                {
                    "id": p.id,
                    "period_start": p.period_start,
                    "period_end": p.period_end,
                    "cash_in_planned": p.cash_in_planned,
                    "cash_out_planned": p.cash_out_planned,
                }
                for p in plans
            ],
        }
