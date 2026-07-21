"""Wave 5 procurement tests — RFQ→PO, customer ownership, stock reconciliation."""

from __future__ import annotations

from datetime import date
from typing import List
from uuid import uuid4

import pytest

from vaybooks.bms.application.project_app_service import ProjectAppService
from vaybooks.bms.application.project_procurement_app_service import (
    ProjectProcurementAppService,
)
from vaybooks.bms.domain.customers.entities import Customer
from vaybooks.bms.domain.purchases.entities import PurchaseOrder, PurchaseOrderLine
from vaybooks.bms.domain.shared.enums import (
    ProjectMaterialOwnership,
    ProjectStockMovementType,
    PurchaseOrderStatus,
)
from vaybooks.bms.domain.shared.exceptions import ValidationError
from tests.conftest import FakeCounterRepository, FakeCustomerRepository
from tests.test_project_full_accounting_usecases import FakeProcurementRepo
from tests.test_projects_module import FakeProjectRepository, FakeProjectTemplateRepository


class FakePurchaseService:
    def __init__(self):
        self.created: List[PurchaseOrder] = []

    def create_purchase_order(
        self,
        vendor_id: str,
        order_date: date,
        lines: list,
        expected_date=None,
        notes: str = "",
        status=PurchaseOrderStatus.DRAFT,
        project_id: str = "",
    ) -> PurchaseOrder:
        po = PurchaseOrder(
            po_number=f"PO-{len(self.created) + 1}",
            vendor_id=vendor_id,
            order_date=order_date,
            lines=[
                PurchaseOrderLine(
                    product_id=str(row.get("product_id") or ""),
                    product_name=(row.get("product_name") or "").strip(),
                    qty_ordered=float(row.get("qty_ordered") or row.get("qty") or 0),
                    rate=float(row.get("rate") or 0),
                )
                for row in lines
            ],
            notes=notes,
            status=PurchaseOrderStatus.SENT,
            project_id=project_id,
            id=uuid4().hex,
        )
        self.created.append(po)
        return po


@pytest.fixture
def customer() -> Customer:
    return Customer(customer_name="Wave5 Co", phone_number="9222222222", id="cust_w5")


@pytest.fixture
def proc_stack(customer):
    customers = FakeCustomerRepository()
    customers.save(customer)
    projects = FakeProjectRepository()
    templates = FakeProjectTemplateRepository()
    counters = FakeCounterRepository()
    project_svc = ProjectAppService(projects, templates, counters, customers)
    project = project_svc.create_project(
        name="Tower B",
        customer_id=customer.id,
        contract_value=500000,
    )
    purchase = FakePurchaseService()
    proc = ProjectProcurementAppService(
        FakeProcurementRepo(),
        projects,
        counters,
        purchase_service=purchase,
    )
    return {
        "project": project,
        "proc": proc,
        "purchase": purchase,
        "projects": projects,
    }


def test_award_rfq_creates_po_id(proc_stack):
    project = proc_stack["project"]
    proc = proc_stack["proc"]
    purchase = proc_stack["purchase"]

    rfq = proc.create_rfq(project.id, "Cement bags", 100, unit="Bags")
    rfq = proc.add_rfq_quote(rfq.id, "v1", "Vendor A", 350.0)
    awarded = proc.award_rfq(rfq.id, rfq.quotes[0].id)

    assert awarded.po_id
    assert len(purchase.created) == 1
    po = purchase.created[0]
    assert po.id == awarded.po_id
    assert po.project_id == project.id
    assert po.vendor_id == "v1"
    assert po.lines[0].product_name == "Cement bags"
    assert po.lines[0].qty_ordered == 100
    assert po.lines[0].rate == 350.0


def test_award_rfq_respects_explicit_po_id(proc_stack):
    project = proc_stack["project"]
    proc = proc_stack["proc"]
    purchase = proc_stack["purchase"]

    rfq = proc.create_rfq(project.id, "Steel", 10)
    rfq = proc.add_rfq_quote(rfq.id, "v2", "Vendor B", 100.0)
    awarded = proc.award_rfq(rfq.id, rfq.quotes[0].id, po_id="existing-po")
    assert awarded.po_id == "existing-po"
    assert purchase.created == []


def test_customer_owned_excluded_from_contractor_cost(proc_stack):
    project = proc_stack["project"]
    proc = proc_stack["proc"]

    proc.record_stock_movement(
        project.id,
        ProjectStockMovementType.CONSUME,
        "Cement",
        10,
        unit_cost=300,
        ownership=ProjectMaterialOwnership.CUSTOMER,
        invoice_party="Customer",
        principal_agent="Agent",
    )
    proc.record_stock_movement(
        project.id,
        ProjectStockMovementType.CONSUME,
        "Steel",
        5,
        unit_cost=100,
        ownership=ProjectMaterialOwnership.CONTRACTOR,
        invoice_party="Contractor",
        principal_agent="Principal",
    )
    assert proc.contractor_consumed_cost(project.id) == 500.0


def test_stock_reconciliation_by_ownership(proc_stack):
    project = proc_stack["project"]
    proc = proc_stack["proc"]

    proc.record_stock_movement(
        project.id,
        ProjectStockMovementType.RECEIPT,
        "Cement",
        50,
        ownership=ProjectMaterialOwnership.CONTRACTOR,
    )
    proc.record_stock_movement(
        project.id,
        ProjectStockMovementType.RECEIPT,
        "Tiles",
        20,
        ownership=ProjectMaterialOwnership.CUSTOMER,
        invoice_party="Customer",
    )
    proc.record_stock_movement(
        project.id,
        ProjectStockMovementType.CONSUME,
        "Cement",
        10,
        ownership=ProjectMaterialOwnership.CONTRACTOR,
    )

    recon = proc.stock_reconciliation(project.id)
    assert recon["by_ownership"]["Contractor"] == pytest.approx(40.0)
    assert recon["by_ownership"]["Customer"] == pytest.approx(20.0)
    assert len(recon["lines"]) >= 2


def test_invoice_party_validation(proc_stack):
    project = proc_stack["project"]
    proc = proc_stack["proc"]
    with pytest.raises(ValidationError, match="invoice_party"):
        proc.record_stock_movement(
            project.id,
            ProjectStockMovementType.RECEIPT,
            "Sand",
            1,
            invoice_party="SomeoneElse",
        )
