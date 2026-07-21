"""Wave 3 budget / cash-flow control tests."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Dict, List, Optional

import pytest

from vaybooks.bms.application.project_budget_app_service import ProjectBudgetAppService
from vaybooks.bms.domain.projects.budget import (
    ProjectBudgetHeader,
    ProjectBudgetLine,
    ProjectBudgetRevision,
)
from vaybooks.bms.domain.projects.cash_flow import ProjectCashFlowPlan
from vaybooks.bms.domain.projects.entities import Project
from vaybooks.bms.domain.shared.enums import ProjectCostCategory
from vaybooks.bms.domain.shared.exceptions import ValidationError
from tests.test_projects_module import FakeProjectRepository


class FakeBudgetRepo:
    def __init__(self):
        self._lines: Dict[str, ProjectBudgetLine] = {}
        self._revisions: List[ProjectBudgetRevision] = []
        self._headers: Dict[str, ProjectBudgetHeader] = {}

    def save_line(self, line: ProjectBudgetLine) -> ProjectBudgetLine:
        self._lines[line.id] = line
        return line

    def save_lines(self, lines: List[ProjectBudgetLine]) -> List[ProjectBudgetLine]:
        for line in lines:
            self.save_line(line)
        return lines

    def find_line_by_id(self, line_id: str) -> Optional[ProjectBudgetLine]:
        line = self._lines.get(line_id)
        return deepcopy(line) if line else None

    def list_lines_by_project(self, project_id: str) -> List[ProjectBudgetLine]:
        return [
            deepcopy(line)
            for line in self._lines.values()
            if line.project_id == project_id
        ]

    def save_revision(self, revision: ProjectBudgetRevision) -> ProjectBudgetRevision:
        self._revisions.append(revision)
        return revision

    def list_revisions_by_project(self, project_id: str) -> List[ProjectBudgetRevision]:
        return [r for r in self._revisions if r.project_id == project_id]

    def save_header(self, header: ProjectBudgetHeader) -> ProjectBudgetHeader:
        self._headers[header.project_id] = header
        return header

    def find_header_by_project(self, project_id: str) -> Optional[ProjectBudgetHeader]:
        return self._headers.get(project_id)


class FakeCashFlowRepo:
    def __init__(self):
        self._store: Dict[str, ProjectCashFlowPlan] = {}

    def save(self, plan: ProjectCashFlowPlan) -> ProjectCashFlowPlan:
        self._store[plan.id] = plan
        return plan

    def find_by_id(self, plan_id: str) -> Optional[ProjectCashFlowPlan]:
        return self._store.get(plan_id)

    def list_by_project(self, project_id: str) -> List[ProjectCashFlowPlan]:
        return [p for p in self._store.values() if p.project_id == project_id]


@pytest.fixture
def budget_stack():
    project_repo = FakeProjectRepository()
    project = Project(
        project_number="P-W3",
        name="Wave 3 Budget",
        customer_id="c1",
        customer_name="Cust",
        contract_value=100000,
    )
    project_repo.save(project)
    budget_repo = FakeBudgetRepo()
    cash_flow_repo = FakeCashFlowRepo()
    svc = ProjectBudgetAppService(
        budget_repo,
        project_repo,
        cash_flow_repo=cash_flow_repo,
    )
    return {
        "project": project,
        "svc": svc,
        "budget_repo": budget_repo,
        "cash_flow_repo": cash_flow_repo,
    }


def test_cash_flow_plan_and_vs_actual(budget_stack):
    project = budget_stack["project"]
    svc = budget_stack["svc"]

    plan = svc.add_cash_flow_plan(
        project.id,
        date(2026, 7, 1),
        date(2026, 7, 31),
        cash_in_planned=50000,
        cash_out_planned=30000,
        notes="July plan",
    )
    assert plan.project_id == project.id
    assert plan.cash_in_planned == 50000
    assert plan.cash_out_planned == 30000

    plans = svc.list_cash_flow_plans(project.id)
    assert len(plans) == 1

    vs = svc.cash_flow_vs_actual(project.id)
    assert vs["plan_count"] == 1
    assert vs["cash_in_planned"] == 50000
    assert vs["cash_out_planned"] == 30000
    assert vs["cash_in_actual"] == 0.0
    assert vs["cash_out_actual"] == 0.0
    assert vs["net_planned"] == 20000

    with pytest.raises(ValidationError):
        svc.add_cash_flow_plan(
            project.id,
            date(2026, 8, 10),
            date(2026, 8, 1),
            1000,
            500,
        )


def test_budget_summary_keys(budget_stack):
    project = budget_stack["project"]
    svc = budget_stack["svc"]

    line = svc.add_line(
        project.id,
        ProjectCostCategory.MATERIAL,
        25000,
        notes="Steel",
    )
    svc.revise_line(
        line.id,
        28000,
        reason="Price rise",
        forecast_eac=32000,
        forecast_etc=4000,
    )

    summary = svc.budget_summary(project.id)
    expected_keys = {
        "project_id",
        "original_total",
        "revised_total",
        "actual",
        "committed",
        "remaining",
        "forecast_eac",
        "forecast_etc",
        "line_count",
    }
    assert expected_keys.issubset(summary.keys())
    assert summary["original_total"] == 25000
    assert summary["revised_total"] == 28000
    assert summary["committed"] == 0.0
    assert summary["forecast_eac"] == 32000
    assert summary["forecast_etc"] == 4000
    assert summary["line_count"] == 1
    assert summary["remaining"] == summary["revised_total"] - summary["actual"] - summary[
        "committed"
    ]
