"""Subcontract work order measure and settle."""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from vaybooks.bms.domain.projects.subcontract import (
    ProjectSubcontractLine,
    ProjectSubcontractOrder,
)
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import ProjectSubcontractStatus
from vaybooks.bms.domain.shared.exceptions import ValidationError


class ProjectSubcontractAppService:
    def __init__(self, subcontract_repo, project_repo, counter_repo):
        self._repo = subcontract_repo
        self._project_repo = project_repo
        self._counter_repo = counter_repo

    def _get_project(self, project_id: str):
        project = self._project_repo.find_by_id(project_id)
        if not project:
            raise ValidationError("Project not found")
        return project

    def _get(self, order_id: str) -> ProjectSubcontractOrder:
        order = self._repo.find_by_id(order_id)
        if not order:
            raise ValidationError("Subcontract order not found")
        return order

    def get_order(self, order_id: str) -> ProjectSubcontractOrder:
        return self._get(order_id)

    def create_order(
        self,
        project_id: str,
        vendor_id: str,
        vendor_name: str,
        lines: List[dict],
        *,
        order_date: Optional[date] = None,
        description: str = "",
        retention_pct: float = 0.0,
        notes: str = "",
    ) -> ProjectSubcontractOrder:
        self._get_project(project_id)
        if not lines:
            raise ValidationError("At least one line is required")
        order = ProjectSubcontractOrder(
            project_id=project_id,
            order_number=self._counter_repo.next("project_subcon_number"),
            vendor_id=vendor_id,
            vendor_name=vendor_name,
            order_date=order_date or date.today(),
            description=(description or "").strip(),
            retention_pct=float(retention_pct or 0),
            notes=(notes or "").strip(),
            lines=[
                ProjectSubcontractLine(
                    description=row.get("description", ""),
                    quantity=float(row.get("quantity") or 0),
                    rate=float(row.get("rate") or 0),
                    unit=row.get("unit") or "Nos",
                    boq_item_id=row.get("boq_item_id") or "",
                )
                for row in lines
            ],
        )
        return self._repo.save(order)

    def list_orders(self, project_id: str) -> List[ProjectSubcontractOrder]:
        self._get_project(project_id)
        return self._repo.list_by_project(project_id)

    def activate(self, order_id: str) -> ProjectSubcontractOrder:
        order = self._get(order_id)
        order.status = ProjectSubcontractStatus.ACTIVE
        order.updated_at = utc_now()
        return self._repo.save(order)

    def record_measurement(
        self, order_id: str, line_id: str, measured_qty: float
    ) -> ProjectSubcontractOrder:
        order = self._get(order_id)
        line = next((ln for ln in order.lines if ln.id == line_id), None)
        if not line:
            raise ValidationError("Line not found")
        line.measured_qty = float(measured_qty or 0)
        order.status = ProjectSubcontractStatus.MEASURED
        order.updated_at = utc_now()
        return self._repo.save(order)

    def certify_line(
        self, order_id: str, line_id: str, certified_qty: float
    ) -> ProjectSubcontractOrder:
        order = self._get(order_id)
        line = next((ln for ln in order.lines if ln.id == line_id), None)
        if not line:
            raise ValidationError("Line not found")
        qty = float(certified_qty or 0)
        if qty > float(line.measured_qty or 0) + 0.0001:
            raise ValidationError("Certified quantity cannot exceed measured")
        line.certified_qty = qty
        order.updated_at = utc_now()
        return self._repo.save(order)

    def settle(
        self, order_id: str, *, line_settlements: Optional[List[dict]] = None
    ) -> dict:
        order = self._get(order_id)
        settlements = {row["line_id"]: float(row.get("qty") or 0) for row in (line_settlements or [])}
        gross = 0.0
        for line in order.lines:
            qty = settlements.get(line.id, float(line.certified_qty or 0))
            if qty + float(line.settled_qty or 0) > float(line.certified_qty or 0) + 0.0001:
                raise ValidationError("Cannot settle more than certified quantity")
            line.settled_qty = float(line.settled_qty or 0) + qty
            gross += qty * float(line.rate or 0)
        retention = round(gross * float(order.retention_pct or 0) / 100.0, 2)
        order.status = ProjectSubcontractStatus.SETTLED
        order.updated_at = utc_now()
        self._repo.save(order)
        return {
            "order_id": order.id,
            "gross": round(gross, 2),
            "retention": retention,
            "payable": round(gross - retention, 2),
        }
