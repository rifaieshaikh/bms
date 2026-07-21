"""Wave 6 — measurement double-bill, RA cumulative, variation status flow."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Dict, List, Optional

import pytest

from tests.conftest import FakeCounterRepository, FakeCustomerRepository
from tests.test_prd_mvp_accounting import FakeBoqRepository, FakeMeasurementRepository
from tests.test_project_billing import FakeRARepository, FakeVariationRepository, FakeWorkOrderRepository
from tests.test_projects_module import FakeProjectRepository, FakeProjectTemplateRepository
from vaybooks.bms.application.project_app_service import ProjectAppService
from vaybooks.bms.application.project_billing_app_service import ProjectBillingAppService
from vaybooks.bms.application.project_boq_app_service import ProjectBoqAppService
from vaybooks.bms.application.project_measurement_app_service import (
    ProjectMeasurementAppService,
)
from vaybooks.bms.domain.customers.entities import Customer
from vaybooks.bms.domain.shared.enums import ProjectVariationStatus
from vaybooks.bms.domain.shared.exceptions import ValidationError


@pytest.fixture
def wave6_stack():
    customer_repo = FakeCustomerRepository()
    customer = Customer(customer_name="Wave6 Co", phone_number="9000000006")
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
        name="Wave6 Tower",
        customer_id=customer.id,
        contract_value=1_000_000,
    )
    boq_repo = FakeBoqRepository()
    measurement_repo = FakeMeasurementRepository()
    ra_repo = FakeRARepository()
    variation_repo = FakeVariationRepository()
    boq = ProjectBoqAppService(boq_repo, project_repo)
    measurement = ProjectMeasurementAppService(
        measurement_repo, boq_repo, project_repo, ra_repo=ra_repo
    )
    billing = ProjectBillingAppService(
        project_repo,
        FakeWorkOrderRepository(),
        counters,
        ra_repo=ra_repo,
        variation_repo=variation_repo,
        boq_repo=boq_repo,
        measurement_repo=measurement_repo,
        measurement_service=measurement,
    )
    return {
        "project": project,
        "projects": projects,
        "boq": boq,
        "measurement": measurement,
        "billing": billing,
        "project_repo": project_repo,
    }


def test_no_double_bill_certified_measurement(wave6_stack):
    project = wave6_stack["project"]
    boq = wave6_stack["boq"]
    measurement = wave6_stack["measurement"]
    billing = wave6_stack["billing"]

    item = boq.create_item(
        project.id, "6.1", "Concrete", estimated_qty=100, selling_rate=500
    )
    boq.update_item(item.id, contracted_qty=100, contracted_rate=500)
    m = measurement.create(project.id, item.id, date.today(), 20)
    measurement.submit(m.id)
    measurement.verify(m.id)
    measurement.certify(m.id)

    eligible = measurement.eligible_for_ra(project.id)
    assert any(x.id == m.id for x in eligible)

    ra = billing.create_ra_from_measurements(project.id, [m.id])
    assert ra.lines[0].current_claimed_qty == 20

    eligible_after = measurement.eligible_for_ra(project.id)
    assert not any(x.id == m.id for x in eligible_after)

    with pytest.raises(ValidationError, match="already linked"):
        billing.create_ra_from_measurements(project.id, [m.id])


def test_ra_previous_current_cumulative(wave6_stack):
    project = wave6_stack["project"]
    boq = wave6_stack["boq"]
    measurement = wave6_stack["measurement"]
    billing = wave6_stack["billing"]

    item = boq.create_item(
        project.id, "6.2", "Steel", estimated_qty=200, selling_rate=100
    )
    boq.update_item(item.id, contracted_qty=200, contracted_rate=100)

    m1 = measurement.create(project.id, item.id, date.today(), 30)
    measurement.submit(m1.id)
    measurement.verify(m1.id)
    ra1 = billing.create_ra_from_measurements(project.id, [m1.id])
    line1 = ra1.lines[0]
    assert line1.previous_qty == 0
    assert line1.current_claimed_qty == 30
    assert line1.cumulative_claimed_qty == 30

    m2 = measurement.create(project.id, item.id, date.today(), 15)
    measurement.submit(m2.id)
    measurement.verify(m2.id)
    ra2 = billing.create_ra_from_measurements(project.id, [m2.id])
    line2 = ra2.lines[0]
    assert line2.previous_qty == 30
    assert line2.current_claimed_qty == 15
    assert line2.cumulative_claimed_qty == 45


def test_variation_status_flow(wave6_stack):
    project = wave6_stack["project"]
    billing = wave6_stack["billing"]

    variation = billing.create_variation(
        project.id,
        new_contract_value=1_100_000,
        reason="Extra floor",
        cost_impact=50_000,
    )
    assert variation.status == ProjectVariationStatus.DRAFT.value

    exposure = billing.unapproved_variation_exposure(project.id)
    assert exposure["cost"] == 50_000
    assert exposure["revenue"] == 100_000

    submitted = billing.submit_variation(variation.id)
    assert submitted.status == ProjectVariationStatus.SUBMITTED.value

    internal = billing.internally_approve_variation(variation.id, approved_by="pm")
    assert internal.status == ProjectVariationStatus.INTERNALLY_APPROVED.value

    customer = billing.customer_approve_variation(variation.id, approved_by="client")
    assert customer.status == ProjectVariationStatus.CUSTOMER_APPROVED.value
    assert customer.customer_approved is True

    refreshed = wave6_stack["project_repo"].find_by_id(project.id)
    assert refreshed.contract_value == 1_100_000

    exposure_after = billing.unapproved_variation_exposure(project.id)
    assert exposure_after["total"] == 0

    withdrawn = billing.create_variation(
        project.id, new_contract_value=1_150_000, reason="Withdraw me", cost_impact=1
    )
    billing.submit_variation(withdrawn.id)
    withdrawn = billing.withdraw_variation(withdrawn.id)
    assert withdrawn.status == ProjectVariationStatus.WITHDRAWN.value
