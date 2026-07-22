"""Wave 1 foundation tests — access, maker-checker, dimensions, audit."""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

import pytest

from vaybooks.bms.application.projects.access.service import ProjectAccessPolicy
from vaybooks.bms.application.projects.audit.service import ProjectAuditAppService
from vaybooks.bms.application.projects.expenses.service import ProjectExpenseAppService
from vaybooks.bms.application.projects.quotations.service import ProjectQuotationAppService
from vaybooks.bms.domain.projects.access import (
    AppUser,
    ProjectAuditEntry,
    ProjectMembership,
)
from vaybooks.bms.domain.projects.entities import Project, ProjectExpense, ProjectQuotation
from vaybooks.bms.domain.shared.enums import ProjectAppRole, ProjectExpenseSource
from vaybooks.bms.domain.shared.exceptions import ValidationError
from tests.conftest import FakeCounterRepository
from tests.test_projects_module import FakeProjectRepository


class FakeUserRepo:
    def __init__(self):
        self._store: Dict[str, AppUser] = {}

    def save(self, user: AppUser) -> AppUser:
        self._store[user.id] = user
        return user

    def find_by_id(self, user_id: str):
        return self._store.get(user_id)

    def find_by_username(self, username: str):
        for u in self._store.values():
            if u.username == username:
                return u
        return None


class FakeMembershipRepo:
    def __init__(self):
        self._store: Dict[str, ProjectMembership] = {}

    def save(self, m: ProjectMembership) -> ProjectMembership:
        self._store[m.id] = m
        return m

    def list_by_project(self, project_id: str):
        return [m for m in self._store.values() if m.project_id == project_id]


class FakeAuditRepo:
    def __init__(self):
        self._store: List[ProjectAuditEntry] = []

    def save(self, entry: ProjectAuditEntry) -> ProjectAuditEntry:
        self._store.append(entry)
        return entry

    def list_by_project(self, project_id: str, limit: int = 200):
        items = [e for e in self._store if e.project_id == project_id]
        return items[:limit]


class FakeExpenseRepo:
    def __init__(self):
        self._store: Dict[str, ProjectExpense] = {}

    def save(self, expense: ProjectExpense) -> ProjectExpense:
        self._store[expense.id] = expense
        return expense

    def find_by_id(self, expense_id: str):
        return self._store.get(expense_id)

    def list_by_project(self, project_id: str):
        return [e for e in self._store.values() if e.project_id == project_id]

    def delete(self, expense_id: str) -> None:
        self._store.pop(expense_id, None)


class FakeQuoteRepo:
    def __init__(self):
        self._store: Dict[str, ProjectQuotation] = {}

    def save(self, q: ProjectQuotation) -> ProjectQuotation:
        self._store[q.id] = q
        return q

    def find_by_id(self, qid: str):
        return self._store.get(qid)

    def list_by_project(self, project_id: str):
        return [q for q in self._store.values() if q.project_id == project_id]


def test_uc043_maker_checker_blocks_self_approve():
    """UC-043 / Wave 1 — cannot approve own quotation."""
    policy = ProjectAccessPolicy(maker_checker_enabled=True)
    with pytest.raises(ValidationError, match="Maker-checker"):
        policy.assert_commercial_approve(
            actor_id="alice",
            actor_name="alice",
            submitted_by="alice",
            document_label="quotation",
        )


def test_ac013_site_engineer_cannot_view_internal_cost():
    """AC-013 — site role cannot view internal cost."""
    user = AppUser(
        username="site1",
        display_name="Site",
        global_roles=[ProjectAppRole.SITE_ENGINEER],
    )
    policy = ProjectAccessPolicy()
    assert policy.can_view_internal_cost(user) is False
    owner = AppUser(
        username="owner",
        global_roles=[ProjectAppRole.OWNER],
    )
    assert policy.can_view_internal_cost(owner) is True


def test_ac003_expense_line_dimensions():
    """AC-003 — expense carries project dimensions."""
    projects = FakeProjectRepository()
    project = Project(
        project_number="P-1",
        name="Dim Project",
        customer_id="c1",
        customer_name="Cust",
    )
    projects.save(project)
    expenses = ProjectExpenseAppService(FakeExpenseRepo(), projects)
    exp = expenses.create_expense(
        project.id,
        date.today(),
        "Cement",
        ProjectExpenseSource.MATERIAL.value,
        500,
        activity_id="act1",
        boq_item_id="boq1",
        site_id="site1",
        wbs_node_id="wbs1",
        cost_category="Material",
    )
    assert exp.site_id == "site1"
    assert exp.wbs_node_id == "wbs1"
    assert exp.cost_category == "Material"
    assert exp.boq_item_id == "boq1"


def test_quotation_approve_records_audit_and_maker_checker():
    projects = FakeProjectRepository()
    project = Project(
        project_number="P-2",
        name="Quote Project",
        customer_id="c1",
        customer_name="Cust",
    )
    projects.save(project)
    audit_repo = FakeAuditRepo()
    audit = ProjectAuditAppService(audit_repo)
    policy = ProjectAccessPolicy(maker_checker_enabled=True)
    quotes = ProjectQuotationAppService(
        FakeQuoteRepo(),
        projects,
        FakeCounterRepository(),
        access_policy=policy,
        audit_service=audit,
    )
    q = quotes.create_quotation(
        project.id,
        lines=[{"description": "Work", "quantity": 1, "rate": 100}],
        created_by="estimator1",
    )
    quotes.submit_for_approval(q.id, submitted_by="estimator1")
    with pytest.raises(ValidationError, match="Maker-checker"):
        quotes.approve_quotation(q.id, approved_by="estimator1")
    approved = quotes.approve_quotation(q.id, approved_by="approver1")
    assert approved.status.value == "Approved"
    assert any(e.action == "approve" for e in audit_repo._store)
