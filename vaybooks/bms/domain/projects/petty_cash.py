"""Site petty cash advances and settlements."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import ProjectPettyCashStatus


@dataclass
class ProjectPettyCashExpenseLine:
    description: str
    amount: float
    expense_date: date
    activity_id: str = ""
    receipt_ref: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)


@dataclass
class ProjectPettyCashAdvance:
    project_id: str
    advance_number: str
    custodian: str
    advance_date: date
    amount: float
    expenses: List[ProjectPettyCashExpenseLine] = field(default_factory=list)
    returned_amount: float = 0.0
    reimbursement_amount: float = 0.0
    status: ProjectPettyCashStatus = ProjectPettyCashStatus.OPEN
    notes: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @property
    def used_amount(self) -> float:
        return sum(line.amount for line in self.expenses)

    @property
    def balance(self) -> float:
        return (
            float(self.amount)
            - self.used_amount
            - float(self.returned_amount)
            + float(self.reimbursement_amount)
        )
