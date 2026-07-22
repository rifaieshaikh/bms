from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.projects.entities import (
    ProjectTemplate,
    ProjectTemplateActivity,
    ProjectTemplatePhase,
)
from vaybooks.bms.domain.shared.enums import PlaceOfSupplyMode, ProjectBillingMode


class MongoProjectTemplateRepository:
    def __init__(self, db: Database):
        self._collection = db.project_templates

    def _phase_to_doc(self, phase: ProjectTemplatePhase) -> dict:
        return {
            "id": phase.id,
            "name": phase.name,
            "sort_order": phase.sort_order,
        }

    def _phase_from_doc(self, doc: dict) -> ProjectTemplatePhase:
        return ProjectTemplatePhase(
            id=doc.get("id", ""),
            name=doc.get("name", ""),
            sort_order=int(doc.get("sort_order") or 0),
        )

    def _activity_to_doc(self, activity: ProjectTemplateActivity) -> dict:
        return {
            "id": activity.id,
            "name": activity.name,
            "sort_order": activity.sort_order,
            "parent_activity_id": activity.parent_activity_id,
            "default_hourly_rate": float(activity.default_hourly_rate or 0.0),
        }

    def _activity_from_doc(self, doc: dict) -> ProjectTemplateActivity:
        return ProjectTemplateActivity(
            id=doc.get("id", ""),
            name=doc.get("name", ""),
            sort_order=int(doc.get("sort_order") or 0),
            parent_activity_id=doc.get("parent_activity_id"),
            default_hourly_rate=float(doc.get("default_hourly_rate") or 0.0),
        )

    def _to_doc(self, template: ProjectTemplate) -> dict:
        return {
            "_id": template.id,
            "name": template.name,
            "description": template.description,
            "phases_enabled": template.phases_enabled,
            "max_activity_depth": template.max_activity_depth,
            "billing_mode": template.billing_mode.value,
            "retention_pct": float(template.retention_pct or 0.0),
            "place_of_supply_mode": template.place_of_supply_mode.value,
            "default_hourly_rate": float(template.default_hourly_rate or 0.0),
            "phases": [self._phase_to_doc(p) for p in template.phases],
            "activities": [self._activity_to_doc(a) for a in template.activities],
            "is_system": template.is_system,
            "created_at": template.created_at,
            "updated_at": template.updated_at,
        }

    def _from_doc(self, doc: dict) -> ProjectTemplate:
        return ProjectTemplate(
            id=doc["_id"],
            name=doc.get("name", ""),
            description=doc.get("description", ""),
            phases_enabled=doc.get("phases_enabled", True),
            max_activity_depth=int(doc.get("max_activity_depth") or 3),
            billing_mode=ProjectBillingMode(
                doc.get("billing_mode", ProjectBillingMode.FIXED.value)
            ),
            retention_pct=float(doc.get("retention_pct") or 0.0),
            place_of_supply_mode=PlaceOfSupplyMode(
                doc.get("place_of_supply_mode", PlaceOfSupplyMode.SITE_STATE.value)
            ),
            default_hourly_rate=float(doc.get("default_hourly_rate") or 0.0),
            phases=[self._phase_from_doc(p) for p in doc.get("phases", [])],
            activities=[
                self._activity_from_doc(a) for a in doc.get("activities", [])
            ],
            is_system=bool(doc.get("is_system", False)),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, template: ProjectTemplate) -> ProjectTemplate:
        self._collection.replace_one(
            {"_id": template.id}, self._to_doc(template), upsert=True
        )
        return template

    def find_by_id(self, template_id: str) -> Optional[ProjectTemplate]:
        doc = self._collection.find_one({"_id": template_id})
        return self._from_doc(doc) if doc else None

    def list_all(self) -> List[ProjectTemplate]:
        return [self._from_doc(d) for d in self._collection.find()]

    def delete(self, template_id: str) -> None:
        self._collection.delete_one({"_id": template_id})
