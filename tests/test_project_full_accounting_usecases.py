"""Full project accounting use-case coverage (UC spine through config)."""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

import pytest

from tests.conftest import FakeCounterRepository, FakeCustomerRepository
from tests.test_projects_module import FakeProjectRepository
from vaybooks.bms.application.project_boq_app_service import ProjectBoqAppService
from vaybooks.bms.application.project_budget_app_service import ProjectBudgetAppService
from vaybooks.bms.application.project_dpr_app_service import ProjectDprAppService
from vaybooks.bms.application.project_enquiry_app_service import ProjectEnquiryAppService
from vaybooks.bms.application.project_app_service import ProjectAppService
from vaybooks.bms.application.project_petty_cash_app_service import (
    ProjectPettyCashAppService,
)
from vaybooks.bms.application.project_procurement_app_service import (
    ProjectProcurementAppService,
)
from vaybooks.bms.application.project_quality_config_app_service import (
    ProjectQualityConfigAppService,
)
from vaybooks.bms.application.project_quotation_app_service import (
    ProjectQuotationAppService,
)
from vaybooks.bms.application.project_recognition_app_service import (
    ProjectRecognitionAppService,
)
from vaybooks.bms.application.project_subcontract_app_service import (
    ProjectSubcontractAppService,
)
from vaybooks.bms.domain.customers.entities import Customer
from vaybooks.bms.domain.projects.boq import ProjectBoqItem
from vaybooks.bms.domain.projects.budget import (
    ProjectBudgetHeader,
    ProjectBudgetLine,
    ProjectBudgetRevision,
)
from vaybooks.bms.domain.projects.dpr import ProjectDpr
from vaybooks.bms.domain.projects.enquiry import ProjectEnquiry, ProjectSiteAssessment
from vaybooks.bms.domain.projects.entities import ProjectActivity
from vaybooks.bms.domain.projects.petty_cash import ProjectPettyCashAdvance
from vaybooks.bms.domain.projects.procurement import (
    ProjectMaterialRequest,
    ProjectRfq,
    ProjectSiteStockMovement,
)
from vaybooks.bms.domain.projects.quality_config import (
    ProjectConfigSnapshot,
    ProjectHandover,
    ProjectQualityIssue,
    ProjectWbsNode,
)
from vaybooks.bms.domain.projects.recognition import (
    ProjectRecognitionEntry,
    ProjectReconciliation,
)
from vaybooks.bms.domain.projects.subcontract import ProjectSubcontractOrder
from vaybooks.bms.domain.shared.enums import (
    ProjectBudgetStatus,
    ProjectCostCategory,
    ProjectEnquiryStatus,
    ProjectMaterialOwnership,
    ProjectQuotationStatus,
    ProjectRecognitionMethod,
    ProjectStatus,
    ProjectStockMovementType,
    ProjectWbsNodeType,
)
from vaybooks.bms.domain.shared.exceptions import ValidationError
from tests.test_project_quotations import FakeProjectQuotationRepository
from tests.test_projects_module import FakeProjectTemplateRepository


class FakeEnquiryRepo:
    def __init__(self):
        self._enquiries: Dict[str, ProjectEnquiry] = {}
        self._assessments: Dict[str, ProjectSiteAssessment] = {}

    def save(self, enquiry: ProjectEnquiry) -> ProjectEnquiry:
        self._enquiries[enquiry.id] = enquiry
        return enquiry

    def find_by_id(self, enquiry_id: str) -> Optional[ProjectEnquiry]:
        return self._enquiries.get(enquiry_id)

    def list_all(self, status=None) -> List[ProjectEnquiry]:
        items = list(self._enquiries.values())
        if status:
            items = [e for e in items if e.status == status]
        return items

    def find_by_project_id(self, project_id: str) -> Optional[ProjectEnquiry]:
        for enquiry in self._enquiries.values():
            if enquiry.project_id == project_id:
                return enquiry
        return None

    def save_assessment(self, assessment: ProjectSiteAssessment) -> ProjectSiteAssessment:
        self._assessments[assessment.id] = assessment
        return assessment

    def list_assessments(self, enquiry_id: str) -> List[ProjectSiteAssessment]:
        return [a for a in self._assessments.values() if a.enquiry_id == enquiry_id]


class FakeBoqRepo:
    def __init__(self):
        self._store: Dict[str, ProjectBoqItem] = {}

    def save(self, item: ProjectBoqItem) -> ProjectBoqItem:
        self._store[item.id] = item
        return item

    def find_by_id(self, item_id: str) -> Optional[ProjectBoqItem]:
        return self._store.get(item_id)

    def list_by_project(self, project_id: str) -> List[ProjectBoqItem]:
        return [i for i in self._store.values() if i.project_id == project_id]

    def delete(self, item_id: str) -> None:
        self._store.pop(item_id, None)


class FakeBudgetRepo:
    def __init__(self):
        self._lines: Dict[str, ProjectBudgetLine] = {}
        self._revisions: List[ProjectBudgetRevision] = []
        self._headers: Dict[str, ProjectBudgetHeader] = {}

    def save_line(self, line: ProjectBudgetLine) -> ProjectBudgetLine:
        self._lines[line.id] = line
        return line

    def find_line_by_id(self, line_id: str) -> Optional[ProjectBudgetLine]:
        return self._lines.get(line_id)

    def list_lines_by_project(self, project_id: str) -> List[ProjectBudgetLine]:
        return [ln for ln in self._lines.values() if ln.project_id == project_id]

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


class FakeDprRepo:
    def __init__(self):
        self._store: Dict[str, ProjectDpr] = {}

    def save(self, dpr: ProjectDpr) -> ProjectDpr:
        self._store[dpr.id] = dpr
        return dpr

    def find_by_id(self, dpr_id: str) -> Optional[ProjectDpr]:
        return self._store.get(dpr_id)

    def list_by_project(self, project_id: str) -> List[ProjectDpr]:
        return [d for d in self._store.values() if d.project_id == project_id]


class FakeProcurementRepo:
    def __init__(self):
        self._mrs: Dict[str, ProjectMaterialRequest] = {}
        self._rfqs: Dict[str, ProjectRfq] = {}
        self._moves: Dict[str, ProjectSiteStockMovement] = {}

    def save_material_request(self, mr: ProjectMaterialRequest) -> ProjectMaterialRequest:
        self._mrs[mr.id] = mr
        return mr

    def find_material_request_by_id(self, mr_id: str):
        return self._mrs.get(mr_id)

    def list_material_requests_by_project(self, project_id: str):
        return [m for m in self._mrs.values() if m.project_id == project_id]

    def save_rfq(self, rfq: ProjectRfq) -> ProjectRfq:
        self._rfqs[rfq.id] = rfq
        return rfq

    def find_rfq_by_id(self, rfq_id: str):
        return self._rfqs.get(rfq_id)

    def list_rfqs_by_project(self, project_id: str):
        return [r for r in self._rfqs.values() if r.project_id == project_id]

    def save_stock_movement(self, movement: ProjectSiteStockMovement):
        self._moves[movement.id] = movement
        return movement

    def list_stock_movements_by_project(self, project_id: str):
        return [m for m in self._moves.values() if m.project_id == project_id]


class FakeSubconRepo:
    def __init__(self):
        self._store: Dict[str, ProjectSubcontractOrder] = {}

    def save(self, order: ProjectSubcontractOrder) -> ProjectSubcontractOrder:
        self._store[order.id] = order
        return order

    def find_by_id(self, order_id: str):
        return self._store.get(order_id)

    def list_by_project(self, project_id: str):
        return [o for o in self._store.values() if o.project_id == project_id]


class FakePettyRepo:
    def __init__(self):
        self._store: Dict[str, ProjectPettyCashAdvance] = {}

    def save(self, advance: ProjectPettyCashAdvance) -> ProjectPettyCashAdvance:
        self._store[advance.id] = advance
        return advance

    def find_by_id(self, advance_id: str):
        return self._store.get(advance_id)

    def list_by_project(self, project_id: str):
        return [a for a in self._store.values() if a.project_id == project_id]


class FakeRecognitionRepo:
    def __init__(self):
        self._entries: Dict[str, ProjectRecognitionEntry] = {}
        self._recons: Dict[str, ProjectReconciliation] = {}

    def save_entry(self, entry: ProjectRecognitionEntry):
        self._entries[entry.id] = entry
        return entry

    def find_entry_by_id(self, entry_id: str):
        return self._entries.get(entry_id)

    def list_entries_by_project(self, project_id: str):
        return [e for e in self._entries.values() if e.project_id == project_id]

    def find_entry_by_idempotency_key(self, key: str):
        for entry in self._entries.values():
            if entry.idempotency_key == key:
                return entry
        return None

    def save_reconciliation(self, recon: ProjectReconciliation):
        self._recons[recon.id] = recon
        return recon

    def find_reconciliation_by_id(self, recon_id: str):
        return self._recons.get(recon_id)

    def list_reconciliations_by_project(self, project_id: str):
        return [r for r in self._recons.values() if r.project_id == project_id]


class FakeQualityRepo:
    def __init__(self):
        self._issues: Dict[str, ProjectQualityIssue] = {}
        self._handovers: Dict[str, ProjectHandover] = {}
        self._wbs: Dict[str, ProjectWbsNode] = {}
        self._snapshots: Dict[str, ProjectConfigSnapshot] = {}

    def save_quality_issue(self, issue: ProjectQualityIssue):
        self._issues[issue.id] = issue
        return issue

    def find_quality_issue_by_id(self, issue_id: str):
        return self._issues.get(issue_id)

    def list_quality_issues_by_project(self, project_id: str):
        return [i for i in self._issues.values() if i.project_id == project_id]

    def save_handover(self, handover: ProjectHandover):
        self._handovers[handover.project_id] = handover
        return handover

    def find_handover_by_project(self, project_id: str):
        return self._handovers.get(project_id)

    def save_wbs_node(self, node: ProjectWbsNode):
        self._wbs[node.id] = node
        return node

    def find_wbs_node_by_id(self, node_id: str):
        return self._wbs.get(node_id)

    def list_wbs_nodes_by_project(self, project_id: str):
        return [n for n in self._wbs.values() if n.project_id == project_id]

    def save_config_snapshot(self, snap: ProjectConfigSnapshot):
        self._snapshots[snap.id] = snap
        return snap

    def list_config_snapshots_by_project(self, project_id: str):
        return [s for s in self._snapshots.values() if s.project_id == project_id]


@pytest.fixture
def customer() -> Customer:
    return Customer(customer_name="Acme Builders", phone_number="9999999999", id="cust1")


@pytest.fixture
def stack(customer):
    counters = FakeCounterRepository()
    customers = FakeCustomerRepository()
    customers.save(customer)
    projects = FakeProjectRepository()
    templates = FakeProjectTemplateRepository()
    enquiry_repo = FakeEnquiryRepo()
    boq_repo = FakeBoqRepo()
    budget_repo = FakeBudgetRepo()
    quote_repo = FakeProjectQuotationRepository()
    dpr_repo = FakeDprRepo()
    proc_repo = FakeProcurementRepo()
    sub_repo = FakeSubconRepo()
    petty_repo = FakePettyRepo()
    recog_repo = FakeRecognitionRepo()
    quality_repo = FakeQualityRepo()

    project_svc = ProjectAppService(projects, templates, counters, customers)
    enquiry_svc = ProjectEnquiryAppService(
        enquiry_repo, projects, counters, customer_repo=customers
    )
    boq_svc = ProjectBoqAppService(boq_repo, projects)
    budget_svc = ProjectBudgetAppService(budget_repo, projects)
    quote_svc = ProjectQuotationAppService(
        quote_repo,
        projects,
        counters,
        boq_repo=boq_repo,
        boq_service=boq_svc,
        enquiry_service=enquiry_svc,
    )
    return {
        "counters": counters,
        "customers": customers,
        "projects": projects,
        "project_svc": project_svc,
        "enquiry": enquiry_svc,
        "boq": boq_svc,
        "budget": budget_svc,
        "quote": quote_svc,
        "dpr": ProjectDprAppService(dpr_repo, projects),
        "proc": ProjectProcurementAppService(proc_repo, projects, counters),
        "sub": ProjectSubcontractAppService(sub_repo, projects, counters),
        "petty": ProjectPettyCashAppService(petty_repo, projects, counters),
        "recog": ProjectRecognitionAppService(recog_repo, projects),
        "quality": ProjectQualityConfigAppService(quality_repo, projects),
        "budget_repo": budget_repo,
    }


def test_commercial_spine_enquiry_to_contract(stack, customer):
    enquiry = stack["enquiry"].create_enquiry(
        customer.id, requirement="Villa interior", source="Website"
    )
    assert enquiry.status == ProjectEnquiryStatus.DRAFT
    stack["enquiry"].add_assessment(
        enquiry.id, visit_date=date.today(), conditions="Good access", submit=True
    )
    project = stack["enquiry"].start_estimation(enquiry.id)
    assert project.enquiry_id == enquiry.id
    assert project.status == ProjectStatus.DRAFT

    item = stack["boq"].create_item(project.id, "A1", "Flooring", estimated_qty=10)
    analysed = stack["boq"].save_rate_analysis(
        item.id,
        material_cost=100,
        labour_cost=50,
        margin_pct=20,
    )
    assert analysed.selling_rate == pytest.approx(180.0)

    quotation = stack["quote"].create_quotation(
        project.id,
        lines=[
            {
                "description": "Flooring",
                "quantity": 10,
                "rate": analysed.selling_rate,
                "boq_item_id": item.id,
            }
        ],
    )
    stack["quote"].submit_for_approval(quotation.id)
    stack["quote"].approve_quotation(quotation.id)
    stack["quote"].send_quotation(quotation.id)
    accepted = stack["quote"].accept_quotation(
        quotation.id, confirmation_note="PO received"
    )
    assert accepted.status == ProjectQuotationStatus.ACCEPTED
    assert accepted.confirmation_note == "PO received"

    result = stack["quote"].convert_to_project(
        quotation.id, create_work_order=False
    )
    assert result["contract_value"] == pytest.approx(1800.0)
    won = stack["enquiry"].get_enquiry(enquiry.id)
    assert won.status == ProjectEnquiryStatus.WON
    refreshed = stack["projects"].find_by_id(project.id)
    assert refreshed.contract_approved is True
    assert refreshed.status == ProjectStatus.ACTIVE


def test_budget_approve_blocks_add_line(stack, customer):
    enquiry = stack["enquiry"].create_enquiry(customer.id)
    project = stack["enquiry"].start_estimation(enquiry.id)
    stack["budget"].add_line(project.id, ProjectCostCategory.MATERIAL, 1000)
    stack["budget"].submit_budget(project.id)
    header = stack["budget"].approve_budget(project.id)
    assert header.status == ProjectBudgetStatus.APPROVED
    with pytest.raises(ValidationError, match="frozen"):
        stack["budget"].add_line(project.id, ProjectCostCategory.LABOUR, 500)
    # revise still allowed
    line = stack["budget"].list_lines(project.id)[0]
    revised = stack["budget"].revise_line(line.id, 1200, reason="Scope")
    assert revised.revised_amount == 1200
    assert revised.original_amount == 1000


def test_activity_block_and_dpr_idempotent(stack, customer):
    enquiry = stack["enquiry"].create_enquiry(customer.id)
    project = stack["enquiry"].start_estimation(enquiry.id)
    project.activities.append(ProjectActivity(name="Cast columns", planned_hours=10))
    stack["projects"].save(project)
    activity_id = project.activities[0].id

    stack["project_svc"].block_activity(project.id, activity_id, reason="Rain")
    with pytest.raises(ValidationError, match="blocked"):
        stack["project_svc"].submit_activity_completion(project.id, activity_id)
    stack["project_svc"].resolve_activity(project.id, activity_id)
    stack["project_svc"].submit_activity_completion(project.id, activity_id)
    stack["project_svc"].approve_activity_completion(project.id, activity_id)

    dpr = stack["dpr"].create_dpr(
        project.id,
        date.today(),
        lines=[{"activity_id": activity_id, "hours": 2}],
    )
    stack["dpr"].submit(dpr.id)
    applied = stack["dpr"].approve_and_apply(dpr.id)
    again = stack["dpr"].approve_and_apply(dpr.id)
    assert applied.applied is True
    assert again.applied is True


def test_procurement_and_customer_owned_excluded(stack, customer):
    enquiry = stack["enquiry"].create_enquiry(customer.id)
    project = stack["enquiry"].start_estimation(enquiry.id)
    mr = stack["proc"].create_material_request(
        project.id, [{"description": "Cement", "quantity": 50}]
    )
    stack["proc"].submit_material_request(mr.id)
    stack["proc"].approve_material_request(mr.id)
    rfq = stack["proc"].create_rfq(project.id, "Cement", 50, material_request_id=mr.id)
    rfq = stack["proc"].add_rfq_quote(rfq.id, "v1", "Vendor A", 320)
    stack["proc"].award_rfq(rfq.id, rfq.quotes[0].id)

    stack["proc"].record_stock_movement(
        project.id,
        ProjectStockMovementType.CONSUME,
        "Cement",
        10,
        unit_cost=300,
        ownership=ProjectMaterialOwnership.CUSTOMER,
    )
    stack["proc"].record_stock_movement(
        project.id,
        ProjectStockMovementType.CONSUME,
        "Steel",
        5,
        unit_cost=100,
        ownership=ProjectMaterialOwnership.CONTRACTOR,
    )
    assert stack["proc"].contractor_consumed_cost(project.id) == 500.0


def test_subcontract_settle_and_petty_cash(stack, customer):
    enquiry = stack["enquiry"].create_enquiry(customer.id)
    project = stack["enquiry"].start_estimation(enquiry.id)
    order = stack["sub"].create_order(
        project.id,
        "v1",
        "Subco",
        [{"description": "Glazing", "quantity": 10, "rate": 1000}],
        retention_pct=5,
    )
    stack["sub"].activate(order.id)
    line_id = order.lines[0].id
    stack["sub"].record_measurement(order.id, line_id, 8)
    stack["sub"].certify_line(order.id, line_id, 8)
    settled = stack["sub"].settle(order.id)
    assert settled["gross"] == 8000
    assert settled["retention"] == 400
    assert settled["payable"] == 7600

    advance = stack["petty"].create_advance(project.id, "Site supervisor", 1000)
    stack["petty"].add_expense(
        advance.id, "Fuel", 600, date.today()
    )
    settled_adv = stack["petty"].settle(advance.id, returned_amount=400)
    assert settled_adv.status.value == "Settled"
    with pytest.raises(ValidationError, match="imbalance"):
        bad = stack["petty"].create_advance(project.id, "X", 500)
        stack["petty"].add_expense(bad.id, "Tea", 100, date.today())
        stack["petty"].settle(bad.id, returned_amount=50)


def test_recognition_quality_wbs_reopen(stack, customer):
    enquiry = stack["enquiry"].create_enquiry(customer.id)
    project = stack["enquiry"].start_estimation(enquiry.id)
    project.contract_value = 100_000
    stack["projects"].save(project)

    entry = stack["recog"].draft_recognition(
        project.id,
        date.today(),
        ProjectRecognitionMethod.PERCENT_COMPLETE,
        percent_complete=40,
        billed_to_date=30_000,
    )
    assert entry.current_recognised == pytest.approx(40_000)
    assert entry.unbilled_revenue == pytest.approx(10_000)

    issue = stack["quality"].create_quality_issue(project.id, "Paint snag")
    assert issue.title == "Paint snag"
    node = stack["quality"].add_wbs_node(
        project.id, "Main site", ProjectWbsNodeType.SITE
    )
    child = stack["quality"].add_wbs_node(
        project.id, "Tower A", ProjectWbsNodeType.ZONE, parent_id=node.id
    )
    assert child.parent_id == node.id
    snap = stack["quality"].publish_config_snapshot(
        project.id, archetype="Interior", scale="Small", modules=["RA", "Quality"]
    )
    assert snap.revision == 1

    project.status = ProjectStatus.FINANCIALLY_CLOSED
    stack["projects"].save(project)
    with pytest.raises(ValidationError, match="reason"):
        stack["project_svc"].reopen_project(project.id, "")
    reopened = stack["project_svc"].reopen_project(project.id, "Retention dispute")
    assert reopened.status == ProjectStatus.ACTIVE
    assert reopened.reopen_reason == "Retention dispute"
