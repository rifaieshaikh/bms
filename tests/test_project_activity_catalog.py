"""Tests for Project Activities catalog and phase-based quotation."""

from __future__ import annotations

from copy import deepcopy
from typing import Dict, List, Optional

import pytest

from tests.conftest import FakeCounterRepository, FakeCustomerRepository
from tests.test_projects_module import FakeProjectRepository, FakeProjectTemplateRepository
from vaybooks.bms.application.project_activity_config_app_service import (
    ProjectActivityConfigAppService,
)
from vaybooks.bms.application.project_app_service import ProjectAppService
from vaybooks.bms.application.project_boq_app_service import ProjectBoqAppService
from vaybooks.bms.application.project_quotation_app_service import (
    ProjectQuotationAppService,
)
from vaybooks.bms.domain.customers.entities import Customer
from vaybooks.bms.domain.projects.activity_catalog import (
    COMPLETED_STATUS,
    CREATED_STATUS,
    ProjectActivityConfig,
    normalize_statuses,
)
from vaybooks.bms.domain.projects.boq import ProjectBoqItem
from vaybooks.bms.domain.projects.entities import (
    ProjectPhase,
    ProjectTemplate,
)
from vaybooks.bms.domain.shared.enums import ActivityCategory, ProjectBoqItemType
from vaybooks.bms.domain.shared.exceptions import ValidationError
from tests.test_project_quotations import FakeProjectQuotationRepository


@pytest.fixture
def blank_template() -> ProjectTemplate:
    return ProjectTemplate(
        name="Blank",
        description="Empty template",
        phases_enabled=True,
        is_system=True,
    )


class FakeActivityConfigRepository:
    def __init__(self, configs: Optional[List[ProjectActivityConfig]] = None):
        self._store: Dict[str, ProjectActivityConfig] = {
            c.id: c for c in (configs or [])
        }

    def save(self, config: ProjectActivityConfig) -> ProjectActivityConfig:
        self._store[config.id] = config
        return config

    def find_by_id(self, config_id: str) -> Optional[ProjectActivityConfig]:
        return self._store.get(config_id)

    def find_by_name(self, name: str) -> Optional[ProjectActivityConfig]:
        for config in self._store.values():
            if config.activity_name.lower() == name.lower():
                return config
        return None

    def list_all(self, active_only: bool = True) -> List[ProjectActivityConfig]:
        items = list(self._store.values())
        if active_only:
            items = [c for c in items if c.is_active]
        return items

    def delete(self, config_id: str) -> None:
        config = self._store.get(config_id)
        if config:
            config.is_active = False


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
            deepcopy(i) for i in self._store.values() if i.project_id == project_id
        ]

    def delete(self, item_id: str) -> None:
        self._store.pop(item_id, None)


@pytest.fixture
def catalog_svc():
    return ProjectActivityConfigAppService(FakeActivityConfigRepository())


@pytest.fixture
def project_stack(blank_template):
    customer_repo = FakeCustomerRepository()
    customer = Customer(customer_name="Acme", phone_number="9999999999")
    customer_repo.save(customer)
    config_repo = FakeActivityConfigRepository()
    electrical = ProjectActivityConfig(
        activity_name="Electrical",
        activity_type=None,
        default_hourly_rate=300.0,
        default_amount=50000.0,
    )
    electrical.apply_category(ActivityCategory.IN_HOUSE_SERVICE)
    painting = ProjectActivityConfig(
        activity_name="Painting",
        activity_type=None,
        default_hourly_rate=200.0,
        default_amount=25000.0,
    )
    painting.apply_category(ActivityCategory.IN_HOUSE_SERVICE)
    painting.set_statuses(["Site Prep", "Finish Coat"])
    config_repo.save(electrical)
    config_repo.save(painting)

    project_repo = FakeProjectRepository()
    projects = ProjectAppService(
        project_repo,
        FakeProjectTemplateRepository([blank_template]),
        FakeCounterRepository(),
        customer_repo,
        activity_config_repo=config_repo,
    )
    return {
        "customer": customer,
        "projects": projects,
        "config_repo": config_repo,
        "electrical": electrical,
        "painting": painting,
        "project_repo": project_repo,
    }


def test_normalize_statuses_bookends():
    assert normalize_statuses(["Site Prep", "Created", "Completed"]) == [
        CREATED_STATUS,
        "Site Prep",
        COMPLETED_STATUS,
    ]


def test_catalog_create_requires_hourly_for_in_house_service(catalog_svc):
    with pytest.raises(ValidationError, match="hourly"):
        catalog_svc.create_activity(
            "Wiring",
            ActivityCategory.IN_HOUSE_SERVICE.value,
            default_hourly_rate=0,
            default_amount=1000,
        )
    created = catalog_svc.create_activity(
        "Wiring",
        ActivityCategory.IN_HOUSE_SERVICE.value,
        default_hourly_rate=250,
        default_amount=1000,
        custom_statuses=["Rough-in"],
    )
    assert created.statuses[0] == CREATED_STATUS
    assert created.statuses[-1] == COMPLETED_STATUS
    assert "Rough-in" in created.statuses
    assert created.default_amount == 1000


def test_add_activities_from_catalog_snapshots(project_stack):
    svc = project_stack["projects"]
    customer = project_stack["customer"]
    electrical = project_stack["electrical"]
    painting = project_stack["painting"]
    project = svc.create_project("Office Fitout", customer.id, 100000)
    phase = ProjectPhase(name="Execution", sort_order=1)
    project.phases = [phase]
    project_stack["project_repo"].save(project)

    updated = svc.add_activities_from_catalog(
        project.id, [electrical.id, painting.id], phase_id=phase.id
    )
    assert len(updated.activities) == 2
    by_name = {a.name: a for a in updated.activities}
    assert by_name["Electrical"].activity_config_id == electrical.id
    assert by_name["Electrical"].amount == 50000
    assert by_name["Electrical"].phase_id == phase.id
    assert by_name["Electrical"].current_status == CREATED_STATUS
    assert by_name["Painting"].activity_category == ActivityCategory.IN_HOUSE_SERVICE.value

    with pytest.raises(ValidationError, match="No new activities"):
        svc.add_activities_from_catalog(project.id, [electrical.id])


def test_set_activity_workflow_status_uses_catalog(project_stack):
    svc = project_stack["projects"]
    customer = project_stack["customer"]
    painting = project_stack["painting"]
    project = svc.create_project("Paint Job", customer.id, 50000)
    project = svc.add_activities_from_catalog(project.id, [painting.id])
    activity = project.activities[0]

    project = svc.set_activity_workflow_status(
        project.id, activity.id, "Site Prep"
    )
    act = project.activities[0]
    assert act.current_status == "Site Prep"
    assert act.status.value == "In Progress"

    with pytest.raises(ValidationError, match="Status must be"):
        svc.set_activity_workflow_status(project.id, activity.id, "Unknown")


def test_quotation_from_phases_hides_material_rates(project_stack):
    svc = project_stack["projects"]
    customer = project_stack["customer"]
    electrical = project_stack["electrical"]
    project = svc.create_project("Quote Project", customer.id, 200000)
    phase = ProjectPhase(name="Works", sort_order=1)
    project.phases = [phase]
    project_stack["project_repo"].save(project)
    project = svc.add_activities_from_catalog(
        project.id, [electrical.id], phase_id=phase.id
    )

    boq_repo = FakeBoqRepository()
    boq_svc = ProjectBoqAppService(boq_repo, project_stack["project_repo"])
    boq_svc.create_item(
        project.id,
        "M1",
        "Cable",
        item_type=ProjectBoqItemType.ITEM,
        estimated_qty=100,
        selling_rate=50,
        phase_id=phase.id,
    )

    quote_svc = ProjectQuotationAppService(
        FakeProjectQuotationRepository(),
        project_stack["project_repo"],
        FakeCounterRepository(),
        boq_repo=boq_repo,
        boq_service=boq_svc,
    )
    lines = quote_svc.default_lines_from_phases(project.id)
    activity_lines = [ln for ln in lines if ln.get("line_kind") == "activity"]
    material_lines = [ln for ln in lines if ln.get("line_kind") == "material"]
    assert len(activity_lines) == 1
    assert activity_lines[0]["rate"] == 50000
    assert len(material_lines) == 1
    assert material_lines[0]["rate"] == 0.0
    assert material_lines[0]["hide_rate"] is True
    assert material_lines[0]["quantity"] == 100
