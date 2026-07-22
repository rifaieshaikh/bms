"""PRD MVP acceptance tests — BOQ, measurements, RA dual, budget, closure."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
from typing import Dict, List, Optional

import pytest

from tests.conftest import FakeCounterRepository, FakeCustomerRepository
from tests.test_project_billing import FakeRARepository, FakeWorkOrderRepository
from tests.test_project_quotations import FakeProjectQuotationRepository
from tests.test_projects_module import FakeProjectRepository, FakeProjectTemplateRepository
from vaybooks.bms.application.projects.core.service import ProjectAppService
from vaybooks.bms.application.projects.billing.service import ProjectBillingAppService
from vaybooks.bms.application.projects.boq.service import ProjectBoqAppService
from vaybooks.bms.application.projects.budget.service import ProjectBudgetAppService
from vaybooks.bms.application.projects.measurements.service import (
    ProjectMeasurementAppService,
)
from vaybooks.bms.application.projects.quotations.service import ProjectQuotationAppService
from vaybooks.bms.domain.finance.accounting.entities import Voucher, VoucherLine
from vaybooks.bms.domain.parties.customers.entities import Customer
from vaybooks.bms.domain.projects.boq import ProjectBoqItem
from vaybooks.bms.domain.projects.budget import ProjectBudgetLine, ProjectBudgetRevision
from vaybooks.bms.domain.projects.entities import (
    ProjectTemplate,
    ProjectTemplateActivity,
)
from vaybooks.bms.domain.projects.measurement import ProjectMeasurement
from vaybooks.bms.domain.shared.enums import (
    ProjectCostCategory,
    ProjectMeasurementStatus,
    ProjectQuotationStatus,
    ProjectRABillStatus,
    ProjectStatus,
    VoucherType,
)
from vaybooks.bms.domain.shared.exceptions import ValidationError


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
        return [
            deepcopy(i)
            for i in self._store.values()
            if i.project_id == project_id
        ]

    def delete(self, item_id: str) -> None:
        self._store.pop(item_id, None)


class FakeBudgetRepository:
    def __init__(self):
        self._lines: Dict[str, ProjectBudgetLine] = {}
        self._revisions: List[ProjectBudgetRevision] = []

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
            deepcopy(l)
            for l in self._lines.values()
            if l.project_id == project_id
        ]

    def save_revision(self, revision: ProjectBudgetRevision) -> ProjectBudgetRevision:
        self._revisions.append(revision)
        return revision

    def list_revisions_by_project(self, project_id: str) -> List[ProjectBudgetRevision]:
        return [r for r in self._revisions if r.project_id == project_id]


class FakeMeasurementRepository:
    def __init__(self):
        self._store: Dict[str, ProjectMeasurement] = {}

    def save(self, measurement: ProjectMeasurement) -> ProjectMeasurement:
        self._store[measurement.id] = measurement
        return measurement

    def find_by_id(self, measurement_id: str) -> Optional[ProjectMeasurement]:
        m = self._store.get(measurement_id)
        return deepcopy(m) if m else None

    def list_by_project(self, project_id: str) -> List[ProjectMeasurement]:
        return [
            deepcopy(m)
            for m in self._store.values()
            if m.project_id == project_id
        ]

    def list_by_boq_item(self, boq_item_id: str) -> List[ProjectMeasurement]:
        return [
            deepcopy(m)
            for m in self._store.values()
            if m.boq_item_id == boq_item_id
        ]

    def delete(self, measurement_id: str) -> None:
        self._store.pop(measurement_id, None)


class FakeAccount:
    def __init__(self, account_id: str = "cust-acct"):
        self.id = account_id


class FakeAccountingService:
    def get_customer_account(self, customer_id: str):
        return FakeAccount()

    def get_discount_account(self):
        return None

    def list_vouchers_by_project(self, project_id: str):
        return []


class FakeSalesService:
    last_line_items: list | None = None

    def create_sales_invoice(self, **kwargs):
        FakeSalesService.last_line_items = kwargs.get("line_items")
        gross = sum(
            float(item.get("qty") or item.get("quantity") or 1)
            * float(item.get("rate") or 0)
            for item in (kwargs.get("line_items") or [])
        )
        voucher = Voucher(
            voucher_number=kwargs.get("store_invoice_number") or "INV-TEST",
            voucher_type=VoucherType.SALES_INVOICE,
            voucher_date=datetime.utcnow(),
            description="Test invoice",
            lines=[
                VoucherLine(
                    account_id="rev",
                    account_name="Revenue",
                    credit_amount=gross,
                ),
                VoucherLine(
                    account_id="ar",
                    account_name="AR",
                    debit_amount=gross,
                ),
            ],
        )
        return voucher


@pytest.fixture
def mvp_stack():
    customer_repo = FakeCustomerRepository()
    customer = Customer(customer_name="MVP Customer", phone_number="7777777777")
    customer_repo.save(customer)
    template = ProjectTemplate(
        id="tpl-mvp",
        name="Blank",
        activities=[ProjectTemplateActivity(id="ta1", name="Work", sort_order=1)],
    )
    project_repo = FakeProjectRepository()
    boq_repo = FakeBoqRepository()
    budget_repo = FakeBudgetRepository()
    measurement_repo = FakeMeasurementRepository()
    quotation_repo = FakeProjectQuotationRepository()
    ra_repo = FakeRARepository()
    counter_repo = FakeCounterRepository()

    projects = ProjectAppService(
        project_repo,
        FakeProjectTemplateRepository([template]),
        counter_repo,
        customer_repo,
    )
    project = projects.create_project_from_template(
        template.id,
        name="MVP Project",
        customer_id=customer.id,
        contract_value=0,
    )
    boq = ProjectBoqAppService(boq_repo, project_repo)
    budget = ProjectBudgetAppService(budget_repo, project_repo)
    measurement = ProjectMeasurementAppService(
        measurement_repo, boq_repo, project_repo, ra_repo=ra_repo
    )
    quotations = ProjectQuotationAppService(
        quotation_repo,
        project_repo,
        counter_repo,
        boq_repo=boq_repo,
        boq_service=boq,
        work_order_repo=FakeWorkOrderRepository(),
    )
    billing = ProjectBillingAppService(
        project_repo,
        FakeWorkOrderRepository(),
        counter_repo,
        accounting_service=FakeAccountingService(),
        sales_service=FakeSalesService(),
        ra_repo=ra_repo,
        boq_repo=boq_repo,
        measurement_repo=measurement_repo,
        measurement_service=measurement,
    )

    return {
        "project": project,
        "project_repo": project_repo,
        "projects": projects,
        "boq": boq,
        "boq_repo": boq_repo,
        "budget": budget,
        "budget_repo": budget_repo,
        "measurement": measurement,
        "measurement_repo": measurement_repo,
        "quotations": quotations,
        "billing": billing,
        "ra_repo": ra_repo,
    }


def test_boq_quotation_convert_sets_contract_baseline(mvp_stack):
    project = mvp_stack["project"]
    boq = mvp_stack["boq"]
    boq_repo = mvp_stack["boq_repo"]
    quotations = mvp_stack["quotations"]
    project_repo = mvp_stack["project_repo"]

    item = boq.create_item(
        project.id,
        "1.1",
        "Flooring",
        estimated_qty=100,
        selling_rate=500,
    )

    quotation = quotations.create_quotation(
        project.id,
        lines=[
            {
                "description": item.description,
                "quantity": 80,
                "rate": 450,
                "boq_item_id": item.id,
            }
        ],
    )
    quotations.submit_for_approval(quotation.id)
    quotations.approve_quotation(quotation.id)
    quotations.convert_to_project(quotation.id, create_work_order=False)

    updated_project = project_repo._store[project.id]
    assert updated_project.contract_approved is True
    assert updated_project.contract_value == 80 * 450

    saved_item = boq_repo._store[item.id]
    assert saved_item.contracted_qty == 80
    assert saved_item.contracted_rate == 450


def test_measurement_double_bill_guard(mvp_stack):
    project = mvp_stack["project"]
    boq = mvp_stack["boq"]
    measurement = mvp_stack["measurement"]
    billing = mvp_stack["billing"]

    item = boq.create_item(
        project.id,
        "2.1",
        "Wiring",
        estimated_qty=50,
        selling_rate=200,
    )
    boq.update_item(item.id, contracted_qty=50, contracted_rate=200)
    m1 = measurement.create(project.id, item.id, date.today(), 10)
    measurement.submit(m1.id)
    measurement.verify(m1.id)

    ra1 = billing.create_ra_from_measurements(project.id, [m1.id])
    assert ra1.id

    m2 = measurement.create(project.id, item.id, date.today(), 5)
    measurement.submit(m2.id)
    measurement.verify(m2.id)

    with pytest.raises(ValidationError, match="already linked"):
        billing.create_ra_from_measurements(project.id, [m1.id])

    ra2 = billing.create_ra_from_measurements(project.id, [m2.id])
    assert ra2.id != ra1.id


def test_ra_invoice_uses_certified_not_claimed(mvp_stack):
    project = mvp_stack["project"]
    boq = mvp_stack["boq"]
    measurement = mvp_stack["measurement"]
    billing = mvp_stack["billing"]

    item = boq.create_item(
        project.id,
        "3.1",
        "Painting",
        estimated_qty=100,
        selling_rate=100,
    )
    boq.update_item(item.id, contracted_qty=100, contracted_rate=100)
    m = measurement.create(project.id, item.id, date.today(), 10)
    measurement.submit(m.id)
    measurement.verify(m.id)

    ra = billing.create_ra_from_measurements(project.id, [m.id])
    assert ra.gross_claimed == 1000
    assert ra.gross_certified == 0

    certified = billing.certify_ra(
        ra.id,
        [{"line_id": ra.lines[0].id, "current_certified_qty": 6.0}],
    )
    assert certified.gross_claimed == 1000
    assert certified.gross_certified == 600

    billing.convert_ra_to_invoice(ra.id, store_account_id="store-1")
    assert FakeSalesService.last_line_items is not None
    invoice_qty = float(FakeSalesService.last_line_items[0]["qty"])
    assert invoice_qty == 6.0


def test_budget_baseline_immutable_on_revise(mvp_stack):
    project = mvp_stack["project"]
    budget = mvp_stack["budget"]
    budget_repo = mvp_stack["budget_repo"]

    line = budget.add_line(
        project.id,
        ProjectCostCategory.MATERIAL,
        100_000,
    )
    revised = budget.revise_line(line.id, 120_000, reason="Scope increase")

    assert revised.original_amount == 100_000
    assert revised.revised_amount == 120_000
    stored = budget_repo._lines[line.id]
    assert stored.original_amount == 100_000
    assert stored.revised_amount == 120_000


def test_uncertified_measurement_blocks_financial_close(mvp_stack):
    project = mvp_stack["project"]
    boq = mvp_stack["boq"]
    measurement = mvp_stack["measurement"]
    projects = mvp_stack["projects"]
    billing = mvp_stack["billing"]

    item = boq.create_item(
        project.id,
        "4.1",
        "Plaster",
        estimated_qty=20,
        selling_rate=300,
    )
    boq.update_item(item.id, contracted_qty=20, contracted_rate=300)
    m = measurement.create(project.id, item.id, date.today(), 5)
    measurement.submit(m.id)

    blockers = projects.get_closure_blockers(
        project.id,
        billing_service=billing,
        measurement_service=measurement,
    )
    assert any(b.get("type") == "uncertified_measurements" for b in blockers)

    with pytest.raises(ValidationError, match="cannot be closed"):
        projects.close_project(
            project.id,
            billing_service=billing,
            measurement_service=measurement,
        )

    measurement.verify(m.id)
    measurement.certify(m.id)

    blockers_after = projects.get_closure_blockers(
        project.id,
        billing_service=billing,
        measurement_service=measurement,
    )
    assert not any(b.get("type") == "uncertified_measurements" for b in blockers_after)
