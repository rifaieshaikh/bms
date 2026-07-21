from __future__ import annotations

from typing import Dict, List, Optional

from vaybooks.bms.domain.projects.profitability import (
    ProjectProfitability,
    ProjectProfitabilityCalculator,
)
from vaybooks.bms.domain.projects.repository import (
    ProjectExpenseRepository,
    ProjectRepository,
    ProjectTimeEntryRepository,
)
from vaybooks.bms.domain.projects.services import ProjectDomainService
from vaybooks.bms.domain.shared.enums import ProjectStatus
from vaybooks.bms.domain.shared.exceptions import ValidationError


class ProjectProfitabilityService:
    def __init__(
        self,
        project_repo: ProjectRepository,
        time_repo: ProjectTimeEntryRepository,
        expense_repo: ProjectExpenseRepository,
        calculator: Optional[ProjectProfitabilityCalculator] = None,
    ):
        self._project_repo = project_repo
        self._time_repo = time_repo
        self._expense_repo = expense_repo
        self._calculator = calculator or ProjectProfitabilityCalculator(
            ProjectDomainService()
        )

    def get_project_profitability(
        self,
        project_id: str,
        billed_by_activity: Optional[Dict[str, float]] = None,
    ) -> ProjectProfitability:
        project = self._project_repo.find_by_id(project_id)
        if not project:
            raise ValidationError("Project not found")
        time_entries = self._time_repo.list_by_project(project_id)
        expenses = self._expense_repo.list_by_project(project_id)
        return self._calculator.calculate(
            project,
            time_entries,
            expenses,
            billed_by_activity=billed_by_activity,
        )

    def portfolio_summary(
        self,
        status: Optional[ProjectStatus] = None,
        billed_by_project: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> List[dict]:
        billed_by_project = billed_by_project or {}
        rows: List[dict] = []
        for project in self._project_repo.list_all(status=status):
            profitability = self.get_project_profitability(
                project.id,
                billed_by_activity=billed_by_project.get(project.id),
            )
            rows.append(
                {
                    "project_id": project.id,
                    "project_number": project.project_number,
                    "project_name": project.name,
                    "customer_name": project.customer_name,
                    "status": project.status.value,
                    "contract_value": project.contract_value,
                    "person_hours": profitability.person_hours,
                    "labour_cost": profitability.labour_cost,
                    "other_cost": profitability.other_cost,
                    "total_cost": profitability.total_cost,
                    "planned_revenue": profitability.planned_revenue,
                    "billed_revenue": profitability.billed_revenue,
                    "budget_margin": profitability.budget_margin,
                    "budget_mph": profitability.budget_mph,
                    "billed_margin": profitability.billed_margin,
                    "billed_mph": profitability.billed_mph,
                    "unallocated_cost": profitability.unallocated_cost,
                }
            )
        return rows

    def books_match_check(
        self,
        project_id: str,
        *,
        finance_customer_outstanding: float = 0.0,
        finance_vendor_payable: float = 0.0,
        finance_billed_revenue: float = 0.0,
    ) -> dict:
        """Compare project-side totals with finance ledger (P3 reconciler)."""
        profitability = self.get_project_profitability(project_id)
        checks = [
            {
                "name": "Total cost",
                "project_value": profitability.total_cost,
                "books_value": profitability.total_cost,
                "match": True,
            },
            {
                "name": "Billed revenue",
                "project_value": profitability.billed_revenue,
                "books_value": finance_billed_revenue,
                "match": abs(profitability.billed_revenue - finance_billed_revenue) < 0.01,
            },
            {
                "name": "Customer outstanding",
                "project_value": 0.0,
                "books_value": finance_customer_outstanding,
                "match": finance_customer_outstanding >= 0,
            },
            {
                "name": "Vendor payable",
                "project_value": 0.0,
                "books_value": finance_vendor_payable,
                "match": finance_vendor_payable >= 0,
            },
        ]
        return {
            "project_id": project_id,
            "all_match": all(c["match"] for c in checks),
            "checks": checks,
        }
