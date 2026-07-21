"""Wave 8 advanced finance — recognition post, offline drafts, portal, overhead."""

from __future__ import annotations

from datetime import date
from typing import Dict, List

import pytest

from vaybooks.bms.application.project_app_service import ProjectAppService
from vaybooks.bms.application.project_offline_app_service import ProjectOfflineAppService
from vaybooks.bms.application.project_portal_app_service import ProjectPortalAppService
from vaybooks.bms.application.project_recognition_app_service import (
    ProjectRecognitionAppService,
)
from vaybooks.bms.domain.customers.entities import Customer
from vaybooks.bms.domain.projects.entities import ProjectExpense
from vaybooks.bms.domain.shared.enums import (
    ProjectExpenseSource,
    ProjectRecognitionMethod,
    ProjectRecognitionStatus,
)
from vaybooks.bms.domain.shared.exceptions import ValidationError
from tests.conftest import FakeCounterRepository, FakeCustomerRepository
from tests.test_project_full_accounting_usecases import FakeRecognitionRepo
from tests.test_projects_module import FakeProjectRepository, FakeProjectTemplateRepository


class FakeExpenseRepo:
    def __init__(self):
        self._store: Dict[str, ProjectExpense] = {}

    def save(self, expense: ProjectExpense) -> ProjectExpense:
        self._store[expense.id] = expense
        return expense

    def find_by_id(self, expense_id: str):
        return self._store.get(expense_id)

    def list_by_project(self, project_id: str) -> List[ProjectExpense]:
        return [e for e in self._store.values() if e.project_id == project_id]

    def delete(self, expense_id: str) -> None:
        self._store.pop(expense_id, None)


class FakeAccount:
    def __init__(self, account_id: str, name: str):
        self.id = account_id
        self.account_name = name


class FakeAccountingWithJournal:
    def __init__(self):
        self.journals: List[dict] = []
        self._accounts = {
            "WIP": FakeAccount("wip-1", "WIP"),
            "Revenue": FakeAccount("rev-1", "Revenue"),
        }

    def get_account_by_name(self, name: str):
        return self._accounts.get(name)

    def get_sales_account(self):
        return self._accounts["Revenue"]

    def create_journal_entry(self, description: str, lines: list, voucher_date=None):
        voucher = type(
            "V",
            (),
            {"id": f"v-{len(self.journals)+1}", "voucher_number": f"JV-{len(self.journals)+1}"},
        )()
        self.journals.append(
            {"description": description, "lines": lines, "voucher": voucher}
        )
        return voucher


@pytest.fixture
def customer() -> Customer:
    return Customer(customer_name="Wave8 Co", phone_number="9888888888", id="cust_w8")


@pytest.fixture
def project_ctx(customer):
    customers = FakeCustomerRepository()
    customers.save(customer)
    projects = FakeProjectRepository()
    templates = FakeProjectTemplateRepository()
    counters = FakeCounterRepository()
    project_svc = ProjectAppService(projects, templates, counters, customers)
    project = project_svc.create_project(
        name="Tower B",
        customer_id=customer.id,
        contract_value=200_000,
    )
    project.overhead_allocation_pct = 10.0
    projects.save(project)
    return {
        "projects": projects,
        "project": project,
        "project_svc": project_svc,
        "expenses": FakeExpenseRepo(),
        "recog_repo": FakeRecognitionRepo(),
    }


def test_recognition_post_status_and_journal_stub(project_ctx):
    svc = ProjectRecognitionAppService(
        project_ctx["recog_repo"], project_ctx["projects"]
    )
    entry = svc.draft_recognition(
        project_ctx["project"].id,
        date.today(),
        ProjectRecognitionMethod.PERCENT_COMPLETE,
        percent_complete=50,
        billed_to_date=50_000,
    )
    approved = svc.approve(entry.id)
    assert approved.status == ProjectRecognitionStatus.APPROVED
    posted = svc.post(approved.id)
    assert posted.status == ProjectRecognitionStatus.POSTED
    assert posted.journal_stub is not None
    assert posted.journal_stub.get("balanced") is True
    assert posted.journal_stub.get("posted_via") == "stub"
    assert len(posted.journal_stub.get("lines") or []) == 2


def test_recognition_post_via_accounting(project_ctx):
    accounting = FakeAccountingWithJournal()
    svc = ProjectRecognitionAppService(
        project_ctx["recog_repo"],
        project_ctx["projects"],
        accounting_service=accounting,
    )
    entry = svc.draft_recognition(
        project_ctx["project"].id,
        date.today(),
        ProjectRecognitionMethod.PERCENT_COMPLETE,
        percent_complete=25,
        billed_to_date=0,
    )
    svc.approve(entry.id)
    posted = svc.post(entry.id)
    assert posted.status == ProjectRecognitionStatus.POSTED
    assert posted.journal_stub.get("posted_via") == "accounting"
    assert posted.voucher_id
    assert len(accounting.journals) == 1
    lines = accounting.journals[0]["lines"]
    debit = sum(float(l.get("debit_amount") or 0) for l in lines)
    credit = sum(float(l.get("credit_amount") or 0) for l in lines)
    assert debit == pytest.approx(credit)


def test_offline_draft_sync(project_ctx):
    offline = ProjectOfflineAppService(project_repo=project_ctx["projects"])
    draft = offline.save_draft(
        project_ctx["project"].id,
        "Progress",
        {"percent": 40},
        device_id="phone-1",
    )
    assert draft.synced is False
    pending = offline.list_drafts(project_ctx["project"].id, pending_only=True)
    assert len(pending) == 1
    synced = offline.sync_draft(draft.id)
    assert synced.synced is True
    assert synced.synced_at is not None
    assert offline.list_drafts(project_ctx["project"].id, pending_only=True) == []


def test_portal_token_validate(project_ctx):
    portal = ProjectPortalAppService(project_repo=project_ctx["projects"])
    token = portal.create_portal_token(
        project_ctx["project"].id, scope="measurement", expires_in_days=7
    )
    validated = portal.validate_portal_token(token.token)
    assert validated.project_id == project_ctx["project"].id
    assert validated.scope == "measurement"
    with pytest.raises(ValidationError, match="Invalid"):
        portal.validate_portal_token("not-a-real-token")


def test_overhead_allocate(project_ctx):
    expenses = project_ctx["expenses"]
    expenses.save(
        ProjectExpense(
            project_id=project_ctx["project"].id,
            expense_date=date.today(),
            expense_name="Cement",
            expense_source=ProjectExpenseSource.MATERIAL,
            amount=50_000,
            cost_category="Material",
        )
    )
    svc = ProjectRecognitionAppService(
        project_ctx["recog_repo"],
        project_ctx["projects"],
        expense_repo=expenses,
    )
    result = svc.allocate_overhead(project_ctx["project"].id)
    assert result["amount"] == pytest.approx(5_000.0)
    assert result["expense_id"]
    oh = expenses.find_by_id(result["expense_id"])
    assert oh is not None
    assert oh.cost_category == "HO OH"
    assert oh.amount == pytest.approx(5_000.0)
