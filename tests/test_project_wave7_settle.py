"""Wave 7 — receipt allocation, handover→DLP, retention closure blockers."""

from __future__ import annotations

from datetime import date, datetime
from typing import Dict, List, Optional
from uuid import uuid4

import pytest

from tests.conftest import FakeCounterRepository, FakeCustomerRepository
from tests.test_project_billing import (
    FakeRARepository,
    FakeRetentionRepository,
    FakeWorkOrderRepository,
)
from tests.test_projects_module import FakeProjectRepository, FakeProjectTemplateRepository
from vaybooks.bms.application.projects.core.service import ProjectAppService
from vaybooks.bms.application.projects.billing.service import ProjectBillingAppService
from vaybooks.bms.application.projects.quality.service import (
    ProjectQualityConfigAppService,
)
from vaybooks.bms.domain.finance.accounting.entities import Voucher, VoucherLine
from vaybooks.bms.domain.parties.customers.entities import Customer
from vaybooks.bms.domain.projects.entities import ProjectRetentionEntry
from vaybooks.bms.domain.projects.quality_config import (
    ProjectHandover,
    ProjectHandoverItem,
)
from vaybooks.bms.domain.shared.enums import ProjectStatus, VoucherType
from vaybooks.bms.domain.shared.exceptions import ValidationError


class FakeAccount:
    def __init__(self, account_id: str, name: str = "Acct"):
        self.id = account_id
        self.account_name = name


class FakeVoucherRepo:
    def __init__(self):
        self._store: Dict[str, Voucher] = {}

    def save(self, voucher: Voucher) -> Voucher:
        self._store[voucher.id] = voucher
        return voucher

    def find_by_id(self, voucher_id: str) -> Optional[Voucher]:
        return self._store.get(voucher_id)

    def list_by_project(self, project_id: str) -> List[Voucher]:
        return [
            v for v in self._store.values() if v.reference_project_id == project_id
        ]


class FakeAccountingForReceipt:
    def __init__(self, voucher_repo: FakeVoucherRepo):
        self._vouchers = voucher_repo
        self._customer = FakeAccount("cust-acct", "Customer AR")

    def get_customer_account(self, customer_id: str):
        return self._customer

    def get_discount_account(self):
        return None

    def list_vouchers_by_project(self, project_id: str):
        return self._vouchers.list_by_project(project_id)

    def create_receipt(
        self,
        receiving_account_id: str,
        customer_account_id: str,
        amount: float,
        description: str,
        voucher_date=None,
    ) -> Voucher:
        voucher = Voucher(
            voucher_number=f"RCPT-{len(self._vouchers._store) + 1}",
            voucher_type=VoucherType.RECEIPT,
            voucher_date=datetime.utcnow(),
            description=description,
            lines=[
                VoucherLine(
                    account_id=receiving_account_id,
                    account_name="Cash",
                    debit_amount=float(amount),
                ),
                VoucherLine(
                    account_id=customer_account_id,
                    account_name="AR",
                    credit_amount=float(amount),
                ),
            ],
            id=uuid4().hex,
        )
        return self._vouchers.save(voucher)


class FakeQualityRepo:
    def __init__(self):
        self._handovers: Dict[str, ProjectHandover] = {}

    def find_handover_by_project(self, project_id: str):
        return self._handovers.get(project_id)

    def save_handover(self, handover: ProjectHandover) -> ProjectHandover:
        self._handovers[handover.project_id] = handover
        return handover

    def list_quality_issues_by_project(self, project_id: str):
        return []

    def save_quality_issue(self, issue):
        return issue

    def find_quality_issue_by_id(self, issue_id: str):
        return None

    def list_wbs_nodes_by_project(self, project_id: str):
        return []

    def save_wbs_node(self, node):
        return node


@pytest.fixture
def wave7_stack():
    customer_repo = FakeCustomerRepository()
    customer = Customer(customer_name="Wave7 Co", phone_number="9000000007")
    customer_repo.save(customer)
    project_repo = FakeProjectRepository()
    counters = FakeCounterRepository()
    projects = ProjectAppService(
        project_repo,
        FakeProjectTemplateRepository(),
        counters,
        customer_repo,
    )
    project = projects.create_project(
        name="Wave7 Site",
        customer_id=customer.id,
        contract_value=500_000,
    )
    project = projects.update_project_settings(
        project.id, dlp_months=12, status=ProjectStatus.ACTIVE
    )

    voucher_repo = FakeVoucherRepo()
    accounting = FakeAccountingForReceipt(voucher_repo)
    retention_repo = FakeRetentionRepository()
    billing = ProjectBillingAppService(
        project_repo,
        FakeWorkOrderRepository(),
        counters,
        accounting_service=accounting,
        voucher_repo=voucher_repo,
        retention_repo=retention_repo,
        ra_repo=FakeRARepository(),
    )
    quality = ProjectQualityConfigAppService(
        FakeQualityRepo(), project_repo, project_service=projects
    )
    return {
        "project": project,
        "projects": projects,
        "billing": billing,
        "quality": quality,
        "voucher_repo": voucher_repo,
        "retention_repo": retention_repo,
        "project_repo": project_repo,
    }


def test_receipt_short_and_unallocated(wave7_stack):
    project = wave7_stack["project"]
    billing = wave7_stack["billing"]
    voucher_repo = wave7_stack["voucher_repo"]

    invoice = Voucher(
        voucher_number="INV-1",
        voucher_type=VoucherType.SALES_INVOICE,
        voucher_date=datetime.utcnow(),
        description="Tax invoice",
        lines=[
            VoucherLine(account_id="rev", account_name="Sales", credit_amount=1000),
            VoucherLine(account_id="ar", account_name="AR", debit_amount=1000),
        ],
        id=uuid4().hex,
        reference_project_id=project.id,
    )
    voucher_repo.save(invoice)

    result = billing.create_receipt(
        project.id,
        receiving_account_id="cash-1",
        customer_account_id="cust-acct",
        amount=700,
        description="Partial collection",
        allocations=[{"invoice_id": invoice.id, "amount": 600}],
    )
    assert isinstance(result, dict)
    assert result["unallocated"] == 100
    assert result["short_payment"] == 400
    assert result["voucher"].voucher_type == VoucherType.RECEIPT


def test_handover_complete_enters_dlp(wave7_stack):
    project = wave7_stack["project"]
    quality = wave7_stack["quality"]
    project_repo = wave7_stack["project_repo"]

    assert project.dlp_months == 12
    handover = quality.set_handover_checklist(
        project.id,
        [{"label": "As-built drawings"}, {"label": "Keys handed over"}],
    )
    assert not handover.is_complete

    item1 = handover.checklist[0]
    quality.complete_handover_item(project.id, item1.id, completed=True)
    mid = project_repo.find_by_id(project.id)
    assert mid.status == ProjectStatus.ACTIVE

    item2 = quality.get_or_create_handover(project.id).checklist[1]
    done = quality.complete_handover_item(project.id, item2.id, completed=True)
    assert done.is_complete
    refreshed = project_repo.find_by_id(project.id)
    assert refreshed.status == ProjectStatus.DLP


def test_closure_blocker_open_retention(wave7_stack):
    project = wave7_stack["project"]
    billing = wave7_stack["billing"]
    retention_repo = wave7_stack["retention_repo"]

    retention_repo.save(
        ProjectRetentionEntry(
            project_id=project.id,
            invoice_voucher_id="inv-x",
            invoice_number="INV-X",
            withheld_amount=25_000,
            released_amount=0,
        )
    )
    blockers = billing.get_closure_blockers(project.id)
    assert any(b.get("type") == "open_retention" for b in blockers)
    retention = next(b for b in blockers if b["type"] == "open_retention")
    assert retention["severity"] == "block"
    assert "retention" in retention["message"].lower()
