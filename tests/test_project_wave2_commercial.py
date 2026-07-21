"""Wave 2 commercial tests — AC-001 quotation spine + compare_revisions."""

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
from vaybooks.bms.application.project_access_policy import ProjectAccessPolicy
from vaybooks.bms.application.project_app_service import ProjectAppService
from vaybooks.bms.application.project_boq_app_service import ProjectBoqAppService
from vaybooks.bms.application.project_document_app_service import ProjectDocumentAppService
from vaybooks.bms.application.project_quotation_app_service import ProjectQuotationAppService
from vaybooks.bms.domain.customers.entities import Customer
from vaybooks.bms.domain.projects.boq import ProjectBoqItem
from vaybooks.bms.domain.projects.entities import (
    ProjectQuotation,
    ProjectTemplate,
    ProjectTemplateActivity,
    ProjectWorkOrder,
)
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
def commercial_stack():
    blank_template = ProjectTemplate(
        id="tpl-blank",
        name="Blank",
        activities=[ProjectTemplateActivity(id="ta1", name="Work A", sort_order=1)],
    )
    customer_repo = FakeCustomerRepository()
    customer = Customer(customer_name="AC-001 Customer", phone_number="9888888888")
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
        name="AC-001 Project",
        customer_id=customer.id,
        contract_value=0,
    )
    access = ProjectAccessPolicy(maker_checker_enabled=True)
    quotations = ProjectQuotationAppService(
        quotation_repo,
        project_repo,
        counter_repo,
        document_service=document_service,
        business_service=FakeBusinessService(),
        work_order_repo=work_order_repo,
        boq_repo=boq_repo,
        boq_service=ProjectBoqAppService(boq_repo, project_repo),
        access_policy=access,
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


def test_ac001_create_submit_approve_accept_convert(commercial_stack):
    """AC-001: create → submit → approve (different actor) → accept → convert."""
    project = commercial_stack["project"]
    svc = commercial_stack["quotations"]
    project_repo = commercial_stack["project_repo"]

    quote = svc.create_quotation(
        project.id,
        quotation_date=date(2026, 7, 1),
        lines=[_line("Foundation", 10, 1000)],
        created_by="estimator",
    )
    assert quote.status == ProjectQuotationStatus.DRAFT
    assert quote.root_id == quote.id

    submitted = svc.submit_for_approval(quote.id, submitted_by="estimator")
    assert submitted.status == ProjectQuotationStatus.PENDING_APPROVAL
    assert submitted.submitted_by == "estimator"

    with pytest.raises(ValidationError):
        svc.approve_quotation(quote.id, approved_by="estimator")

    approved = svc.approve_quotation(quote.id, approved_by="commercial_approver")
    assert approved.status == ProjectQuotationStatus.APPROVED
    assert approved.approved_by == "commercial_approver"

    sent = svc.send_quotation(quote.id)
    assert sent.status == ProjectQuotationStatus.SENT

    accepted = svc.accept_quotation(
        quote.id,
        confirmation_note="PO attached",
        confirmation_evidence="PO-7788.pdf",
    )
    assert accepted.status == ProjectQuotationStatus.ACCEPTED
    assert accepted.confirmation_evidence == "PO-7788.pdf"
    assert accepted.confirmation_note == "PO attached"

    result = svc.convert_to_project(quote.id)
    assert result["project_id"] == project.id
    assert result["contract_value"] == 10000
    assert result["wo_id"]

    converted = svc.get_quotation(quote.id)
    assert converted.status == ProjectQuotationStatus.CONVERTED
    updated = project_repo._store[project.id]
    assert updated.contract_value == 10000
    assert updated.contract_approved is True


def test_compare_revisions_line_diffs(commercial_stack):
    project = commercial_stack["project"]
    svc = commercial_stack["quotations"]

    original = svc.create_quotation(
        project.id,
        lines=[_line("Phase 1", 1, 1000), _line("Phase 2", 2, 500)],
    )
    svc.submit_for_approval(original.id, submitted_by="estimator")
    svc.approve_quotation(original.id, approved_by="approver")

    revision = svc.revise_quotation(original.id)
    svc.update_quotation(
        revision.id,
        lines=[
            _line("Phase 1", 1, 1200),
            _line("Phase 3", 1, 800),
        ],
    )

    comparison = svc.compare_revisions(original.root_id)
    assert comparison["root_id"] == original.root_id
    assert comparison["revision_count"] == 2
    assert len(comparison["diffs"]) == 1

    diff = comparison["diffs"][0]
    assert diff["from_revision"] == 1
    assert diff["to_revision"] == 2
    assert any(row["description"] == "Phase 3" for row in diff["added"])
    assert any(row["description"] == "Phase 2" for row in diff["removed"])
    assert any(
        row["before"]["description"] == "Phase 1"
        and row["after"]["rate"] == 1200
        for row in diff["changed"]
    )


def test_generate_pdf_strip_internal_flag(commercial_stack):
    project = commercial_stack["project"]
    svc = commercial_stack["quotations"]
    quote = svc.create_quotation(
        project.id,
        lines=[_line("Design", 1, 5000)],
    )
    pdf = svc.generate_pdf(quote.id, strip_internal=True)
    assert isinstance(pdf, (bytes, bytearray))
    assert len(pdf) > 0
