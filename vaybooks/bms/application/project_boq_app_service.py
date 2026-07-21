from __future__ import annotations

import csv
from io import StringIO
from typing import List, Optional

from vaybooks.bms.domain.projects.boq import ProjectBoqItem
from vaybooks.bms.domain.projects.repository import ProjectBoqRepository, ProjectRepository
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import ProjectBoqItemType
from vaybooks.bms.domain.shared.exceptions import ValidationError

_UPDATE_FIELDS = {
    "code",
    "description",
    "item_type",
    "parent_id",
    "unit",
    "sort_order",
    "estimated_qty",
    "material_cost",
    "labour_cost",
    "equipment_cost",
    "subcon_cost",
    "overhead_cost",
    "contingency_cost",
    "selling_rate",
    "hsn_sac",
    "activity_id",
    "phase_id",
    "contracted_qty",
    "contracted_rate",
    "varied_qty",
}


class ProjectBoqAppService:
    def __init__(self, boq_repo: ProjectBoqRepository, project_repo: ProjectRepository):
        self._boq_repo = boq_repo
        self._project_repo = project_repo

    def _get_project(self, project_id: str):
        project = self._project_repo.find_by_id(project_id)
        if not project:
            raise ValidationError("Project not found")
        return project

    def _get_item(self, item_id: str) -> ProjectBoqItem:
        item = self._boq_repo.find_by_id(item_id)
        if not item:
            raise ValidationError("BOQ item not found")
        return item

    def _children(self, project_id: str, parent_id: str) -> List[ProjectBoqItem]:
        return [
            item
            for item in self._boq_repo.list_by_project(project_id)
            if item.parent_id == parent_id
        ]

    def list_items(self, project_id: str) -> List[ProjectBoqItem]:
        self._get_project(project_id)
        return self._boq_repo.list_by_project(project_id)

    def get_item(self, item_id: str) -> Optional[ProjectBoqItem]:
        return self._boq_repo.find_by_id(item_id)

    def create_item(
        self,
        project_id: str,
        code: str,
        description: str,
        *,
        item_type: ProjectBoqItemType = ProjectBoqItemType.ITEM,
        parent_id: Optional[str] = None,
        unit: str = "Nos",
        sort_order: int = 0,
        estimated_qty: float = 0,
        material_cost: float = 0,
        labour_cost: float = 0,
        equipment_cost: float = 0,
        subcon_cost: float = 0,
        overhead_cost: float = 0,
        contingency_cost: float = 0,
        selling_rate: float = 0,
        hsn_sac: str = "",
        activity_id: Optional[str] = None,
        phase_id: Optional[str] = None,
    ) -> ProjectBoqItem:
        self._get_project(project_id)
        code = (code or "").strip()
        if not code:
            raise ValidationError("BOQ code is required")
        if not (description or "").strip():
            raise ValidationError("BOQ description is required")
        if parent_id:
            parent = self._boq_repo.find_by_id(parent_id)
            if not parent or parent.project_id != project_id:
                raise ValidationError("Parent BOQ item not found")
        if isinstance(item_type, str):
            item_type = ProjectBoqItemType(item_type)
        item = ProjectBoqItem(
            project_id=project_id,
            code=code,
            description=(description or "").strip(),
            item_type=item_type,
            parent_id=parent_id,
            unit=(unit or "Nos").strip() or "Nos",
            sort_order=int(sort_order or 0),
            estimated_qty=float(estimated_qty or 0.0),
            material_cost=float(material_cost or 0.0),
            labour_cost=float(labour_cost or 0.0),
            equipment_cost=float(equipment_cost or 0.0),
            subcon_cost=float(subcon_cost or 0.0),
            overhead_cost=float(overhead_cost or 0.0),
            contingency_cost=float(contingency_cost or 0.0),
            selling_rate=float(selling_rate or 0.0),
            hsn_sac=(hsn_sac or "").strip(),
            activity_id=activity_id,
            phase_id=phase_id,
        )
        return self._boq_repo.save(item)

    def update_item(self, item_id: str, **fields) -> ProjectBoqItem:
        unknown = set(fields) - _UPDATE_FIELDS
        if unknown:
            raise ValidationError(f"Unknown fields: {', '.join(sorted(unknown))}")
        item = self._get_item(item_id)
        if "code" in fields:
            code = (fields["code"] or "").strip()
            if not code:
                raise ValidationError("BOQ code is required")
            item.code = code
        if "description" in fields:
            desc = (fields["description"] or "").strip()
            if not desc:
                raise ValidationError("BOQ description is required")
            item.description = desc
        if "item_type" in fields:
            item_type = fields["item_type"]
            if isinstance(item_type, str):
                item_type = ProjectBoqItemType(item_type)
            item.item_type = item_type
        if "parent_id" in fields:
            parent_id = fields["parent_id"]
            if parent_id:
                if parent_id == item_id:
                    raise ValidationError("BOQ item cannot be its own parent")
                parent = self._boq_repo.find_by_id(parent_id)
                if not parent or parent.project_id != item.project_id:
                    raise ValidationError("Parent BOQ item not found")
            item.parent_id = parent_id
        if "unit" in fields:
            item.unit = (fields["unit"] or "Nos").strip() or "Nos"
        if "sort_order" in fields:
            item.sort_order = int(fields["sort_order"] or 0)
        if "hsn_sac" in fields:
            item.hsn_sac = (fields["hsn_sac"] or "").strip()
        if "activity_id" in fields:
            item.activity_id = fields["activity_id"]
        if "phase_id" in fields:
            item.phase_id = fields["phase_id"]
        for key in (
            "estimated_qty",
            "material_cost",
            "labour_cost",
            "equipment_cost",
            "subcon_cost",
            "overhead_cost",
            "contingency_cost",
            "selling_rate",
            "contracted_qty",
            "contracted_rate",
            "varied_qty",
        ):
            if key in fields:
                setattr(item, key, float(fields[key] or 0.0))
        item.updated_at = utc_now()
        return self._boq_repo.save(item)

    def delete_item(self, item_id: str) -> None:
        item = self._get_item(item_id)
        if self._children(item.project_id, item_id):
            raise ValidationError("Remove child BOQ items before deleting this item")
        self._boq_repo.delete(item_id)

    SAMPLE_CSV_COLUMNS = (
        "code,description,item_type,parent_code,unit,estimated_qty,"
        "material_cost,labour_cost,equipment_cost,subcon_cost,"
        "overhead_cost,contingency_cost,selling_rate,hsn_sac"
    )

    SAMPLE_CSV = (
        SAMPLE_CSV_COLUMNS
        + "\n"
        + "\n".join(
            [
                "A,Civil Works,Section,,Nos,0,0,0,0,0,0,0,0,",
                "A.1,Brickwork,Item,A,Cum,10,500,200,0,0,50,0,900,9954",
                "A.2,Plastering,Item,A,Sqm,50,80,40,0,0,10,0,150,9954",
                "B,Finishes,Section,,Nos,0,0,0,0,0,0,0,0,",
                "B.1,Painting,Item,B,Sqm,120,40,25,0,0,5,0,85,9954",
            ]
        )
        + "\n"
    )

    def sample_csv(self) -> str:
        """Return a downloadable sample BOQ CSV matching import_csv columns."""
        return self.SAMPLE_CSV

    def import_csv(self, project_id: str, csv_text: str) -> dict:
        self._get_project(project_id)
        reader = csv.DictReader(StringIO(csv_text or ""))
        if not reader.fieldnames:
            raise ValidationError("CSV has no header row")
        created: List[ProjectBoqItem] = []
        errors: List[str] = []
        pending_rows: List[dict] = []
        code_to_id: dict[str, str] = {}
        existing = {item.code: item for item in self._boq_repo.list_by_project(project_id)}
        code_to_id.update({code: item.id for code, item in existing.items()})

        for row_num, row in enumerate(reader, start=2):
            code = (row.get("code") or "").strip()
            if not code:
                errors.append(f"Row {row_num}: code is required")
                continue
            item_type_raw = (row.get("item_type") or ProjectBoqItemType.ITEM.value).strip()
            try:
                item_type = ProjectBoqItemType(item_type_raw)
            except ValueError:
                errors.append(f"Row {row_num}: invalid item_type '{item_type_raw}'")
                continue
            parent_code = (row.get("parent_code") or "").strip()
            if parent_code and parent_code not in code_to_id:
                pending_rows.append({"row_num": row_num, "row": row})
                continue
            try:
                item = self._item_from_csv_row(
                    project_id,
                    row,
                    item_type=item_type,
                    parent_id=code_to_id.get(parent_code) if parent_code else None,
                )
                saved = self._boq_repo.save(item)
                created.append(saved)
                code_to_id[code] = saved.id
            except ValidationError as exc:
                errors.append(f"Row {row_num}: {exc}")

        for pass_num in range(len(pending_rows) + 1):
            if not pending_rows:
                break
            remaining: List[dict] = []
            for pending in pending_rows:
                row = pending["row"]
                row_num = pending["row_num"]
                code = (row.get("code") or "").strip()
                parent_code = (row.get("parent_code") or "").strip()
                if parent_code and parent_code not in code_to_id:
                    remaining.append(pending)
                    continue
                try:
                    item_type = ProjectBoqItemType(
                        (row.get("item_type") or ProjectBoqItemType.ITEM.value).strip()
                    )
                    item = self._item_from_csv_row(
                        project_id,
                        row,
                        item_type=item_type,
                        parent_id=code_to_id.get(parent_code) if parent_code else None,
                    )
                    saved = self._boq_repo.save(item)
                    created.append(saved)
                    code_to_id[code] = saved.id
                except ValidationError as exc:
                    errors.append(f"Row {row_num}: {exc}")
            if len(remaining) == len(pending_rows):
                for pending in remaining:
                    parent_code = (pending["row"].get("parent_code") or "").strip()
                    errors.append(
                        f"Row {pending['row_num']}: parent_code '{parent_code}' not found"
                    )
                break
            pending_rows = remaining

        return {"created": created, "errors": errors}

    def _item_from_csv_row(
        self,
        project_id: str,
        row: dict,
        *,
        item_type: ProjectBoqItemType,
        parent_id: Optional[str],
    ) -> ProjectBoqItem:
        code = (row.get("code") or "").strip()
        description = (row.get("description") or "").strip()
        if not description:
            raise ValidationError("description is required")
        return ProjectBoqItem(
            project_id=project_id,
            code=code,
            description=description,
            item_type=item_type,
            parent_id=parent_id,
            unit=(row.get("unit") or "Nos").strip() or "Nos",
            estimated_qty=float(row.get("estimated_qty") or 0.0),
            material_cost=float(row.get("material_cost") or 0.0),
            labour_cost=float(row.get("labour_cost") or 0.0),
            equipment_cost=float(row.get("equipment_cost") or 0.0),
            subcon_cost=float(row.get("subcon_cost") or 0.0),
            overhead_cost=float(row.get("overhead_cost") or 0.0),
            contingency_cost=float(row.get("contingency_cost") or 0.0),
            selling_rate=float(row.get("selling_rate") or 0.0),
            hsn_sac=(row.get("hsn_sac") or "").strip(),
        )

    def seed_from_apartment_interior(self, project_id: str) -> List[ProjectBoqItem]:
        self._get_project(project_id)
        existing = self._boq_repo.list_by_project(project_id)
        if existing:
            return existing
        prep = self.create_item(
            project_id,
            "1.0",
            "Preparation",
            item_type=ProjectBoqItemType.SECTION,
            sort_order=1,
        )
        exec_section = self.create_item(
            project_id,
            "2.0",
            "Execution",
            item_type=ProjectBoqItemType.SECTION,
            sort_order=2,
        )
        samples = [
            ("2.1", "Demolition", "Sqft", 800, 12000),
            ("2.2", "Electrical rewiring", "Lump Sum", 1, 85000),
            ("2.3", "Plumbing", "Lump Sum", 1, 65000),
            ("2.4", "Carpentry", "Sqft", 600, 450),
            ("2.5", "Painting", "Sqft", 1200, 85),
        ]
        created = [prep, exec_section]
        for idx, (code, desc, unit, qty, rate) in enumerate(samples, start=1):
            created.append(
                self.create_item(
                    project_id,
                    code,
                    desc,
                    parent_id=exec_section.id,
                    unit=unit,
                    sort_order=idx,
                    estimated_qty=float(qty),
                    selling_rate=float(rate),
                )
            )
        return created

    def rollup_totals(self, project_id: str) -> dict:
        items = self.list_items(project_id)
        line_items = [i for i in items if i.item_type == ProjectBoqItemType.ITEM]
        estimated_cost = round(sum(i.estimated_cost for i in line_items), 2)
        estimated_value = round(sum(i.estimated_value for i in line_items), 2)
        contracted_value = round(
            sum(
                (i.contracted_qty + i.varied_qty) * (i.contracted_rate or i.selling_rate)
                for i in line_items
            ),
            2,
        )
        return {
            "project_id": project_id,
            "item_count": len(line_items),
            "section_count": sum(
                1 for i in items if i.item_type == ProjectBoqItemType.SECTION
            ),
            "estimated_cost": estimated_cost,
            "estimated_value": estimated_value,
            "contracted_value": contracted_value,
            "measured_qty_total": round(sum(i.measured_qty for i in line_items), 2),
            "certified_qty_total": round(sum(i.certified_qty for i in line_items), 2),
            "billed_qty_total": round(sum(i.billed_qty for i in line_items), 2),
        }

    def apply_contract_baseline(self, project_id: str, lines: List[dict]) -> None:
        self._get_project(project_id)
        items = self._boq_repo.list_by_project(project_id)
        by_id = {item.id: item for item in items}
        by_code = {item.code: item for item in items}
        for row in lines or []:
            item = None
            boq_item_id = (row.get("boq_item_id") or "").strip()
            code = (row.get("code") or "").strip()
            if boq_item_id:
                item = by_id.get(boq_item_id)
            elif code:
                item = by_code.get(code)
            if not item:
                raise ValidationError("BOQ item not found for contract baseline line")
            qty = float(row.get("qty") or row.get("quantity") or 0.0)
            rate = float(row.get("rate") or 0.0)
            item.contracted_qty = qty
            item.contracted_rate = rate
            item.updated_at = utc_now()
            self._boq_repo.save(item)

    def _adjust_qty(self, boq_item_id: str, field: str, qty: float) -> ProjectBoqItem:
        if float(qty or 0) <= 0:
            raise ValidationError("Quantity must be greater than zero")
        item = self._get_item(boq_item_id)
        current = float(getattr(item, field) or 0.0)
        setattr(item, field, round(current + float(qty), 4))
        item.updated_at = utc_now()
        return self._boq_repo.save(item)

    def add_billed_qty(self, boq_item_id: str, qty: float) -> ProjectBoqItem:
        return self._adjust_qty(boq_item_id, "billed_qty", qty)

    def add_measured_qty(self, boq_item_id: str, qty: float) -> ProjectBoqItem:
        return self._adjust_qty(boq_item_id, "measured_qty", qty)

    def add_certified_qty(self, boq_item_id: str, qty: float) -> ProjectBoqItem:
        return self._adjust_qty(boq_item_id, "certified_qty", qty)

    def save_rate_analysis(
        self,
        item_id: str,
        material_cost: float = 0.0,
        labour_cost: float = 0.0,
        equipment_cost: float = 0.0,
        subcon_cost: float = 0.0,
        overhead_cost: float = 0.0,
        contingency_cost: float = 0.0,
        *,
        selling_rate: Optional[float] = None,
        margin_pct: Optional[float] = None,
        override_reason: str = "",
    ) -> ProjectBoqItem:
        item = self._get_item(item_id)
        item.material_cost = float(material_cost or 0.0)
        item.labour_cost = float(labour_cost or 0.0)
        item.equipment_cost = float(equipment_cost or 0.0)
        item.subcon_cost = float(subcon_cost or 0.0)
        item.overhead_cost = float(overhead_cost or 0.0)
        item.contingency_cost = float(contingency_cost or 0.0)
        unit_cost = item.estimated_cost
        if selling_rate is not None:
            item.selling_rate = float(selling_rate)
            item.rate_override_reason = (override_reason or "").strip()
        elif margin_pct is not None:
            item.selling_rate = round(unit_cost * (1 + float(margin_pct) / 100.0), 4)
            if override_reason:
                item.rate_override_reason = (override_reason or "").strip()
        else:
            item.selling_rate = round(unit_cost, 4)
            if override_reason:
                item.rate_override_reason = (override_reason or "").strip()
        item.updated_at = utc_now()
        return self._boq_repo.save(item)

    def add_varied_qty(self, boq_item_id: str, qty: float) -> ProjectBoqItem:
        return self._adjust_qty(boq_item_id, "varied_qty", qty)
