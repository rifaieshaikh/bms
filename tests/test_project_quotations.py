"""Unit tests for project quotation workflow."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Dict, List, Optional

import pytest

from tests.conftest import FakeCounterRepository, FakeCustomerRepository
from tests.test_projects_module import (
    FakeProjectDocumentRepository,
    FakeProjectRepository,
    FakeProjectTemplateRepository,
)
from tests.test_sales_workflow import FakeBusinessService
from vaybooks.bms.application.project_app_service import ProjectAppService
from vaybooks.bms.application.project_boq_app_service import ProjectBoqAppService
from vaybooks.bms.application.project_document_app_service import ProjectDocumentAppService
from vaybooks.bms.application.project_quotation_app_service import ProjectQuotationAppService
from vaybooks.bms.domain.customers.entities import Customer
from vaybooks.bms.domain.projects.entities import (
    Project,
    ProjectQuotation,
    ProjectTemplate,
    ProjectTemplateActivity,
    ProjectWorkOrder,
)
from vaybooks.bms.domain.projects.boq import ProjectBoqItem
from vaybooks.bms.domain.shared.enums import ProjectQuotationStatus
from vaybooks.bms.domain.shared.exceptions import ValidationError


class FakeProjectQuotationRepository:
    def __init__(self):
        self._store: Dict[str, ProjectQuotation] = {}

    def save(self, quotation: ProjectQuotation) -> ProjectQuotation:
        self._store[quotation.id] = quotation
        return quotation

    def find_by_id(self, quotation_id: str) -> Optional[ProjectQuotation]:
        item = self._store.get(quotation_id)
        return deepcopy(item) if item else None

    def list_by_project(self, project_id: str) -> List[ProjectQuotation]:
        return [
            deepcopy(q)
            for q in self._store.values()
            if q.project_id == project_id
        ]

    def list_all(self) -> List[ProjectQuotation]:
        return [deepcopy(q) for q in self._store.values()]


class FakeProjectWorkOrderRepository:
    def __init__(self):
        self._store: Dict[str, ProjectWorkOrder] = {}

    def save(self, work_order: ProjectWorkOrder) -> ProjectWorkOrder:
        self._store[work_order.id] = work_order
        return work_order

    def find_by_id(self, wo_id: str) -> Optional[ProjectWorkOrder]:
        return self._store.get(wo_id)

    def list_by_project(self, project_id: str) -> List[ProjectWorkOrder]:
        return [wo for wo in self._store.values() if wo.project_id == project_id]


class FakeBoqRepository:
    def __init__(self):
        self._store: Dict[str, ProjectBoqItem] = {}

    def save(self, item: ProjectBoqItem) -> ProjectBoqItem:
        self._store[item.id] = item
        return item

    def save_many(self, items: List[ProjectBoqItem]) -> List[ProjectBoqItem]:
        for item in items:
            self.save(item)
        return items

    def find_by_id(self, item_id: str) -> Optional[ProjectBoqItem]:
        item = self._store.get(item_id)
        return deepcopy(item) if item else None

    def list_by_project(self, project_id: str) -> List[ProjectBoqItem]:
        return [deepcopy(i) for i in self._store.values() if i.project_id == project_id]

    def delete(self, item_id: str) -> None:
        self._store.pop(item_id, None)


@pytest.fixture
def quotation_stack():
    blank_template = ProjectTemplate(
        id="tpl-blank",
        name="Blank",
        activities=[ProjectTemplateActivity(id="ta1", name="Work A", sort_order=1)],
    )
    customer_repo = FakeCustomerRepository()
    customer = Customer(customer_name="Test Customer", phone_number="9999999999")
    customer_repo.save(customer)
    project_repo = FakeProjectRepository()
    quotation_repo = FakeProjectQuotationRepository()
    work_order_repo = FakeProjectWorkOrderRepository()
    boq_repo = FakeBoqRepository()
    counter_repo = FakeCounterRepository()
    document_repo = FakeProjectDocumentRepository()
    document_service = ProjectDocumentAppService(document_repo, project_repo)
    projects = ProjectAppService(
        project_repo,
        FakeProjectTemplateRepository([blank_template]),
        counter_repo,
        customer_repo,
    )
    project = projects.create_project_from_template(
        blank_template.id,
        name="Quotation Project",
        customer_id=customer.id,
        contract_value=0,
    )
    quotations = ProjectQuotationAppService(
        quotation_repo,
        project_repo,
        counter_repo,
        document_service=document_service,
        business_service=FakeBusinessService(),
        work_order_repo=work_order_repo,
        boq_repo=boq_repo,
        boq_service=ProjectBoqAppService(boq_repo, project_repo),
    )
    return {
        "project": project,
        "project_repo": project_repo,
        "quotation_repo": quotation_repo,
        "work_order_repo": work_order_repo,
        "quotations": quotations,
    }


def _line(description: str, quantity: float, rate: float) -> dict:
    return {"description": description, "quantity": quantity, "rate": rate}


def test_create_submit_approve_convert_sets_contract_value(quotation_stack):
    project = quotation_stack["project"]
    svc = quotation_stack["quotations"]
    project_repo = quotation_stack["project_repo"]
    work_order_repo = quotation_stack["work_order_repo"]

    quotation = svc.create_quotation(
        project.id,
        quotation_date=date(2026, 7, 1),
        lines=[_line("Design work", 10, 500)],
    )
    svc.submit_for_approval(quotation.id)
    svc.approve_quotation(quotation.id, approved_by="manager")

    result = svc.convert_to_project(quotation.id)

    assert result["project_id"] == project.id
    assert result["quotation_id"] == quotation.id
    assert result["contract_value"] == 5000
    assert result["wo_id"]

    updated_project = project_repo._store[project.id]
    assert updated_project.contract_value == 5000

    converted = svc.get_quotation(quotation.id)
    assert converted.status == ProjectQuotationStatus.CONVERTED

    work_orders = work_order_repo.list_by_project(project.id)
    assert len(work_orders) == 1
    assert work_orders[0].quotation_id == quotation.id


def test_revise_supersedes_prior(quotation_stack):
    project = quotation_stack["project"]
    svc = quotation_stack["quotations"]
    quotation_repo = quotation_stack["quotation_repo"]

    original = svc.create_quotation(
        project.id,
        lines=[_line("Phase 1", 1, 1000)],
    )
    svc.submit_for_approval(original.id)
    svc.approve_quotation(original.id)

    revision = svc.revise_quotation(original.id)

    prior = quotation_repo._store[original.id]
    assert prior.status == ProjectQuotationStatus.SUPERSEDED
    assert revision.status == ProjectQuotationStatus.DRAFT
    assert revision.revision_no == 2
    assert revision.root_id == original.root_id
    assert revision.supersedes_id == original.id


def test_reject_and_send_guards(quotation_stack):
    project = quotation_stack["project"]
    svc = quotation_stack["quotations"]

    quotation = svc.create_quotation(
        project.id,
        lines=[_line("Consulting", 5, 200)],
    )

    with pytest.raises(ValidationError, match="approved"):
        svc.send_quotation(quotation.id)

    svc.submit_for_approval(quotation.id)
    svc.approve_quotation(quotation.id)

    with pytest.raises(ValidationError, match="sent"):
        svc.reject_quotation(quotation.id)

    svc.send_quotation(quotation.id)
    rejected = svc.reject_quotation(quotation.id)
    assert rejected.status == ProjectQuotationStatus.REJECTED

    with pytest.raises(ValidationError, match="sent"):
        svc.accept_quotation(quotation.id)


def test_request_changes_returns_to_draft(quotation_stack):
    project = quotation_stack["project"]
    svc = quotation_stack["quotations"]

    quotation = svc.create_quotation(
        project.id,
        lines=[_line("Review", 1, 100)],
    )
    svc.submit_for_approval(quotation.id)
    updated = svc.request_changes(quotation.id)
    assert updated.status == ProjectQuotationStatus.DRAFT

    with pytest.raises(ValidationError, match="pending approval"):
        svc.request_changes(quotation.id)
