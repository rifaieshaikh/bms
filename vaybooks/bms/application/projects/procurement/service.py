"""Procurement: material requests, RFQ, site stock movements."""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional

from vaybooks.bms.domain.projects.procurement import (
    ProjectMaterialRequest,
    ProjectMaterialRequestLine,
    ProjectRfq,
    ProjectRfqQuote,
    ProjectSiteStockMovement,
)
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import (
    ProjectMaterialOwnership,
    ProjectMaterialRequestStatus,
    ProjectRfqStatus,
    ProjectStockMovementType,
)
from vaybooks.bms.domain.shared.exceptions import ValidationError

_INVOICE_PARTIES = {"Customer", "Contractor"}
_PRINCIPAL_AGENTS = {"Principal", "Agent"}


class ProjectProcurementAppService:
    def __init__(
        self, procurement_repo, project_repo, counter_repo, purchase_service=None
    ):
        self._repo = procurement_repo
        self._project_repo = project_repo
        self._counter_repo = counter_repo
        self._purchase_service = purchase_service

    def _get_project(self, project_id: str):
        project = self._project_repo.find_by_id(project_id)
        if not project:
            raise ValidationError("Project not found")
        return project

    def create_material_request(
        self,
        project_id: str,
        lines: List[dict],
        *,
        need_by: Optional[date] = None,
        notes: str = "",
        invoice_party: str = "Contractor",
        principal_agent: str = "Principal",
    ) -> ProjectMaterialRequest:
        self._get_project(project_id)
        if not lines:
            raise ValidationError("At least one line is required")
        invoice_party, principal_agent = self._validate_party_flags(
            invoice_party, principal_agent
        )
        mr = ProjectMaterialRequest(
            project_id=project_id,
            request_number=self._counter_repo.next("project_mr_number"),
            need_by=need_by,
            notes=(notes or "").strip(),
            invoice_party=invoice_party,
            principal_agent=principal_agent,
            lines=[
                ProjectMaterialRequestLine(
                    description=row.get("description", ""),
                    quantity=float(row.get("quantity") or 0),
                    unit=row.get("unit") or "Nos",
                    activity_id=row.get("activity_id") or "",
                    boq_item_id=row.get("boq_item_id") or "",
                )
                for row in lines
            ],
        )
        return self._repo.save_material_request(mr)

    def list_material_requests(self, project_id: str) -> List[ProjectMaterialRequest]:
        self._get_project(project_id)
        return self._repo.list_material_requests_by_project(project_id)

    def submit_material_request(self, mr_id: str) -> ProjectMaterialRequest:
        mr = self._repo.find_material_request_by_id(mr_id)
        if not mr:
            raise ValidationError("Material request not found")
        mr.status = ProjectMaterialRequestStatus.SUBMITTED
        mr.updated_at = utc_now()
        return self._repo.save_material_request(mr)

    def approve_material_request(self, mr_id: str) -> ProjectMaterialRequest:
        mr = self._repo.find_material_request_by_id(mr_id)
        if not mr:
            raise ValidationError("Material request not found")
        mr.status = ProjectMaterialRequestStatus.APPROVED
        mr.updated_at = utc_now()
        return self._repo.save_material_request(mr)

    def create_rfq(
        self,
        project_id: str,
        description: str,
        quantity: float,
        *,
        unit: str = "Nos",
        material_request_id: str = "",
    ) -> ProjectRfq:
        self._get_project(project_id)
        rfq = ProjectRfq(
            project_id=project_id,
            rfq_number=self._counter_repo.next("project_rfq_number"),
            description=(description or "").strip(),
            quantity=float(quantity or 0),
            unit=unit or "Nos",
            material_request_id=material_request_id or "",
        )
        return self._repo.save_rfq(rfq)

    def add_rfq_quote(
        self,
        rfq_id: str,
        vendor_id: str,
        vendor_name: str,
        unit_price: float,
        *,
        lead_time_days: int = 0,
        notes: str = "",
    ) -> ProjectRfq:
        rfq = self._repo.find_rfq_by_id(rfq_id)
        if not rfq:
            raise ValidationError("RFQ not found")
        rfq.quotes.append(
            ProjectRfqQuote(
                vendor_id=vendor_id,
                vendor_name=vendor_name,
                unit_price=float(unit_price or 0),
                lead_time_days=int(lead_time_days or 0),
                notes=(notes or "").strip(),
            )
        )
        rfq.status = ProjectRfqStatus.COMPARED if len(rfq.quotes) > 1 else ProjectRfqStatus.SENT
        rfq.updated_at = utc_now()
        return self._repo.save_rfq(rfq)

    def award_rfq(self, rfq_id: str, quote_id: str, *, po_id: str = "") -> ProjectRfq:
        rfq = self._repo.find_rfq_by_id(rfq_id)
        if not rfq:
            raise ValidationError("RFQ not found")
        quote = next((q for q in rfq.quotes if q.id == quote_id), None)
        if not quote:
            raise ValidationError("Quote not found on RFQ")
        resolved_po_id = (po_id or "").strip()
        if not resolved_po_id and self._purchase_service is not None:
            po = self._purchase_service.create_purchase_order(
                vendor_id=quote.vendor_id,
                order_date=date.today(),
                lines=[
                    {
                        "product_name": rfq.description,
                        "qty_ordered": rfq.quantity,
                        "rate": quote.unit_price,
                    }
                ],
                notes=f"From RFQ {rfq.rfq_number}",
                project_id=rfq.project_id,
            )
            resolved_po_id = getattr(po, "id", "") or ""
        rfq.awarded_quote_id = quote_id
        rfq.po_id = resolved_po_id
        rfq.status = ProjectRfqStatus.AWARDED
        rfq.updated_at = utc_now()
        return self._repo.save_rfq(rfq)

    def list_rfqs(self, project_id: str) -> List[ProjectRfq]:
        self._get_project(project_id)
        return self._repo.list_rfqs_by_project(project_id)

    @staticmethod
    def _validate_party_flags(
        invoice_party: str, principal_agent: str
    ) -> tuple[str, str]:
        invoice_party = (invoice_party or "Contractor").strip()
        principal_agent = (principal_agent or "Principal").strip()
        if invoice_party not in _INVOICE_PARTIES:
            raise ValidationError(
                f"invoice_party must be one of: {', '.join(sorted(_INVOICE_PARTIES))}"
            )
        if principal_agent not in _PRINCIPAL_AGENTS:
            raise ValidationError(
                f"principal_agent must be one of: {', '.join(sorted(_PRINCIPAL_AGENTS))}"
            )
        return invoice_party, principal_agent

    def record_stock_movement(
        self,
        project_id: str,
        movement_type,
        description: str,
        quantity: float,
        *,
        unit: str = "Nos",
        unit_cost: float = 0.0,
        activity_id: str = "",
        boq_item_id: str = "",
        ownership=ProjectMaterialOwnership.CONTRACTOR,
        invoice_party: str = "",
        principal_agent: str = "Principal",
        source_ref_type: str = "",
        source_ref_id: str = "",
        notes: str = "",
    ) -> ProjectSiteStockMovement:
        self._get_project(project_id)
        if isinstance(movement_type, str):
            movement_type = ProjectStockMovementType(movement_type)
        if isinstance(ownership, str):
            ownership = ProjectMaterialOwnership(ownership)
        if float(quantity or 0) == 0:
            raise ValidationError("Quantity is required")
        if not invoice_party:
            invoice_party = (
                "Customer"
                if ownership == ProjectMaterialOwnership.CUSTOMER
                else "Contractor"
            )
        invoice_party, principal_agent = self._validate_party_flags(
            invoice_party, principal_agent
        )
        movement = ProjectSiteStockMovement(
            project_id=project_id,
            movement_type=movement_type,
            description=(description or "").strip(),
            quantity=float(quantity),
            unit=unit or "Nos",
            unit_cost=float(unit_cost or 0),
            activity_id=activity_id or "",
            boq_item_id=boq_item_id or "",
            ownership=ownership,
            invoice_party=invoice_party,
            principal_agent=principal_agent,
            source_ref_type=source_ref_type or "",
            source_ref_id=source_ref_id or "",
            notes=(notes or "").strip(),
        )
        return self._repo.save_stock_movement(movement)

    def list_stock_movements(self, project_id: str) -> List[ProjectSiteStockMovement]:
        self._get_project(project_id)
        return self._repo.list_stock_movements_by_project(project_id)

    def contractor_consumed_cost(self, project_id: str) -> float:
        total = 0.0
        for movement in self.list_stock_movements(project_id):
            if movement.ownership != ProjectMaterialOwnership.CONTRACTOR:
                continue
            if movement.movement_type not in (
                ProjectStockMovementType.CONSUME,
                ProjectStockMovementType.ISSUE,
            ):
                continue
            total += abs(movement.quantity) * float(movement.unit_cost or 0)
        return round(total, 2)

    def stock_reconciliation(self, project_id: str) -> Dict:
        """Return on-hand qty by ownership (and by item description)."""
        self._get_project(project_id)
        inbound = {
            ProjectStockMovementType.RECEIPT,
            ProjectStockMovementType.RETURN,
        }
        outbound = {
            ProjectStockMovementType.ISSUE,
            ProjectStockMovementType.CONSUME,
            ProjectStockMovementType.TRANSFER,
        }
        by_ownership: Dict[str, float] = {
            ProjectMaterialOwnership.CONTRACTOR.value: 0.0,
            ProjectMaterialOwnership.CUSTOMER.value: 0.0,
        }
        by_item: Dict[str, Dict[str, float]] = {}
        for movement in self.list_stock_movements(project_id):
            own = (
                movement.ownership.value
                if hasattr(movement.ownership, "value")
                else str(movement.ownership)
            )
            qty = float(movement.quantity or 0)
            if movement.movement_type in outbound:
                qty = -abs(qty)
            elif movement.movement_type in inbound:
                qty = abs(qty)
            by_ownership[own] = round(by_ownership.get(own, 0.0) + qty, 4)
            key = f"{movement.description}|{own}|{movement.unit}"
            bucket = by_item.setdefault(
                key,
                {
                    "description": movement.description,
                    "ownership": own,
                    "unit": movement.unit,
                    "qty": 0.0,
                },
            )
            bucket["qty"] = round(float(bucket["qty"]) + qty, 4)
        return {
            "by_ownership": by_ownership,
            "lines": list(by_item.values()),
        }
