"""Tests for activity CRUD used by Work tab."""

from datetime import date

import pytest

from vaybooks.bms.application.project_app_service import ProjectAppService
from vaybooks.bms.application.project_quotation_app_service import ProjectQuotationAppService
from vaybooks.bms.domain.customers.entities import Customer
from vaybooks.bms.domain.projects.entities import ProjectTemplate, ProjectTemplateActivity
from vaybooks.bms.domain.shared.enums import ProjectActivityStatus
from vaybooks.bms.domain.shared.exceptions import ValidationError
from tests.conftest import FakeCounterRepository, FakeCustomerRepository
from tests.test_projects_module import FakeProjectRepository, FakeProjectTemplateRepository
from tests.test_project_quotations import (
    FakeProjectQuotationRepository,
    FakeProjectWorkOrderRepository,
)


@pytest.fixture
def ctx():
    customer_repo = FakeCustomerRepository()
    customer = Customer(customer_name="UX Cust", phone_number="7777777777")
    customer_repo.save(customer)
    template = ProjectTemplate(id="t1", name="Blank", activities=[])
    project_repo = FakeProjectRepository()
    projects = ProjectAppService(
        project_repo,
        FakeProjectTemplateRepository([template]),
        FakeCounterRepository(),
        customer_repo,
    )
    project = projects.create_project(
        name="UX Project",
        customer_id=customer.id,
        contract_value=500_000,
    )
    return {"projects": projects, "project": project, "project_repo": project_repo, "customer": customer}


def test_add_child_activity_and_planned_revenue(ctx):
    projects = ctx["projects"]
    project = ctx["project"]
    projects.add_activity(project.id, "Interior", planned_revenue_amount=0)
    project = projects.get_project(project.id)
    parent = project.activities[0]
    projects.add_activity(
        project.id,
        "Painting",
        parent_activity_id=parent.id,
        planned_revenue_amount=100_000,
        status=ProjectActivityStatus.IN_PROGRESS,
    )
    project = projects.get_project(project.id)
    child = next(a for a in project.activities if a.name == "Painting")
    assert child.parent_activity_id == parent.id
    assert child.planned_revenue_amount == 100_000
    assert child.status == ProjectActivityStatus.IN_PROGRESS


def test_parent_cannot_keep_revenue_when_has_children(ctx):
    projects = ctx["projects"]
    project = ctx["project"]
    projects.add_activity(project.id, "Parent", planned_revenue_amount=50_000)
    project = projects.get_project(project.id)
    parent = project.activities[0]
    projects.add_activity(project.id, "Child", parent_activity_id=parent.id, planned_revenue_amount=50_000)
    # Updating parent with revenue should zero it because it has children
    projects.update_activity(project.id, parent.id, planned_revenue_amount=999)
    project = projects.get_project(project.id)
    parent = next(a for a in project.activities if a.id == parent.id)
    assert parent.planned_revenue_amount == 0


def test_default_quotation_lines_from_leaves(ctx):
    projects = ctx["projects"]
    project = ctx["project"]
    projects.add_activity(project.id, "Parent")
    project = projects.get_project(project.id)
    parent = project.activities[0]
    projects.add_activity(
        project.id, "Leaf A", parent_activity_id=parent.id, planned_revenue_amount=60_000
    )
    projects.add_activity(
        project.id, "Leaf B", parent_activity_id=parent.id, planned_revenue_amount=40_000
    )
    quotes = ProjectQuotationAppService(
        FakeProjectQuotationRepository(),
        ctx["project_repo"],
        FakeCounterRepository(),
        work_order_repo=FakeProjectWorkOrderRepository(),
    )
    lines = quotes.default_lines_from_activities(project.id)
    assert len(lines) == 2
    assert {ln["description"] for ln in lines} == {"Leaf A", "Leaf B"}
    assert sum(ln["rate"] for ln in lines) == 100_000
