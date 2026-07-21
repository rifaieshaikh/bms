"""Seed system project templates."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from pymongo.database import Database

from vaybooks.bms.domain.projects.entities import (
    ProjectTemplate,
    ProjectTemplateActivity,
    ProjectTemplatePhase,
)
from vaybooks.bms.domain.shared.enums import PlaceOfSupplyMode, ProjectBillingMode
from vaybooks.bms.infrastructure.repositories.mongo_project_template_repository import (
    MongoProjectTemplateRepository,
)


def _apartment_interior_template() -> ProjectTemplate:
    demolition = ProjectTemplateActivity(name="Demolition", sort_order=1)
    electrical = ProjectTemplateActivity(name="Electrical", sort_order=2)
    plumbing = ProjectTemplateActivity(name="Plumbing", sort_order=3)
    carpentry = ProjectTemplateActivity(
        name="Carpentry", sort_order=4, default_hourly_rate=350.0
    )
    painting = ProjectTemplateActivity(
        name="Painting", sort_order=5, default_hourly_rate=200.0
    )
    finishing = ProjectTemplateActivity(name="Finishing", sort_order=6)
    return ProjectTemplate(
        name="Apartment Interior",
        description="Full apartment interior renovation (₹8L golden path)",
        phases_enabled=True,
        max_activity_depth=3,
        billing_mode=ProjectBillingMode.FIXED,
        retention_pct=5.0,
        place_of_supply_mode=PlaceOfSupplyMode.SITE_STATE,
        default_hourly_rate=250.0,
        is_system=True,
        phases=[
            ProjectTemplatePhase(name="Preparation", sort_order=1),
            ProjectTemplatePhase(name="Execution", sort_order=2),
            ProjectTemplatePhase(name="Handover", sort_order=3),
        ],
        activities=[demolition, electrical, plumbing, carpentry, painting, finishing],
    )


def _small_repair_template() -> ProjectTemplate:
    return ProjectTemplate(
        name="Small Repair",
        description="Quick repair / patch job",
        phases_enabled=False,
        max_activity_depth=2,
        billing_mode=ProjectBillingMode.TIME_AND_MATERIAL,
        default_hourly_rate=300.0,
        is_system=True,
        activities=[
            ProjectTemplateActivity(name="Assessment", sort_order=1),
            ProjectTemplateActivity(name="Repair Work", sort_order=2),
        ],
    )


def _blank_template() -> ProjectTemplate:
    return ProjectTemplate(
        name="Blank",
        description="Empty project — add your own phases and activities",
        phases_enabled=False,
        max_activity_depth=3,
        billing_mode=ProjectBillingMode.FIXED,
        is_system=True,
    )


SYSTEM_TEMPLATES = [
    _apartment_interior_template(),
    _small_repair_template(),
    _blank_template(),
]


def ensure_project_templates(db: Database) -> None:
    repo = MongoProjectTemplateRepository(db)
    existing = {t.name: t for t in repo.list_all()}
    now = datetime.utcnow()
    for template in SYSTEM_TEMPLATES:
        if template.name in existing:
            continue
        template.id = uuid4().hex
        template.created_at = now
        template.updated_at = now
        repo.save(template)
