"""Site petty cash advances and settlements."""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from vaybooks.bms.domain.projects.petty_cash import (
    ProjectPettyCashAdvance,
    ProjectPettyCashExpenseLine,
)
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import ProjectPettyCashStatus
from vaybooks.bms.domain.shared.exceptions import ValidationError


class ProjectPettyCashAppService:
    def __init__(self, petty_cash_repo, project_repo, counter_repo):
        self._repo = petty_cash_repo
        self._project_repo = project_repo
        self._counter_repo = counter_repo

    def _get_project(self, project_id: str):
        project = self._project_repo.find_by_id(project_id)
        if not project:
            raise ValidationError("Project not found")
        return project

    def create_advance(
        self,
        project_id: str,
        custodian: str,
        amount: float,
        *,
        advance_date: Optional[date] = None,
        notes: str = "",
    ) -> ProjectPettyCashAdvance:
        self._get_project(project_id)
        if float(amount or 0) <= 0:
            raise ValidationError("Advance amount must be positive")
        advance = ProjectPettyCashAdvance(
            project_id=project_id,
            advance_number=self._counter_repo.next("project_petty_cash_number"),
            custodian=(custodian or "").strip(),
            advance_date=advance_date or date.today(),
            amount=float(amount),
            notes=(notes or "").strip(),
        )
        return self._repo.save(advance)

    def list_advances(self, project_id: str) -> List[ProjectPettyCashAdvance]:
        self._get_project(project_id)
        return self._repo.list_by_project(project_id)

    def add_expense(
        self,
        advance_id: str,
        description: str,
        amount: float,
        expense_date: date,
        *,
        activity_id: str = "",
        receipt_ref: str = "",
    ) -> ProjectPettyCashAdvance:
        advance = self._repo.find_by_id(advance_id)
        if not advance:
            raise ValidationError("Advance not found")
        if advance.status == ProjectPettyCashStatus.SETTLED:
            raise ValidationError("Advance already settled")
        advance.expenses.append(
            ProjectPettyCashExpenseLine(
                description=(description or "").strip(),
                amount=float(amount or 0),
                expense_date=expense_date,
                activity_id=activity_id or "",
                receipt_ref=receipt_ref or "",
            )
        )
        advance.status = ProjectPettyCashStatus.SETTLEMENT_PENDING
        advance.updated_at = utc_now()
        return self._repo.save(advance)

    def settle(
        self,
        advance_id: str,
        *,
        returned_amount: float = 0.0,
        reimbursement_amount: float = 0.0,
    ) -> ProjectPettyCashAdvance:
        advance = self._repo.find_by_id(advance_id)
        if not advance:
            raise ValidationError("Advance not found")
        advance.returned_amount = float(returned_amount or 0)
        advance.reimbursement_amount = float(reimbursement_amount or 0)
        # used + returned - reimbursement should equal advance
        identity = (
            advance.used_amount
            + advance.returned_amount
            - advance.reimbursement_amount
        )
        if abs(identity - float(advance.amount)) > 0.01:
            raise ValidationError(
                f"Settlement imbalance: used+returned-reimburse={identity:.2f} "
                f"vs advance={advance.amount:.2f}"
            )
        advance.status = ProjectPettyCashStatus.SETTLED
        advance.updated_at = utc_now()
        return self._repo.save(advance)
