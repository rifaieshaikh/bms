from __future__ import annotations

import re
from datetime import datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.projects.entities import (
    Project,
    ProjectActivity,
    ProjectParty,
    ProjectPhase,
)
from vaybooks.bms.domain.shared.enums import (
    PlaceOfSupplyMode,
    ProjectActivityStatus,
    ProjectBillingMode,
    ProjectPartyRole,
    ProjectStatus,
)
from vaybooks.bms.infrastructure.db.bson_utils import from_bson_date, to_bson_value


class MongoProjectRepository:
    def __init__(self, db: Database):
        self._collection = db.projects

    def _party_to_doc(self, party: ProjectParty) -> dict:
        return {
            "id": party.id,
            "party_id": party.party_id,
            "party_name": party.party_name,
            "role": party.role.value,
            "is_primary": party.is_primary,
        }

    def _party_from_doc(self, doc: dict) -> ProjectParty:
        return ProjectParty(
            id=doc.get("id", ""),
            party_id=doc.get("party_id", ""),
            party_name=doc.get("party_name", ""),
            role=ProjectPartyRole(
                doc.get("role", ProjectPartyRole.CUSTOMER.value)
            ),
            is_primary=bool(doc.get("is_primary", False)),
        )

    def _phase_to_doc(self, phase: ProjectPhase) -> dict:
        return {
            "id": phase.id,
            "name": phase.name,
            "sort_order": phase.sort_order,
        }

    def _phase_from_doc(self, doc: dict) -> ProjectPhase:
        return ProjectPhase(
            id=doc.get("id", ""),
            name=doc.get("name", ""),
            sort_order=int(doc.get("sort_order") or 0),
        )

    def _activity_to_doc(self, activity: ProjectActivity) -> dict:
        return {
            "id": activity.id,
            "name": activity.name,
            "sort_order": activity.sort_order,
            "parent_activity_id": activity.parent_activity_id,
            "phase_id": activity.phase_id,
            "status": activity.status.value,
            "activity_config_id": activity.activity_config_id,
            "activity_category": activity.activity_category,
            "current_status": activity.current_status,
            "amount": float(activity.amount or 0.0),
            "default_hourly_rate": float(activity.default_hourly_rate or 0.0),
            "planned_hours": float(activity.planned_hours or 0.0),
            "planned_cost": float(activity.planned_cost or 0.0),
            "planned_revenue_amount": float(activity.planned_revenue_amount or 0.0),
            "planned_revenue_pct": float(activity.planned_revenue_pct or 0.0),
            "planned_start": to_bson_value(activity.planned_start),
            "planned_end": to_bson_value(activity.planned_end),
            "percent_complete": float(activity.percent_complete or 0.0),
            "weightage": float(activity.weightage or 0.0),
            "boq_item_ids": list(activity.boq_item_ids or []),
            "predecessor_ids": list(activity.predecessor_ids or []),
            "blocked": bool(activity.blocked),
            "block_reason": activity.block_reason,
            "completion_submitted": bool(activity.completion_submitted),
            "progress_method": activity.progress_method,
            "wbs_node_id": activity.wbs_node_id,
        }

    def _activity_from_doc(self, doc: dict) -> ProjectActivity:
        return ProjectActivity(
            id=doc.get("id", ""),
            name=doc.get("name", ""),
            sort_order=int(doc.get("sort_order") or 0),
            parent_activity_id=doc.get("parent_activity_id"),
            phase_id=doc.get("phase_id"),
            status=ProjectActivityStatus(
                doc.get("status", ProjectActivityStatus.PENDING.value)
            ),
            activity_config_id=doc.get("activity_config_id", ""),
            activity_category=doc.get("activity_category", ""),
            current_status=doc.get("current_status") or "Created",
            amount=float(doc.get("amount") or doc.get("planned_revenue_amount") or 0.0),
            default_hourly_rate=float(doc.get("default_hourly_rate") or 0.0),
            planned_hours=float(doc.get("planned_hours") or 0.0),
            planned_cost=float(doc.get("planned_cost") or 0.0),
            planned_revenue_amount=float(doc.get("planned_revenue_amount") or 0.0),
            planned_revenue_pct=float(doc.get("planned_revenue_pct") or 0.0),
            planned_start=from_bson_date(doc.get("planned_start")),
            planned_end=from_bson_date(doc.get("planned_end")),
            percent_complete=float(doc.get("percent_complete") or 0.0),
            weightage=float(doc.get("weightage") or 0.0),
            boq_item_ids=list(doc.get("boq_item_ids") or []),
            predecessor_ids=list(doc.get("predecessor_ids") or []),
            blocked=bool(doc.get("blocked", False)),
            block_reason=doc.get("block_reason", ""),
            completion_submitted=bool(doc.get("completion_submitted", False)),
            progress_method=doc.get("progress_method", "percent"),
            wbs_node_id=doc.get("wbs_node_id", ""),
        )

    @staticmethod
    def _parse_project_status(raw: str) -> ProjectStatus:
        legacy = {
            "Completed": ProjectStatus.PHYSICALLY_COMPLETED,
            "Closed": ProjectStatus.FINANCIALLY_CLOSED,
        }
        if raw in legacy:
            return legacy[raw]
        return ProjectStatus(raw)

    def _to_doc(self, project: Project) -> dict:
        return {
            "_id": project.id,
            "project_number": project.project_number,
            "name": project.name,
            "customer_id": project.customer_id,
            "customer_name": project.customer_name,
            "contract_value": float(project.contract_value or 0.0),
            "original_contract_value": float(project.original_contract_value or 0.0),
            "revised_contract_value": float(project.revised_contract_value or 0.0),
            "contract_approved": project.contract_approved,
            "advance_terms": project.advance_terms,
            "dlp_months": int(project.dlp_months or 0),
            "project_manager": project.project_manager,
            "consultant_name": project.consultant_name,
            "owner_name": project.owner_name,
            "hard_budget_check": project.hard_budget_check,
            "physically_completed_at": project.physically_completed_at,
            "status": project.status.value,
            "template_id": project.template_id,
            "site_address": project.site_address,
            "site_state_code": project.site_state_code,
            "notes": project.notes,
            "start_date": to_bson_value(project.start_date),
            "expected_end_date": to_bson_value(project.expected_end_date),
            "phases_enabled": project.phases_enabled,
            "max_activity_depth": project.max_activity_depth,
            "billing_mode": project.billing_mode.value,
            "retention_pct": float(project.retention_pct or 0.0),
            "place_of_supply_mode": project.place_of_supply_mode.value,
            "default_hourly_rate": float(project.default_hourly_rate or 0.0),
            "parties": [self._party_to_doc(p) for p in project.parties],
            "phases": [self._phase_to_doc(p) for p in project.phases],
            "activities": [self._activity_to_doc(a) for a in project.activities],
            "closed_at": project.closed_at,
            "closed_by": project.closed_by,
            "period_locked": project.period_locked,
            "advance_gst_policy": project.advance_gst_policy,
            "overhead_allocation_pct": float(project.overhead_allocation_pct or 0.0),
            "currency_code": (project.currency_code or "INR").strip() or "INR",
            "final_snapshot": project.final_snapshot,
            "enquiry_id": project.enquiry_id,
            "archetype": project.archetype,
            "scale_profile": project.scale_profile,
            "reopen_reason": project.reopen_reason,
            "reopened_at": project.reopened_at,
            "created_at": project.created_at,
            "updated_at": project.updated_at,
        }

    def _from_doc(self, doc: dict) -> Project:
        return Project(
            id=doc["_id"],
            project_number=doc.get("project_number", ""),
            name=doc.get("name", ""),
            customer_id=doc.get("customer_id", ""),
            customer_name=doc.get("customer_name", ""),
            contract_value=float(doc.get("contract_value") or 0.0),
            original_contract_value=float(doc.get("original_contract_value") or 0.0),
            revised_contract_value=float(doc.get("revised_contract_value") or 0.0),
            contract_approved=bool(doc.get("contract_approved", False)),
            advance_terms=doc.get("advance_terms", ""),
            dlp_months=int(doc.get("dlp_months") or 0),
            project_manager=doc.get("project_manager", ""),
            consultant_name=doc.get("consultant_name", ""),
            owner_name=doc.get("owner_name", ""),
            hard_budget_check=bool(doc.get("hard_budget_check", False)),
            physically_completed_at=doc.get("physically_completed_at"),
            status=self._parse_project_status(
                doc.get("status", ProjectStatus.DRAFT.value)
            ),
            template_id=doc.get("template_id"),
            site_address=doc.get("site_address", ""),
            site_state_code=doc.get("site_state_code", ""),
            notes=doc.get("notes", ""),
            start_date=from_bson_date(doc.get("start_date")),
            expected_end_date=from_bson_date(doc.get("expected_end_date")),
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
            parties=[self._party_from_doc(p) for p in doc.get("parties", [])],
            phases=[self._phase_from_doc(p) for p in doc.get("phases", [])],
            activities=[
                self._activity_from_doc(a) for a in doc.get("activities", [])
            ],
            closed_at=doc.get("closed_at"),
            closed_by=doc.get("closed_by", ""),
            period_locked=bool(doc.get("period_locked", False)),
            advance_gst_policy=doc.get("advance_gst_policy", ""),
            overhead_allocation_pct=float(doc.get("overhead_allocation_pct") or 0.0),
            currency_code=(doc.get("currency_code") or "INR").strip() or "INR",
            final_snapshot=doc.get("final_snapshot"),
            enquiry_id=doc.get("enquiry_id", ""),
            archetype=doc.get("archetype", "Custom"),
            scale_profile=doc.get("scale_profile", "Small"),
            reopen_reason=doc.get("reopen_reason", ""),
            reopened_at=doc.get("reopened_at"),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, project: Project) -> Project:
        self._collection.replace_one(
            {"_id": project.id}, self._to_doc(project), upsert=True
        )
        return project

    def find_by_id(self, project_id: str) -> Optional[Project]:
        doc = self._collection.find_one({"_id": project_id})
        return self._from_doc(doc) if doc else None

    def list_all(self, status: Optional[ProjectStatus] = None) -> List[Project]:
        query: dict = {}
        if status is not None:
            query["status"] = status.value
        return [self._from_doc(d) for d in self._collection.find(query)]

    def search(self, query: str = "") -> List[Project]:
        term = (query or "").strip()
        if not term:
            return self.list_all()
        regex = {"$regex": re.escape(term), "$options": "i"}
        docs = self._collection.find(
            {
                "$or": [
                    {"project_number": regex},
                    {"name": regex},
                    {"customer_name": regex},
                    {"customer_id": regex},
                    {"site_address": regex},
                    {"notes": regex},
                    {"_id": regex},
                    {"parties.party_name": regex},
                ]
            }
        )
        return [self._from_doc(d) for d in docs]
