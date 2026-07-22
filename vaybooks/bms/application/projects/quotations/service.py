from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Any, List, Optional
from uuid import uuid4

from vaybooks.bms.domain.finance.accounting.repository import CounterRepository
from vaybooks.bms.domain.projects.entities import (
    ProjectQuotation,
    ProjectQuotationLine,
    ProjectWorkOrder,
)
from vaybooks.bms.domain.projects.repository import (
    ProjectBoqRepository,
    ProjectQuotationRepository,
    ProjectRepository,
    ProjectWorkOrderRepository,
)
from vaybooks.bms.domain.projects.services import ProjectDomainService
from vaybooks.bms.domain.shared.date_utils import today, utc_now
from vaybooks.bms.domain.shared.enums import (
    ProjectBoqItemType,
    ProjectDocumentCategory,
    ProjectQuotationStatus,
    ProjectStatus,
)
from vaybooks.bms.domain.shared.exceptions import ValidationError


class ProjectQuotationAppService:
    def __init__(
        self,
        quotation_repo: ProjectQuotationRepository,
        project_repo: ProjectRepository,
        counter_repo: CounterRepository,
        *,
        document_service=None,
        business_service=None,
        work_order_repo: Optional[ProjectWorkOrderRepository] = None,
        boq_repo: Optional[ProjectBoqRepository] = None,
        boq_service=None,
        enquiry_service=None,
        access_policy=None,
        audit_service=None,
    ):
        self._quotation_repo = quotation_repo
        self._project_repo = project_repo
        self._counter_repo = counter_repo
        self._document_service = document_service
        self._business_service = business_service
        self._work_order_repo = work_order_repo
        self._boq_repo = boq_repo
        self._boq_service = boq_service
        self._enquiry_service = enquiry_service
        self._access_policy = access_policy
        self._audit_service = audit_service

    def _get_project(self, project_id: str):
        project = self._project_repo.find_by_id(project_id)
        if not project:
            raise ValidationError("Project not found")
        return project

    def _get_quotation(self, quotation_id: str) -> ProjectQuotation:
        quotation = self._quotation_repo.find_by_id(quotation_id)
        if not quotation:
            raise ValidationError("Quotation not found")
        return quotation

    def _parse_lines(self, raw_lines: List[dict]) -> List[ProjectQuotationLine]:
        lines: List[ProjectQuotationLine] = []
        for row in raw_lines or []:
            lines.append(
                ProjectQuotationLine(
                    description=(row.get("description") or "").strip(),
                    quantity=float(row.get("quantity") or 1.0),
                    rate=float(row.get("rate") or 0.0),
                    discount_pct=float(row.get("discount_pct") or 0.0),
                    hsn_sac=(row.get("hsn_sac") or "").strip(),
                    activity_id=row.get("activity_id"),
                    boq_item_id=(row.get("boq_item_id") or "").strip() or None,
                )
            )
        return lines

    def _quotation_pdf_adapter(self, quotation: ProjectQuotation) -> dict[str, Any]:
        lines: list[dict[str, Any]] = []
        for line in quotation.lines:
            gross = line.quantity * line.rate
            discount_amt = gross * (line.discount_pct / 100.0)
            lines.append(
                {
                    "description": line.description,
                    "qty": line.quantity,
                    "quantity": line.quantity,
                    "rate": line.rate,
                    "discount": round(discount_amt, 2),
                    "hsn_sac": line.hsn_sac,
                    "taxable_amount": round(line.line_total, 2),
                    "line_total": round(line.line_total, 2),
                }
            )
        return {
            "quotation_number": quotation.quotation_number,
            "quotation_date": quotation.quotation_date,
            "customer_name": quotation.customer_name,
            "lines": lines,
            "notes": quotation.notes,
            "status": quotation.status.value,
            "valid_until": quotation.valid_until,
            "document_content": {},
        }

    def default_lines_from_activities(self, project_id: str) -> List[dict]:
        """One BOQ line per leaf activity; rate = planned_revenue_amount if > 0."""
        project = self._get_project(project_id)
        leaf_ids = ProjectDomainService().leaf_activity_ids(project)
        lines: List[dict] = []
        for activity in sorted(
            project.activities, key=lambda a: (a.sort_order, a.name)
        ):
            if activity.id not in leaf_ids:
                continue
            rate = (
                float(activity.planned_revenue_amount)
                if activity.planned_revenue_amount > 0
                else 0.0
            )
            lines.append(
                {
                    "description": activity.name,
                    "quantity": 1.0,
                    "rate": rate,
                    "discount_pct": 0.0,
                    "hsn_sac": "",
                    "activity_id": activity.id,
                }
            )
        return lines

    def default_lines_from_boq(
        self, project_id: str, item_ids: Optional[List[str]] = None
    ) -> List[dict]:
        boq_repo = self._boq_repo
        if not boq_repo and self._boq_service:
            items = self._boq_service.list_items(project_id)
        elif boq_repo:
            items = boq_repo.list_by_project(project_id)
        else:
            raise ValidationError("BOQ service is unavailable")
        selected = set(item_ids or [])
        lines: List[dict] = []
        for item in items:
            if item.item_type != ProjectBoqItemType.ITEM:
                continue
            if selected and item.id not in selected:
                continue
            lines.append(
                {
                    "description": item.description,
                    "quantity": item.estimated_qty or item.contracted_qty or 1.0,
                    "rate": item.contracted_rate or item.selling_rate,
                    "discount_pct": 0.0,
                    "hsn_sac": item.hsn_sac,
                    "boq_item_id": item.id,
                    "activity_id": item.activity_id,
                }
            )
        return lines

    def default_lines_from_phases(self, project_id: str) -> List[dict]:
        """Activity amounts + BOQ materials without rates (customer-facing)."""
        project = self._get_project(project_id)
        phase_names = {p.id: p.name for p in project.phases}
        lines: List[dict] = []

        activities = sorted(
            project.activities, key=lambda a: (a.sort_order, a.name)
        )
        for activity in activities:
            phase_label = phase_names.get(activity.phase_id or "", "")
            prefix = f"[{phase_label}] " if phase_label else ""
            amount = float(activity.amount or activity.planned_revenue_amount or 0.0)
            lines.append(
                {
                    "description": f"{prefix}{activity.name}",
                    "quantity": 1.0,
                    "rate": amount,
                    "discount_pct": 0.0,
                    "hsn_sac": "",
                    "activity_id": activity.id,
                    "hide_rate": False,
                    "line_kind": "activity",
                }
            )

        boq_items: list = []
        if self._boq_service:
            boq_items = self._boq_service.list_items(project_id)
        elif self._boq_repo:
            boq_items = self._boq_repo.list_by_project(project_id)
        for item in boq_items:
            if item.item_type != ProjectBoqItemType.ITEM:
                continue
            # Material lines: qty/description only — rate hidden (0)
            phase_label = phase_names.get(getattr(item, "phase_id", None) or "", "")
            prefix = f"[{phase_label} Material] " if phase_label else "[Material] "
            qty = item.estimated_qty or item.contracted_qty or 1.0
            lines.append(
                {
                    "description": f"{prefix}{item.description}",
                    "quantity": qty,
                    "rate": 0.0,
                    "discount_pct": 0.0,
                    "hsn_sac": item.hsn_sac,
                    "boq_item_id": item.id,
                    "activity_id": item.activity_id,
                    "hide_rate": True,
                    "line_kind": "material",
                }
            )
        return lines

    def create_quotation(
        self,
        project_id: str,
        quotation_date: Optional[date] = None,
        lines: Optional[List[dict]] = None,
        notes: str = "",
        valid_until: Optional[date] = None,
        created_by: str = "",
    ) -> ProjectQuotation:
        project = self._get_project(project_id)
        quotation = ProjectQuotation(
            project_id=project.id,
            quotation_number=self._counter_repo.next("project_quotation_number"),
            quotation_date=quotation_date or today(),
            customer_id=project.customer_id,
            customer_name=project.customer_name,
            lines=self._parse_lines(lines or []),
            notes=(notes or "").strip(),
            valid_until=valid_until,
            root_id="",
            created_by=(created_by or "").strip(),
        )
        quotation.root_id = quotation.id
        return self._quotation_repo.save(quotation)

    def update_quotation(
        self,
        quotation_id: str,
        *,
        quotation_date: Optional[date] = None,
        lines: Optional[List[dict]] = None,
        notes: Optional[str] = None,
        valid_until: Optional[date] = None,
    ) -> ProjectQuotation:
        quotation = self._get_quotation(quotation_id)
        if quotation.status not in (
            ProjectQuotationStatus.DRAFT,
            ProjectQuotationStatus.PENDING_APPROVAL,
        ):
            raise ValidationError("Only draft quotations can be edited")
        if quotation_date is not None:
            quotation.quotation_date = quotation_date
        if lines is not None:
            quotation.lines = self._parse_lines(lines)
        if notes is not None:
            quotation.notes = (notes or "").strip()
        if valid_until is not None:
            quotation.valid_until = valid_until
        quotation.updated_at = utc_now()
        return self._quotation_repo.save(quotation)

    def get_quotation(self, quotation_id: str) -> Optional[ProjectQuotation]:
        return self._quotation_repo.find_by_id(quotation_id)

    def list_by_project(self, project_id: str) -> List[ProjectQuotation]:
        return self._quotation_repo.list_by_project(project_id)

    def submit_for_approval(
        self, quotation_id: str, submitted_by: str = ""
    ) -> ProjectQuotation:
        quotation = self._get_quotation(quotation_id)
        if quotation.status != ProjectQuotationStatus.DRAFT:
            raise ValidationError("Only draft quotations can be submitted")
        if not quotation.lines:
            raise ValidationError("Quotation must have at least one line")
        quotation.status = ProjectQuotationStatus.PENDING_APPROVAL
        quotation.submitted_by = (submitted_by or quotation.created_by or "").strip()
        quotation.updated_at = utc_now()
        saved = self._quotation_repo.save(quotation)
        self._audit(
            saved.project_id,
            "quotation",
            saved.id,
            "submit",
            actor_name=saved.submitted_by,
            after={"status": saved.status.value},
        )
        return saved

    def request_changes(self, quotation_id: str) -> ProjectQuotation:
        quotation = self._get_quotation(quotation_id)
        if quotation.status != ProjectQuotationStatus.PENDING_APPROVAL:
            raise ValidationError("Quotation is not pending approval")
        quotation.status = ProjectQuotationStatus.DRAFT
        quotation.updated_at = utc_now()
        return self._quotation_repo.save(quotation)

    def approve_quotation(
        self, quotation_id: str, approved_by: str = ""
    ) -> ProjectQuotation:
        quotation = self._get_quotation(quotation_id)
        if quotation.status != ProjectQuotationStatus.PENDING_APPROVAL:
            raise ValidationError("Quotation is not pending approval")
        actor = (approved_by or "").strip()
        if self._access_policy is not None:
            self._access_policy.assert_commercial_approve(
                actor_id=actor,
                actor_name=actor,
                submitted_by=quotation.submitted_by or quotation.created_by,
                document_label="quotation",
            )
        before = {"status": quotation.status.value}
        quotation.status = ProjectQuotationStatus.APPROVED
        quotation.approved_by = actor
        quotation.approved_at = utc_now()
        quotation.updated_at = utc_now()
        saved = self._quotation_repo.save(quotation)
        self._audit(
            saved.project_id,
            "quotation",
            saved.id,
            "approve",
            actor_name=actor,
            before=before,
            after={"status": saved.status.value},
        )
        return saved

    def _audit(
        self,
        project_id: str,
        entity_type: str,
        entity_id: str,
        action: str,
        *,
        actor_name: str = "",
        reason: str = "",
        before=None,
        after=None,
    ) -> None:
        if not self._audit_service:
            return
        try:
            self._audit_service.record(
                project_id,
                entity_type,
                entity_id,
                action,
                actor_name=actor_name,
                reason=reason,
                before=before,
                after=after,
            )
        except Exception:
            pass

    def send_quotation(self, quotation_id: str) -> ProjectQuotation:
        quotation = self._get_quotation(quotation_id)
        if quotation.status != ProjectQuotationStatus.APPROVED:
            raise ValidationError("Only approved quotations can be sent")
        quotation.status = ProjectQuotationStatus.SENT
        quotation.sent_at = utc_now()
        quotation.updated_at = utc_now()
        return self._quotation_repo.save(quotation)

    def accept_quotation(
        self,
        quotation_id: str,
        *,
        confirmation_date: Optional[date] = None,
        confirmation_note: str = "",
        confirmation_evidence: str = "",
    ) -> ProjectQuotation:
        quotation = self._get_quotation(quotation_id)
        if quotation.status != ProjectQuotationStatus.SENT:
            raise ValidationError("Only sent quotations can be accepted")
        quotation.status = ProjectQuotationStatus.ACCEPTED
        quotation.confirmation_date = confirmation_date or today()
        quotation.confirmation_note = (confirmation_note or "").strip()
        quotation.confirmation_evidence = (confirmation_evidence or "").strip()
        quotation.updated_at = utc_now()
        return self._quotation_repo.save(quotation)

    def compare_revisions(self, root_id: str) -> dict:
        """Return line-level diffs across quotation revisions sharing root_id."""
        rid = (root_id or "").strip()
        if not rid:
            raise ValidationError("root_id is required")
        if hasattr(self._quotation_repo, "list_all"):
            candidates = self._quotation_repo.list_all()
        else:
            raise ValidationError("Quotation repository cannot list revisions")
        revisions = sorted(
            [q for q in candidates if (q.root_id or q.id) == rid],
            key=lambda q: (q.revision_no, q.created_at),
        )
        if not revisions:
            raise ValidationError("No quotations found for root_id")

        def _line_key(line: ProjectQuotationLine) -> str:
            return (
                f"{(line.description or '').strip().lower()}|"
                f"{(line.boq_item_id or '')}|{(line.activity_id or '')}"
            )

        def _line_dict(line: ProjectQuotationLine) -> dict:
            return {
                "description": line.description,
                "quantity": line.quantity,
                "rate": line.rate,
                "discount_pct": line.discount_pct,
                "line_total": round(line.line_total, 2),
                "boq_item_id": line.boq_item_id,
                "activity_id": line.activity_id,
            }

        diffs: List[dict] = []
        for idx in range(1, len(revisions)):
            prev, curr = revisions[idx - 1], revisions[idx]
            prev_map = {_line_key(ln): ln for ln in prev.lines}
            curr_map = {_line_key(ln): ln for ln in curr.lines}
            added = [
                _line_dict(curr_map[k]) for k in curr_map.keys() - prev_map.keys()
            ]
            removed = [
                _line_dict(prev_map[k]) for k in prev_map.keys() - curr_map.keys()
            ]
            changed = []
            for key in prev_map.keys() & curr_map.keys():
                a, b = prev_map[key], curr_map[key]
                if (
                    float(a.quantity) != float(b.quantity)
                    or float(a.rate) != float(b.rate)
                    or float(a.discount_pct) != float(b.discount_pct)
                    or (a.description or "") != (b.description or "")
                ):
                    changed.append({"before": _line_dict(a), "after": _line_dict(b)})
            diffs.append(
                {
                    "from_revision": prev.revision_no,
                    "to_revision": curr.revision_no,
                    "from_id": prev.id,
                    "to_id": curr.id,
                    "added": added,
                    "removed": removed,
                    "changed": changed,
                }
            )
        return {
            "root_id": rid,
            "revision_count": len(revisions),
            "revisions": [
                {
                    "id": q.id,
                    "revision_no": q.revision_no,
                    "status": q.status.value,
                    "quotation_number": q.quotation_number,
                    "subtotal": q.subtotal,
                }
                for q in revisions
            ],
            "diffs": diffs,
        }

    def reject_quotation(self, quotation_id: str) -> ProjectQuotation:
        quotation = self._get_quotation(quotation_id)
        if quotation.status != ProjectQuotationStatus.SENT:
            raise ValidationError("Only sent quotations can be rejected")
        quotation.status = ProjectQuotationStatus.REJECTED
        quotation.updated_at = utc_now()
        return self._quotation_repo.save(quotation)

    def cancel_quotation(self, quotation_id: str) -> ProjectQuotation:
        quotation = self._get_quotation(quotation_id)
        if quotation.status in (
            ProjectQuotationStatus.CONVERTED,
            ProjectQuotationStatus.SUPERSEDED,
            ProjectQuotationStatus.CANCELLED,
        ):
            raise ValidationError("Quotation cannot be cancelled")
        quotation.status = ProjectQuotationStatus.CANCELLED
        quotation.updated_at = utc_now()
        return self._quotation_repo.save(quotation)

    def revise_quotation(self, quotation_id: str) -> ProjectQuotation:
        source = self._get_quotation(quotation_id)
        if source.status in (
            ProjectQuotationStatus.SUPERSEDED,
            ProjectQuotationStatus.CANCELLED,
        ):
            raise ValidationError("Quotation cannot be revised")
        revision = deepcopy(source)
        revision.id = uuid4().hex
        revision.quotation_number = self._counter_repo.next(
            "project_quotation_number"
        )
        revision.status = ProjectQuotationStatus.DRAFT
        revision.revision_no = source.revision_no + 1
        revision.root_id = source.root_id or source.id
        revision.supersedes_id = source.id
        revision.approved_by = ""
        revision.approved_at = None
        revision.sent_at = None
        revision.created_at = utc_now()
        revision.updated_at = utc_now()
        saved = self._quotation_repo.save(revision)
        source.status = ProjectQuotationStatus.SUPERSEDED
        source.updated_at = utc_now()
        self._quotation_repo.save(source)
        return saved

    def supersede_quotation(
        self, quotation_id: str, replacement_id: str
    ) -> ProjectQuotation:
        quotation = self._get_quotation(quotation_id)
        replacement = self._get_quotation(replacement_id)
        if quotation.project_id != replacement.project_id:
            raise ValidationError("Replacement quotation belongs to another project")
        quotation.status = ProjectQuotationStatus.SUPERSEDED
        quotation.supersedes_id = replacement.id
        quotation.updated_at = utc_now()
        return self._quotation_repo.save(quotation)

    def convert_to_project(
        self,
        quotation_id: str,
        *,
        set_contract_value: bool = True,
        create_work_order: bool = True,
    ) -> dict:
        quotation = self._get_quotation(quotation_id)
        if quotation.status not in (
            ProjectQuotationStatus.APPROVED,
            ProjectQuotationStatus.ACCEPTED,
        ):
            raise ValidationError("Only approved or accepted quotations can be converted")

        project = self._get_project(quotation.project_id)
        contract_value = quotation.subtotal
        wo_id = ""
        boq_items = []
        if self._boq_repo:
            boq_items = self._boq_repo.list_by_project(project.id)
        elif self._boq_service:
            boq_items = self._boq_service.list_items(project.id)

        lines_with_boq = [line for line in quotation.lines if line.boq_item_id]
        if lines_with_boq:
            baseline = [
                {
                    "boq_item_id": line.boq_item_id,
                    "qty": line.quantity,
                    "rate": line.rate,
                }
                for line in lines_with_boq
            ]
            if self._boq_service:
                self._boq_service.apply_contract_baseline(project.id, baseline)
            elif self._boq_repo:
                from vaybooks.bms.application.projects.boq.service import (
                    ProjectBoqAppService,
                )

                ProjectBoqAppService(self._boq_repo, self._project_repo).apply_contract_baseline(
                    project.id, baseline
                )
        elif quotation.lines:
            snapshot_lines = []
            for idx, line in enumerate(quotation.lines, start=1):
                if self._boq_service:
                    item = self._boq_service.create_item(
                        project.id,
                        f"Q{idx}",
                        line.description,
                        unit="Nos",
                        estimated_qty=line.quantity,
                        selling_rate=line.rate,
                        hsn_sac=line.hsn_sac,
                    )
                elif self._boq_repo:
                    from vaybooks.bms.domain.projects.boq import ProjectBoqItem

                    item = ProjectBoqItem(
                        project_id=project.id,
                        code=f"Q{idx}",
                        description=line.description,
                        estimated_qty=line.quantity,
                        selling_rate=line.rate,
                        hsn_sac=line.hsn_sac,
                        contracted_qty=line.quantity,
                        contracted_rate=line.rate,
                    )
                    item = self._boq_repo.save(item)
                else:
                    raise ValidationError("BOQ service is unavailable for contract snapshot")
                snapshot_lines.append(
                    {
                        "boq_item_id": item.id,
                        "qty": line.quantity,
                        "rate": line.rate,
                    }
                )
            if self._boq_service:
                self._boq_service.apply_contract_baseline(project.id, snapshot_lines)
            elif self._boq_repo:
                from vaybooks.bms.application.projects.boq.service import (
                    ProjectBoqAppService,
                )

                ProjectBoqAppService(self._boq_repo, self._project_repo).apply_contract_baseline(
                    project.id, snapshot_lines
                )
        elif boq_items:
            raise ValidationError(
                "Convert requires BOQ item references on quotation lines or empty BOQ"
            )

        if set_contract_value:
            if not project.contract_approved:
                project.original_contract_value = contract_value
            project.revised_contract_value = contract_value
            project.contract_value = contract_value
            project.contract_approved = True
            project.updated_at = utc_now()
            self._project_repo.save(project)

        if create_work_order:
            if not self._work_order_repo:
                raise ValidationError("Work order repository is unavailable")
            work_order = ProjectWorkOrder(
                project_id=quotation.project_id,
                wo_number=self._counter_repo.next("project_work_order_number"),
                wo_date=today(),
                description=f"Work order from {quotation.quotation_number}",
                quotation_id=quotation.id,
            )
            saved_wo = self._work_order_repo.save(work_order)
            wo_id = saved_wo.id

        quotation.status = ProjectQuotationStatus.CONVERTED
        quotation.updated_at = utc_now()
        self._quotation_repo.save(quotation)

        if self._enquiry_service is not None:
            try:
                self._enquiry_service.mark_won_for_project(quotation.project_id)
            except Exception:
                pass
            linked = self._get_project(quotation.project_id)
            if getattr(linked, "enquiry_id", "") and linked.status == ProjectStatus.DRAFT:
                linked.status = ProjectStatus.ACTIVE
                linked.updated_at = utc_now()
                self._project_repo.save(linked)

        return {
            "project_id": quotation.project_id,
            "quotation_id": quotation.id,
            "wo_id": wo_id,
            "contract_value": contract_value if set_contract_value else project.contract_value,
        }

    def generate_pdf(
        self, quotation_id: str, *, strip_internal: bool = False
    ) -> bytes:
        quotation = self._get_quotation(quotation_id)
        if not self._business_service:
            raise ValidationError("Business service is unavailable")

        from vaybooks.bms.infrastructure.pdf.sales_doc_pdf import (
            generate_sales_document_pdf,
        )

        adapter = self._quotation_pdf_adapter(quotation)
        if strip_internal:
            # Customer-safe path: strip cost/rate internals from the PDF payload.
            safe_lines = []
            for line in adapter.get("lines") or []:
                safe_lines.append(
                    {
                        **line,
                        "rate": 0.0,
                        "discount": 0.0,
                        "taxable_amount": 0.0,
                        "line_total": 0.0,
                        "hide_rate": True,
                    }
                )
            adapter["lines"] = safe_lines
            adapter["strip_internal"] = True
            adapter["notes"] = (
                (adapter.get("notes") or "")
                + ("\n" if adapter.get("notes") else "")
                + "Customer copy — internal cost rates omitted."
            ).strip()
        business = self._business_service.get_profile()
        pdf_bytes = generate_sales_document_pdf("quotation", adapter, business)

        if self._document_service:
            suffix = "-customer" if strip_internal else ""
            self._document_service.register_generated_pdf(
                quotation.project_id,
                name=f"{quotation.quotation_number}{suffix}.pdf",
                pdf_bytes=pdf_bytes,
                category=ProjectDocumentCategory.QUOTATION.value,
                source_ref_type="project_quotation",
                source_ref_id=quotation.id,
            )
        return pdf_bytes
