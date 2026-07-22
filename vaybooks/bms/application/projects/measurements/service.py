from __future__ import annotations

from datetime import date
from typing import List, Optional

from vaybooks.bms.domain.projects.measurement import ProjectMeasurement
from vaybooks.bms.domain.projects.repository import (
    ProjectBoqRepository,
    ProjectMeasurementRepository,
    ProjectRABillRepository,
    ProjectRepository,
)
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import ProjectMeasurementStatus
from vaybooks.bms.domain.shared.exceptions import ValidationError

_ELIGIBLE_RA_STATUSES = {
    ProjectMeasurementStatus.SUBMITTED,
    ProjectMeasurementStatus.ENGINEER_VERIFIED,
    ProjectMeasurementStatus.CUSTOMER_CERTIFIED,
}


class ProjectMeasurementAppService:
    def __init__(
        self,
        measurement_repo: ProjectMeasurementRepository,
        boq_repo: ProjectBoqRepository,
        project_repo: ProjectRepository,
        ra_repo: Optional[ProjectRABillRepository] = None,
    ):
        self._measurement_repo = measurement_repo
        self._boq_repo = boq_repo
        self._project_repo = project_repo
        self._ra_repo = ra_repo

    def _get_project(self, project_id: str):
        project = self._project_repo.find_by_id(project_id)
        if not project:
            raise ValidationError("Project not found")
        return project

    def _get_measurement(self, measurement_id: str) -> ProjectMeasurement:
        measurement = self._measurement_repo.find_by_id(measurement_id)
        if not measurement:
            raise ValidationError("Measurement not found")
        return measurement

    def _get_boq_item(self, boq_item_id: str, project_id: str):
        item = self._boq_repo.find_by_id(boq_item_id)
        if not item or item.project_id != project_id:
            raise ValidationError("BOQ item not found")
        return item

    def _prior_cumulative(self, boq_item_id: str, *, exclude_id: str = "") -> float:
        cumulative = 0.0
        for measurement in self._measurement_repo.list_by_boq_item(boq_item_id):
            if measurement.id == exclude_id:
                continue
            if measurement.status == ProjectMeasurementStatus.REJECTED:
                continue
            cumulative = max(cumulative, float(measurement.cumulative_quantity or 0.0))
        return cumulative

    def list_by_project(self, project_id: str) -> List[ProjectMeasurement]:
        self._get_project(project_id)
        return self._measurement_repo.list_by_project(project_id)

    def create(
        self,
        project_id: str,
        boq_item_id: str,
        measurement_date: date,
        quantity: float,
        *,
        location: str = "",
        dimensions: str = "",
        notes: str = "",
        override_qty_cap: bool = False,
        override_reason: str = "",
    ) -> ProjectMeasurement:
        self._get_project(project_id)
        boq_item = self._get_boq_item(boq_item_id, project_id)
        qty = float(quantity or 0.0)
        if qty <= 0:
            raise ValidationError("Measurement quantity must be greater than zero")
        prior = self._prior_cumulative(boq_item_id)
        cumulative = round(prior + qty, 4)
        cap = float(boq_item.contracted_qty or 0.0) + float(boq_item.varied_qty or 0.0)
        if cap > 0 and cumulative > cap + 0.0001 and not override_qty_cap:
            raise ValidationError(
                f"Cumulative quantity {cumulative} exceeds contracted cap {cap}"
            )
        if override_qty_cap and not (override_reason or "").strip():
            raise ValidationError("Override reason is required when overriding qty cap")
        measurement = ProjectMeasurement(
            project_id=project_id,
            boq_item_id=boq_item_id,
            measurement_date=measurement_date,
            location=(location or "").strip(),
            dimensions=(dimensions or "").strip(),
            quantity=qty,
            cumulative_quantity=cumulative,
            override_qty_cap=bool(override_qty_cap),
            override_reason=(override_reason or "").strip(),
            notes=(notes or "").strip(),
        )
        return self._measurement_repo.save(measurement)

    def submit(self, measurement_id: str) -> ProjectMeasurement:
        measurement = self._get_measurement(measurement_id)
        if measurement.status != ProjectMeasurementStatus.DRAFT:
            raise ValidationError("Only draft measurements can be submitted")
        measurement.status = ProjectMeasurementStatus.SUBMITTED
        measurement.updated_at = utc_now()
        saved = self._measurement_repo.save(measurement)
        self._boq_repo.save(
            self._sync_boq_measured_qty(measurement.boq_item_id, saved.cumulative_quantity)
        )
        return saved

    def verify(self, measurement_id: str, verified_by: str = "") -> ProjectMeasurement:
        measurement = self._get_measurement(measurement_id)
        if measurement.status != ProjectMeasurementStatus.SUBMITTED:
            raise ValidationError("Only submitted measurements can be verified")
        measurement.status = ProjectMeasurementStatus.ENGINEER_VERIFIED
        measurement.verified_by = (verified_by or "").strip()
        measurement.updated_at = utc_now()
        return self._measurement_repo.save(measurement)

    def certify(self, measurement_id: str, certified_by: str = "") -> ProjectMeasurement:
        measurement = self._get_measurement(measurement_id)
        if measurement.status not in (
            ProjectMeasurementStatus.SUBMITTED,
            ProjectMeasurementStatus.ENGINEER_VERIFIED,
        ):
            raise ValidationError("Measurement must be submitted or verified before certification")
        measurement.status = ProjectMeasurementStatus.CUSTOMER_CERTIFIED
        measurement.certified_by = (certified_by or "").strip()
        measurement.updated_at = utc_now()
        saved = self._measurement_repo.save(measurement)
        boq_item = self._get_boq_item(saved.boq_item_id, saved.project_id)
        boq_item.certified_qty = max(
            float(boq_item.certified_qty or 0.0),
            float(saved.cumulative_quantity or 0.0),
        )
        boq_item.updated_at = utc_now()
        self._boq_repo.save(boq_item)
        return saved

    def dispute(self, measurement_id: str) -> ProjectMeasurement:
        measurement = self._get_measurement(measurement_id)
        if measurement.status not in (
            ProjectMeasurementStatus.SUBMITTED,
            ProjectMeasurementStatus.ENGINEER_VERIFIED,
        ):
            raise ValidationError("Only submitted or verified measurements can be disputed")
        measurement.status = ProjectMeasurementStatus.DISPUTED
        measurement.updated_at = utc_now()
        return self._measurement_repo.save(measurement)

    def reject(self, measurement_id: str) -> ProjectMeasurement:
        measurement = self._get_measurement(measurement_id)
        if measurement.status == ProjectMeasurementStatus.REJECTED:
            raise ValidationError("Measurement is already rejected")
        if measurement.ra_bill_id:
            raise ValidationError("Measurement linked to an RA bill cannot be rejected")
        measurement.status = ProjectMeasurementStatus.REJECTED
        measurement.updated_at = utc_now()
        return self._measurement_repo.save(measurement)

    def eligible_for_ra(self, project_id: str) -> List[ProjectMeasurement]:
        self._get_project(project_id)
        return [
            m
            for m in self._measurement_repo.list_by_project(project_id)
            if m.status in _ELIGIBLE_RA_STATUSES and not (m.ra_bill_id or "").strip()
        ]

    def _sync_boq_measured_qty(self, boq_item_id: str, cumulative: float):
        item = self._boq_repo.find_by_id(boq_item_id)
        if not item:
            raise ValidationError("BOQ item not found")
        item.measured_qty = max(float(item.measured_qty or 0.0), float(cumulative or 0.0))
        item.updated_at = utc_now()
        return item
