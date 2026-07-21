from __future__ import annotations

from datetime import date
from typing import List, Optional

from vaybooks.bms.domain.projects.entities import ProjectExpense
from vaybooks.bms.domain.projects.repository import (
    ProjectExpenseRepository,
    ProjectRepository,
)
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import ProjectExpenseSource, ProjectStatus
from vaybooks.bms.domain.shared.exceptions import ValidationError


class ProjectExpenseAppService:
    def __init__(
        self,
        expense_repo: ProjectExpenseRepository,
        project_repo: ProjectRepository,
        *,
        budget_service=None,
    ):
        self._expense_repo = expense_repo
        self._project_repo = project_repo
        self._budget_service = budget_service

    def _get_project(self, project_id: str) -> None:
        if not self._project_repo.find_by_id(project_id):
            raise ValidationError("Project not found")

    def _validate_amount(self, amount: float) -> None:
        if float(amount or 0) <= 0:
            raise ValidationError("Expense amount must be greater than zero")

    def _budget_guard(self, project_id: str, amount: float) -> None:
        if not self._budget_service:
            return
        check = self._budget_service.check_over_budget(project_id, amount)
        if check.get("hard_block"):
            raise ValidationError(
                check.get("message")
                or "Expense blocked: project hard budget check exceeded"
            )

    def create_expense(
        self,
        project_id: str,
        expense_date: date,
        expense_name: str,
        expense_source: str,
        amount: float,
        *,
        activity_id: Optional[str] = None,
        boq_item_id: str = "",
        vendor_id: str = "",
        vendor_name: str = "",
        notes: str = "",
        purchase_voucher_id: str = "",
        wbs_node_id: str = "",
        site_id: str = "",
        cost_category: str = "",
    ) -> ProjectExpense:
        project = self._project_repo.find_by_id(project_id)
        if not project:
            raise ValidationError("Project not found")
        if project.status == ProjectStatus.FINANCIALLY_CLOSED:
            raise ValidationError("Project is closed; expenses cannot be added")
        if not (expense_name or "").strip():
            raise ValidationError("Expense name is required")
        self._validate_amount(amount)
        self._budget_guard(project_id, float(amount))
        expense = ProjectExpense(
            project_id=project_id,
            expense_date=expense_date,
            expense_name=(expense_name or "").strip(),
            expense_source=ProjectExpenseSource(expense_source),
            amount=float(amount),
            activity_id=activity_id,
            boq_item_id=(boq_item_id or "").strip(),
            vendor_id=(vendor_id or "").strip(),
            vendor_name=(vendor_name or "").strip(),
            notes=(notes or "").strip(),
            purchase_voucher_id=(purchase_voucher_id or "").strip(),
            wbs_node_id=(wbs_node_id or "").strip(),
            site_id=(site_id or "").strip(),
            cost_category=(cost_category or "").strip(),
        )
        return self._expense_repo.save(expense)

    def update_expense(
        self,
        expense_id: str,
        expense_date: date,
        expense_name: str,
        expense_source: str,
        amount: float,
        *,
        activity_id: Optional[str] = None,
        boq_item_id: str = "",
        vendor_id: str = "",
        vendor_name: str = "",
        notes: str = "",
        purchase_voucher_id: str = "",
    ) -> ProjectExpense:
        expense = self._expense_repo.find_by_id(expense_id)
        if not expense:
            raise ValidationError("Expense not found")
        if not (expense_name or "").strip():
            raise ValidationError("Expense name is required")
        self._validate_amount(amount)
        expense.expense_date = expense_date
        expense.expense_name = (expense_name or "").strip()
        expense.expense_source = ProjectExpenseSource(expense_source)
        expense.amount = float(amount)
        expense.activity_id = activity_id
        expense.boq_item_id = (boq_item_id or "").strip()
        expense.vendor_id = (vendor_id or "").strip()
        expense.vendor_name = (vendor_name or "").strip()
        expense.notes = (notes or "").strip()
        expense.purchase_voucher_id = (purchase_voucher_id or "").strip()
        expense.updated_at = utc_now()
        return self._expense_repo.save(expense)

    def get_expense(self, expense_id: str) -> Optional[ProjectExpense]:
        return self._expense_repo.find_by_id(expense_id)

    def list_by_project(self, project_id: str) -> List[ProjectExpense]:
        return self._expense_repo.list_by_project(project_id)

    def delete_expense(self, expense_id: str) -> None:
        if not self._expense_repo.find_by_id(expense_id):
            raise ValidationError("Expense not found")
        self._expense_repo.delete(expense_id)
