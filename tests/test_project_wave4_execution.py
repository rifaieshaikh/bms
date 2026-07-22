"""Wave 4 execution tests — activity transitions, DPR idempotency, block reason."""

from __future__ import annotations

from datetime import date

import pytest

from vaybooks.bms.application.projects.core.service import ProjectAppService
from vaybooks.bms.application.projects.dpr.service import ProjectDprAppService
from vaybooks.bms.application.projects.quality.service import (
    ProjectQualityConfigAppService,
)
from vaybooks.bms.domain.parties.customers.entities import Customer
from vaybooks.bms.domain.projects.entities import ProjectActivity
from vaybooks.bms.domain.projects.quality_config import ProjectQualityIssue
from vaybooks.bms.domain.shared.enums import (
    ProjectActivityStatus,
    ProjectQualityIssueType,
)
from vaybooks.bms.domain.shared.exceptions import ValidationError
from tests.conftest import FakeCounterRepository, FakeCustomerRepository
from tests.test_project_full_accounting_usecases import FakeDprRepo, FakeQualityRepo
from tests.test_projects_module import FakeProjectRepository, FakeProjectTemplateRepository


@pytest.fixture
def customer() -> Customer:
    return Customer(customer_name="Wave4 Co", phone_number="9111111111", id="cust_w4")


@pytest.fixture
def project_svc(customer):
    customers = FakeCustomerRepository()
    customers.save(customer)
    projects = FakeProjectRepository()
    templates = FakeProjectTemplateRepository()
    counters = FakeCounterRepository()
    svc = ProjectAppService(projects, templates, counters, customers)
    project = svc.create_project(
        name="Site A",
        customer_id=customer.id,
        contract_value=100000,
    )
    return svc, projects, project


def test_predecessor_blocks_start_until_completed(project_svc):
    svc, projects, project = project_svc
    pred = ProjectActivity(name="Foundation", sort_order=1)
    succ = ProjectActivity(
        name="Columns",
        sort_order=2,
        predecessor_ids=[pred.id],
    )
    project.activities = [pred, succ]
    projects.save(project)

    with pytest.raises(ValidationError, match="Predecessor"):
        svc.assert_activity_transition(project.id, succ.id, "In Progress")

    with pytest.raises(ValidationError, match="Predecessor"):
        svc.set_activity_workflow_status(project.id, succ.id, "Completed")

    # Complete predecessor, then successor may start / complete
    svc.set_activity_workflow_status(project.id, pred.id, "Completed")
    svc.assert_activity_transition(project.id, succ.id, "In Progress")
    updated = svc.set_activity_workflow_status(project.id, succ.id, "Completed")
    activity = next(a for a in updated.activities if a.id == succ.id)
    assert activity.status == ProjectActivityStatus.COMPLETED
    assert activity.current_status == "Completed"


def test_block_activity_requires_reason(project_svc):
    svc, projects, project = project_svc
    activity = ProjectActivity(name="Pour slab")
    project.activities = [activity]
    projects.save(project)

    with pytest.raises(ValidationError, match="Block reason"):
        svc.block_activity(project.id, activity.id, reason="")

    with pytest.raises(ValidationError, match="Block reason"):
        svc.assert_activity_transition(
            project.id, activity.id, "Blocked", block_reason="  "
        )

    blocked = svc.block_activity(project.id, activity.id, reason="Rain delay")
    act = next(a for a in blocked.activities if a.id == activity.id)
    assert act.blocked is True
    assert act.block_reason == "Rain delay"
    assert act.current_status == "Blocked"


def test_dpr_double_approve_idempotent(project_svc):
    """AC-014: approve_and_apply is safe to call twice."""
    svc, projects, project = project_svc
    activity = ProjectActivity(name="Plaster", planned_hours=10)
    project.activities = [activity]
    projects.save(project)

    dpr_svc = ProjectDprAppService(FakeDprRepo(), projects)
    dpr = dpr_svc.create_dpr(
        project.id,
        date.today(),
        lines=[{"activity_id": activity.id, "hours": 2}],
        photo_document_ids=["doc_photo_1", "doc_photo_2"],
    )
    assert dpr.photo_document_ids == ["doc_photo_1", "doc_photo_2"]
    dpr_svc.submit(dpr.id)
    first = dpr_svc.approve_and_apply(dpr.id)
    refreshed = projects.find_by_id(project.id)
    pct_after_first = next(
        a.percent_complete for a in refreshed.activities if a.id == activity.id
    )
    second = dpr_svc.approve_and_apply(dpr.id)
    refreshed2 = projects.find_by_id(project.id)
    pct_after_second = next(
        a.percent_complete for a in refreshed2.activities if a.id == activity.id
    )
    assert first.applied is True
    assert second.applied is True
    assert pct_after_first == pct_after_second


def test_create_quality_issue_rework_cost(project_svc):
    svc, projects, project = project_svc
    quality = ProjectQualityConfigAppService(FakeQualityRepo(), projects)
    issue = quality.create_quality_issue(
        project.id,
        "Repaint wall",
        issue_type=ProjectQualityIssueType.REWORK,
        cost_impact=1500.0,
    )
    assert isinstance(issue, ProjectQualityIssue)
    assert issue.is_rework_cost is True
    assert issue.cost_impact == 1500.0

    snag = quality.create_quality_issue(
        project.id, "Chip", issue_type="Snag", cost_impact=50.0, is_rework_cost=False
    )
    assert snag.is_rework_cost is False
