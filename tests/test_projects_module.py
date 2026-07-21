"""Unit tests for the Projects module."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Dict, List, Optional
from uuid import uuid4

import pytest

from vaybooks.bms.application.project_app_service import ProjectAppService
from vaybooks.bms.application.project_document_app_service import ProjectDocumentAppService
from vaybooks.bms.application.project_expense_app_service import ProjectExpenseAppService
from vaybooks.bms.application.project_profitability_service import ProjectProfitabilityService
from vaybooks.bms.application.project_time_app_service import ProjectTimeAppService
from vaybooks.bms.domain.customers.entities import Customer
from vaybooks.bms.domain.projects.entities import (
    Project,
    ProjectActivity,
    ProjectDocument,
    ProjectExpense,
    ProjectTemplate,
    ProjectTemplateActivity,
    ProjectTimeEntry,
)
from vaybooks.bms.domain.projects.profitability import ProjectProfitabilityCalculator
from vaybooks.bms.domain.projects.services import ProjectDomainService
from vaybooks.bms.domain.shared.enums import ProjectDocumentCategory, ProjectExpenseSource
from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.domain.workers.entities import Worker
from tests.conftest import FakeCounterRepository, FakeCustomerRepository


class FakeProjectTemplateRepository:
    def __init__(self, templates: Optional[List[ProjectTemplate]] = None):
        self._store = {t.id: t for t in (templates or [])}

    def save(self, template: ProjectTemplate) -> ProjectTemplate:
        self._store[template.id] = template
        return template

    def find_by_id(self, template_id: str) -> Optional[ProjectTemplate]:
        return self._store.get(template_id)

    def list_all(self) -> List[ProjectTemplate]:
        return list(self._store.values())

    def delete(self, template_id: str) -> None:
        self._store.pop(template_id, None)


class FakeProjectRepository:
    def __init__(self):
        self._store: Dict[str, Project] = {}

    def save(self, project: Project) -> Project:
        self._store[project.id] = project
        return project

    def find_by_id(self, project_id: str) -> Optional[Project]:
        return deepcopy(self._store.get(project_id))

    def list_all(self, status=None) -> List[Project]:
        items = list(self._store.values())
        if status is not None:
            items = [p for p in items if p.status == status]
        return deepcopy(items)

    def search(self, query: str = "") -> List[Project]:
        q = (query or "").lower()
        if not q:
            return self.list_all()
        return [
            p
            for p in self.list_all()
            if q in p.name.lower() or q in p.project_number.lower()
        ]


class FakeProjectDocumentRepository:
    def __init__(self):
        self._store: Dict[str, ProjectDocument] = {}

    def save(self, document: ProjectDocument) -> ProjectDocument:
        self._store[document.id] = document
        return document

    def find_by_id(self, document_id: str) -> Optional[ProjectDocument]:
        return self._store.get(document_id)

    def list_by_project(self, project_id, include_deleted=False, category=None):
        docs = [d for d in self._store.values() if d.project_id == project_id]
        if not include_deleted:
            docs = [d for d in docs if not d.is_deleted]
        if category is not None:
            docs = [d for d in docs if d.category == category]
        return docs

    def soft_delete(self, document_id: str) -> None:
        doc = self._store.get(document_id)
        if doc:
            doc.is_deleted = True


class FakeProjectTimeRepository:
    def __init__(self):
        self._store: Dict[str, ProjectTimeEntry] = {}

    def save(self, entry: ProjectTimeEntry) -> ProjectTimeEntry:
        self._store[entry.id] = entry
        return entry

    def save_many(self, entries: List[ProjectTimeEntry]) -> List[ProjectTimeEntry]:
        for entry in entries:
            self.save(entry)
        return entries

    def find_by_id(self, entry_id: str) -> Optional[ProjectTimeEntry]:
        return self._store.get(entry_id)

    def list_by_project(self, project_id: str) -> List[ProjectTimeEntry]:
        return [e for e in self._store.values() if e.project_id == project_id]

    def list_by_activity(self, activity_id: str) -> List[ProjectTimeEntry]:
        return [e for e in self._store.values() if e.activity_id == activity_id]

    def delete(self, entry_id: str) -> None:
        self._store.pop(entry_id, None)


class FakeProjectExpenseRepository:
    def __init__(self):
        self._store: Dict[str, ProjectExpense] = {}

    def save(self, expense: ProjectExpense) -> ProjectExpense:
        self._store[expense.id] = expense
        return expense

    def find_by_id(self, expense_id: str) -> Optional[ProjectExpense]:
        return self._store.get(expense_id)

    def list_by_project(self, project_id: str) -> List[ProjectExpense]:
        return [e for e in self._store.values() if e.project_id == project_id]

    def delete(self, expense_id: str) -> None:
        self._store.pop(expense_id, None)


class FakeWorkerRepository:
    def __init__(self, workers: Optional[List[Worker]] = None):
        self._store = {w.id: w for w in (workers or [])}

    def save(self, worker: Worker) -> Worker:
        self._store[worker.id] = worker
        return worker

    def find_by_id(self, worker_id: str) -> Optional[Worker]:
        return self._store.get(worker_id)

    def list_all(self, active_only: bool = True) -> List[Worker]:
        items = list(self._store.values())
        if active_only:
            items = [w for w in items if w.is_active]
        return items

    def list_by_activity(self, activity_id: str, active_only: bool = True) -> List[Worker]:
        return self.list_all(active_only)


@pytest.fixture
def blank_template() -> ProjectTemplate:
    return ProjectTemplate(
        id="tpl-blank",
        name="Blank",
        activities=[
            ProjectTemplateActivity(id="ta1", name="Work A", sort_order=1),
            ProjectTemplateActivity(id="ta2", name="Work B", sort_order=2),
        ],
    )


@pytest.fixture
def project_services(blank_template):
    customer_repo = FakeCustomerRepository()
    customer = Customer(customer_name="Test Customer", phone_number="9999999999")
    customer_repo.save(customer)
    template_repo = FakeProjectTemplateRepository([blank_template])
    project_repo = FakeProjectRepository()
    counter_repo = FakeCounterRepository()
    return {
        "customer": customer,
        "project_repo": project_repo,
        "projects": ProjectAppService(
            project_repo, template_repo, counter_repo, customer_repo
        ),
        "documents": ProjectDocumentAppService(
            FakeProjectDocumentRepository(), project_repo
        ),
        "time_repo": FakeProjectTimeRepository(),
        "expense_repo": FakeProjectExpenseRepository(),
    }


def test_create_project_with_contract_value(project_services, blank_template):
    customer = project_services["customer"]
    project = project_services["projects"].create_project_from_template(
        blank_template.id,
        name="Apartment Reno",
        customer_id=customer.id,
        contract_value=800_000,
        site_address="Mumbai",
        site_state_code="MH",
    )
    assert project.contract_value == 800_000
    assert project.customer_id == customer.id
    assert len(project.activities) == 2


def test_parent_activity_cannot_have_planned_revenue(project_services):
    customer = project_services["customer"]
    parent = ProjectActivity(name="Parent", sort_order=1)
    child = ProjectActivity(
        name="Child", sort_order=2, parent_activity_id=parent.id
    )
    parent.planned_revenue_amount = 1000
    with pytest.raises(ValidationError):
        project_services["projects"].create_project(
            name="Bad tree",
            customer_id=customer.id,
            contract_value=100_000,
            activities=[parent, child],
        )


def test_document_upload_does_not_touch_boutique_attachments(project_services):
    customer = project_services["customer"]
    project = project_services["projects"].create_project(
        name="Doc test",
        customer_id=customer.id,
        contract_value=50_000,
    )
    doc = project_services["documents"].upload(
        project.id,
        ProjectDocumentCategory.PHOTO.value,
        "site.jpg",
        "image/jpeg",
        b"fake-image-bytes",
    )
    assert doc.project_id == project.id
    assert doc.size_bytes == len(b"fake-image-bytes")


def test_multi_worker_time_mph_fixture(project_services):
    customer = project_services["customer"]
    project = project_services["projects"].create_project(
        name="MPH test",
        customer_id=customer.id,
        contract_value=20_000,
        activities=[ProjectActivity(id="act1", name="Interior", sort_order=1)],
    )
    project.activities[0].planned_revenue_amount = 20_000
    project_services["project_repo"].save(project)

    worker_a = Worker(id="wA", worker_name="A", default_hourly_rate=200)
    worker_b = Worker(id="wB", worker_name="B", default_hourly_rate=350)
    worker_c = Worker(id="wC", worker_name="C", default_hourly_rate=500)
    worker_repo = FakeWorkerRepository([worker_a, worker_b, worker_c])
    time_svc = ProjectTimeAppService(
        project_services["time_repo"],
        project_services["project_repo"],
        worker_repo,
    )
    expense_svc = ProjectExpenseAppService(
        project_services["expense_repo"],
        project_services["project_repo"],
    )

    time_svc.create_time_entries(
        project.id,
        "act1",
        [
            {"worker_id": "wA", "duration_minutes": 480},
            {"worker_id": "wB", "duration_minutes": 480},
        ],
        date(2026, 1, 1),
    )
    time_svc.create_time_entries(
        project.id,
        "act1",
        [
            {"worker_id": "wA", "duration_minutes": 480},
            {"worker_id": "wC", "duration_minutes": 240},
        ],
        date(2026, 1, 2),
    )
    expense_svc.create_expense(
        project.id,
        date(2026, 1, 2),
        "Materials",
        ProjectExpenseSource.MATERIAL,
        2000,
        activity_id="act1",
    )

    profitability = ProjectProfitabilityService(
        project_services["project_repo"],
        project_services["time_repo"],
        project_services["expense_repo"],
    )
    result = profitability.get_project_profitability(project.id)
    assert result.person_hours == 28.0
    assert result.labour_cost == 8000.0
    assert result.other_cost == 2000.0
    assert result.budget_margin == 10000.0
    assert result.budget_mph == pytest.approx(357.14, rel=0.01)


def test_zero_rate_blocks_without_override(project_services):
    customer = project_services["customer"]
    project = project_services["projects"].create_project(
        name="Rate block",
        customer_id=customer.id,
        contract_value=10_000,
        activities=[ProjectActivity(id="act1", name="Work", sort_order=1)],
    )
    worker = Worker(id="w0", worker_name="Unpaid", default_hourly_rate=0)
    time_svc = ProjectTimeAppService(
        project_services["time_repo"],
        project_services["project_repo"],
        FakeWorkerRepository([worker]),
    )
    with pytest.raises(ValidationError):
        time_svc.create_time_entries(
            project.id,
            "act1",
            [{"worker_id": "w0", "duration_minutes": 60}],
            date.today(),
        )


def test_rate_frozen_on_save(project_services):
    customer = project_services["customer"]
    project = project_services["projects"].create_project(
        name="Freeze",
        customer_id=customer.id,
        contract_value=10_000,
        activities=[
            ProjectActivity(
                id="act1", name="Work", sort_order=1, default_hourly_rate=200
            )
        ],
    )
    worker = Worker(id="w1", worker_name="A", default_hourly_rate=999)
    time_svc = ProjectTimeAppService(
        project_services["time_repo"],
        project_services["project_repo"],
        FakeWorkerRepository([worker]),
    )
    entries = time_svc.create_time_entries(
        project.id,
        "act1",
        [{"worker_id": "w1", "duration_minutes": 60}],
        date.today(),
    )
    assert entries[0].hourly_rate == 200.0
    assert entries[0].labour_cost == 200.0


def test_parent_revenue_roll_up():
    parent = ProjectActivity(id="p", name="Parent", sort_order=1)
    child_a = ProjectActivity(
        id="a", name="A", sort_order=2, parent_activity_id="p", planned_revenue_amount=6000
    )
    child_b = ProjectActivity(
        id="b", name="B", sort_order=3, parent_activity_id="p", planned_revenue_amount=4000
    )
    project = Project(
        project_number="PRJ-0001",
        name="Roll-up",
        customer_id="c1",
        customer_name="C",
        activities=[parent, child_a, child_b],
    )
    revenue = ProjectDomainService().roll_up_planned_revenue(project)
    assert revenue["p"] == 10000
    assert revenue["a"] == 6000


def test_portfolio_summary_matches_project_profitability(project_services):
    customer = project_services["customer"]
    project = project_services["projects"].create_project(
        name="Portfolio",
        customer_id=customer.id,
        contract_value=20_000,
        activities=[
            ProjectActivity(
                id="act1", name="Work", sort_order=1, planned_revenue_amount=20_000
            )
        ],
    )
    worker = Worker(id="w1", worker_name="A", default_hourly_rate=200)
    time_svc = ProjectTimeAppService(
        project_services["time_repo"],
        project_services["project_repo"],
        FakeWorkerRepository([worker]),
    )
    time_svc.create_time_entries(
        project.id,
        "act1",
        [{"worker_id": "w1", "duration_minutes": 480}],
        date.today(),
    )
    profitability = ProjectProfitabilityService(
        project_services["project_repo"],
        project_services["time_repo"],
        project_services["expense_repo"],
    )
    detail = profitability.get_project_profitability(project.id)
    portfolio = profitability.portfolio_summary()
    row = next(r for r in portfolio if r["project_id"] == project.id)
    assert row["person_hours"] == detail.person_hours
    assert row["budget_mph"] == detail.budget_mph


def test_create_and_delete_custom_template(project_services):
    svc = project_services["projects"]
    template = svc.create_template(
        "Custom Fit-out",
        description="Office fit-out",
        phase_names=["Design", "Build"],
        activity_names=["Survey", "Civil", "Electrical"],
    )
    assert template.id
    assert template.is_system is False
    assert len(template.phases) == 2
    assert len(template.activities) == 3
    names = {t.name for t in svc.list_templates()}
    assert "Custom Fit-out" in names
    svc.delete_template(template.id)
    assert template.id not in {t.id for t in svc.list_templates()}


def test_cannot_delete_system_template(project_services, blank_template):
    blank_template.is_system = True
    svc = project_services["projects"]
    # ensure fake has system flag persisted
    svc._template_repo.save(blank_template)
    with pytest.raises(ValidationError, match="System templates"):
        svc.delete_template(blank_template.id)


def test_boq_sample_csv_importable(project_services):
    from vaybooks.bms.application.project_boq_app_service import ProjectBoqAppService

    class FakeBoqRepo:
        def __init__(self):
            self._store = {}

        def save(self, item):
            self._store[item.id] = item
            return item

        def save_many(self, items):
            for i in items:
                self.save(i)
            return items

        def find_by_id(self, item_id):
            return self._store.get(item_id)

        def list_by_project(self, project_id):
            return [i for i in self._store.values() if i.project_id == project_id]

        def delete(self, item_id):
            self._store.pop(item_id, None)

    customer = project_services["customer"]
    project = project_services["projects"].create_project(
        "CSV Project", customer.id, 1000
    )
    boq = ProjectBoqAppService(FakeBoqRepo(), project_services["project_repo"])
    sample = boq.sample_csv()
    assert "code,description,item_type" in sample
    result = boq.import_csv(project.id, sample)
    assert len(result["created"]) >= 3
    assert not result["errors"]

