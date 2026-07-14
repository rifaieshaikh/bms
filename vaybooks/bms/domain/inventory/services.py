from datetime import date, datetime
from typing import Any, Dict, List, Optional

from vaybooks.bms.domain.inventory.category_tree import (
    build_category_paths,
    normalize_parent_id,
    validate_category_parent,
)
from vaybooks.bms.domain.inventory.entities import (
    InventoryProduct,
    ProductCategory,
    ProductUnit,
    StockMovement,
)
from vaybooks.bms.domain.inventory.field_definitions import (
    ProductFieldDefinition,
    ProductFieldType,
    normalize_field_key,
    validate_custom_field_values,
)
from vaybooks.bms.domain.inventory.repository import (
    InventoryProductRepository,
    ProductCategoryRepository,
    ProductFieldDefinitionRepository,
    ProductUnitRepository,
    StockMovementRepository,
)
from vaybooks.bms.domain.inventory.rate_history_service import ProductRateHistoryService
from vaybooks.bms.domain.inventory.units import default_unit_label, normalize_unit_code
from vaybooks.bms.domain.shared.enums import StockMovementType, StockReferenceType
from vaybooks.bms.domain.shared.exceptions import ValidationError

INFLOW_TYPES = frozenset(
    {
        StockMovementType.RECEIVE,
        StockMovementType.ADJUST_IN,
        StockMovementType.PURCHASE_RECEIVE,
        StockMovementType.SALES_RETURN,
    }
)


def movement_qty_in(movement_type: StockMovementType, qty: float) -> float:
    return round(qty, 2) if movement_type in INFLOW_TYPES else 0.0


def movement_qty_out(movement_type: StockMovementType, qty: float) -> float:
    return 0.0 if movement_type in INFLOW_TYPES else round(qty, 2)


def _movement_sort_key(movement: StockMovement) -> tuple:
    md = movement.movement_date
    if isinstance(md, datetime):
        md = md.date()
    created = movement.created_at
    ts = created.timestamp() if isinstance(created, datetime) else 0.0
    return (md, ts, movement.id)


class InventoryDomainService:
    def __init__(
        self,
        category_repo: ProductCategoryRepository,
        product_repo: InventoryProductRepository,
        movement_repo: StockMovementRepository,
        unit_repo: Optional[ProductUnitRepository] = None,
        field_def_repo: Optional[ProductFieldDefinitionRepository] = None,
        rate_history: Optional[ProductRateHistoryService] = None,
    ):
        self._category_repo = category_repo
        self._product_repo = product_repo
        self._movement_repo = movement_repo
        self._unit_repo = unit_repo
        self._field_def_repo = field_def_repo
        self._rate_history = rate_history

    def _categories_by_id(self) -> Dict[str, ProductCategory]:
        return {c.id: c for c in self._category_repo.list_all(active_only=False)}

    def list_units(self, active_only: bool = True) -> List[ProductUnit]:
        if not self._unit_repo:
            return []
        return self._unit_repo.list_all(active_only=active_only)

    def find_or_create_unit(self, code: str, label: str = "") -> ProductUnit:
        if not self._unit_repo:
            raise ValidationError("Unit repository not configured")
        normalized = normalize_unit_code(code)
        if not normalized:
            raise ValidationError("Unit code is required")
        existing = self._unit_repo.find_by_code(normalized)
        if existing:
            return existing
        unit = ProductUnit(
            code=normalized,
            label=(label or default_unit_label(normalized)).strip(),
        )
        return self._unit_repo.save(unit)

    def update_unit(self, unit_id: str, label: str, is_active: bool = True) -> ProductUnit:
        if not self._unit_repo:
            raise ValidationError("Unit repository not configured")
        unit = self._unit_repo.find_by_id(unit_id)
        if not unit:
            raise ValidationError("Unit not found")
        label = (label or "").strip()
        if not label:
            raise ValidationError("Unit label is required")
        unit.update(label=label, is_active=is_active)
        return self._unit_repo.save(unit)

    def resolve_unit_for_product(self, product: InventoryProduct) -> InventoryProduct:
        if not self._unit_repo:
            return product
        if product.unit_id:
            unit = self._unit_repo.find_by_id(product.unit_id)
            if unit:
                product.unit = unit.code
                return product
        unit = self.find_or_create_unit(product.unit or "pcs")
        product.unit_id = unit.id
        product.unit = unit.code
        self._product_repo.save(product)
        return product

    def _resolve_categories(
        self, category_ids: List[str]
    ) -> tuple[List[str], List[str]]:
        requested = [cid for cid in (category_ids or []) if cid]
        if not requested:
            return [], []
        categories_by_id = self._categories_by_id()
        resolved_ids: List[str] = []
        for category_id in requested:
            if category_id not in categories_by_id:
                raise ValidationError("Category not found")
            if category_id not in resolved_ids:
                resolved_ids.append(category_id)
        paths = build_category_paths(resolved_ids, categories_by_id)
        return resolved_ids, paths

    def create_category(
        self,
        name: str,
        description: str = "",
        parent_id: Optional[str] = None,
    ) -> ProductCategory:
        name = name.strip()
        if not name:
            raise ValidationError("Category name is required")
        parent_id = normalize_parent_id(parent_id)
        categories_by_id = self._categories_by_id()
        validate_category_parent(None, parent_id, categories_by_id)
        if self._category_repo.find_by_parent_and_name(parent_id, name):
            raise ValidationError("A category with this name already exists under the parent")
        category = ProductCategory(
            name=name,
            description=description.strip(),
            parent_id=parent_id,
        )
        return self._category_repo.save(category)

    def update_category(
        self,
        category_id: str,
        name: str,
        description: str = "",
        is_active: bool = True,
        parent_id: Optional[str] = None,
    ) -> ProductCategory:
        category = self._category_repo.find_by_id(category_id)
        if not category:
            raise ValidationError("Category not found")
        name = name.strip()
        if not name:
            raise ValidationError("Category name is required")
        parent_id = normalize_parent_id(parent_id)
        categories_by_id = self._categories_by_id()
        validate_category_parent(category_id, parent_id, categories_by_id)
        existing = self._category_repo.find_by_parent_and_name(parent_id, name)
        if existing and existing.id != category_id:
            raise ValidationError("A category with this name already exists under the parent")
        category.update(
            name=name,
            description=description.strip(),
            is_active=is_active,
            parent_id=parent_id,
        )
        return self._category_repo.save(category)

    def delete_category(self, category_id: str) -> None:
        categories_by_id = self._categories_by_id()
        if self._category_repo.list_children(category_id):
            raise ValidationError("Cannot delete a category that has child categories")
        if self._product_repo.count_by_category(category_id) > 0:
            raise ValidationError("Cannot delete a category that has products")
        self._category_repo.delete(category_id)

    def list_field_definitions(self, active_only: bool = False) -> List[ProductFieldDefinition]:
        if not self._field_def_repo:
            return []
        return self._field_def_repo.list_all(active_only=active_only)

    def create_field_definition(
        self,
        key: str,
        label: str,
        field_type: ProductFieldType,
        *,
        options: Optional[List[str]] = None,
        required: bool = False,
        applies_to_category_ids: Optional[List[str]] = None,
        sort_order: int = 0,
    ) -> ProductFieldDefinition:
        if not self._field_def_repo:
            raise ValidationError("Custom field repository not configured")
        key = normalize_field_key(key)
        label = label.strip()
        if not key or not label:
            raise ValidationError("Field key and label are required")
        if self._field_def_repo.find_by_key(key):
            raise ValidationError("A custom field with this key already exists")
        definition = ProductFieldDefinition(
            key=key,
            label=label,
            field_type=field_type,
            options=list(options or []),
            required=required,
            applies_to_category_ids=list(applies_to_category_ids or []),
            sort_order=sort_order,
        )
        return self._field_def_repo.save(definition)

    def update_field_definition(
        self,
        definition_id: str,
        *,
        label: str,
        field_type: ProductFieldType,
        options: Optional[List[str]] = None,
        required: bool = False,
        applies_to_category_ids: Optional[List[str]] = None,
        sort_order: int = 0,
        is_active: bool = True,
    ) -> ProductFieldDefinition:
        if not self._field_def_repo:
            raise ValidationError("Custom field repository not configured")
        definition = self._field_def_repo.find_by_id(definition_id)
        if not definition:
            raise ValidationError("Custom field not found")
        label = label.strip()
        if not label:
            raise ValidationError("Field label is required")
        definition.update(
            label=label,
            field_type=field_type,
            options=list(options or []),
            required=required,
            applies_to_category_ids=list(applies_to_category_ids or []),
            sort_order=sort_order,
            is_active=is_active,
        )
        return self._field_def_repo.save(definition)

    def delete_field_definition(self, definition_id: str) -> None:
        if not self._field_def_repo:
            raise ValidationError("Custom field repository not configured")
        self._field_def_repo.delete(definition_id)

    def create_product(
        self,
        sku: str,
        name: str,
        category_ids: List[str],
        unit_id: str = "",
        unit_code: str = "",
        opening_qty: float = 0.0,
        *,
        hsn_sac: str = "",
        selling_rate: float = 0.0,
        mrp: float = 0.0,
        gst_rate: float = 0.0,
        gst_required: bool = False,
        specifications: Optional[Dict[str, str]] = None,
        custom_fields: Optional[Dict[str, Any]] = None,
    ) -> InventoryProduct:
        sku = sku.strip()
        name = name.strip()
        if not sku:
            raise ValidationError("SKU is required")
        if not name:
            raise ValidationError("Product name is required")
        if self._product_repo.find_by_sku(sku):
            raise ValidationError("A product with this SKU already exists")
        resolved_ids, paths = self._resolve_categories(category_ids)
        unit = self._resolve_unit(unit_id, unit_code)
        if not self._rate_history:
            raise ValidationError("Rate history is not configured")
        if gst_required and not (hsn_sac or "").strip():
            raise ValidationError("HSN code is required for registered businesses")
        opening_qty = round(max(opening_qty, 0.0), 2)
        specs = {
            k.strip(): str(v).strip()
            for k, v in (specifications or {}).items()
            if k and str(k).strip() and str(v).strip()
        }
        field_values = custom_fields or {}
        if self._field_def_repo:
            definitions = self._field_def_repo.list_all(active_only=True)
            field_values = validate_custom_field_values(
                definitions, field_values, resolved_ids
            )
        product = InventoryProduct(
            sku=sku,
            name=name,
            category_ids=resolved_ids,
            category_names=paths,
            unit_id=unit.id,
            unit=unit.code,
            hsn_sac=(hsn_sac or "").strip(),
            opening_qty=opening_qty,
            current_qty=0.0,
            specifications=specs,
            custom_fields=field_values,
        )
        product.sync_legacy_category_fields()
        saved = self._product_repo.save(product)
        self._rate_history.apply_form_changes(
            saved.id,
            selling_rate=selling_rate,
            mrp=mrp,
            gst_rate=gst_rate,
            is_new=True,
            gst_required=gst_required,
        )
        self._rate_history.hydrate_active_values(saved.id, saved)
        saved = self._product_repo.save(saved)
        if opening_qty > 0:
            self._record_movement(
                saved,
                StockMovementType.RECEIVE,
                opening_qty,
                date.today(),
                StockReferenceType.MANUAL,
                None,
                "Opening stock",
            )
        return saved

    def _resolve_unit(self, unit_id: str, unit_code: str = "") -> ProductUnit:
        if not self._unit_repo:
            raise ValidationError("Unit repository not configured")
        unit = None
        if unit_id:
            unit = self._unit_repo.find_by_id(unit_id)
        if not unit and unit_code:
            unit = self._unit_repo.find_by_code(unit_code)
        if not unit:
            raise ValidationError("Unit is required")
        return unit

    def update_product(
        self,
        product_id: str,
        sku: str,
        name: str,
        category_ids: List[str],
        unit_id: str,
        is_active: bool = True,
        *,
        hsn_sac: Optional[str] = None,
        selling_rate: Optional[float] = None,
        mrp: Optional[float] = None,
        gst_rate: Optional[float] = None,
        gst_required: bool = False,
        specifications: Optional[Dict[str, str]] = None,
        custom_fields: Optional[Dict[str, Any]] = None,
    ) -> InventoryProduct:
        product = self._product_repo.find_by_id(product_id)
        if not product:
            raise ValidationError("Product not found")
        if not self._rate_history:
            raise ValidationError("Rate history is not configured")
        resolved_ids, paths = self._resolve_categories(category_ids)
        sku = sku.strip()
        name = name.strip()
        if not sku or not name:
            raise ValidationError("SKU and product name are required")
        existing = self._product_repo.find_by_sku(sku)
        if existing and existing.id != product_id:
            raise ValidationError("A product with this SKU already exists")
        unit = self._resolve_unit(unit_id, "")
        if gst_required and hsn_sac is not None and not (hsn_sac or "").strip():
            raise ValidationError("HSN code is required for registered businesses")
        specs = product.specifications
        if specifications is not None:
            specs = {
                k.strip(): str(v).strip()
                for k, v in specifications.items()
                if k and str(k).strip() and str(v).strip()
            }
        field_values = product.custom_fields
        if custom_fields is not None:
            field_values = custom_fields
            if self._field_def_repo:
                definitions = self._field_def_repo.list_all(active_only=True)
                field_values = validate_custom_field_values(
                    definitions, field_values, resolved_ids
                )
        product.update(
            sku=sku,
            name=name,
            category_ids=resolved_ids,
            category_names=paths,
            unit_id=unit.id,
            unit=unit.code,
            is_active=is_active,
            specifications=specs,
            custom_fields=field_values,
        )
        if hsn_sac is not None:
            product.hsn_sac = (hsn_sac or "").strip()
        product.sync_legacy_category_fields()
        saved = self._product_repo.save(product)
        if selling_rate is not None and mrp is not None and gst_rate is not None:
            self._rate_history.apply_form_changes(
                saved.id,
                selling_rate=selling_rate,
                mrp=mrp,
                gst_rate=gst_rate,
                is_new=False,
                gst_required=gst_required,
            )
        self._rate_history.hydrate_active_values(saved.id, saved)
        return self._product_repo.save(saved)

    def record_manual_movement(
        self,
        product_id: str,
        movement_type: StockMovementType,
        qty: float,
        movement_date: date,
        notes: str = "",
    ) -> StockMovement:
        product = self._product_repo.find_by_id(product_id)
        if not product:
            raise ValidationError("Product not found")
        return self._record_movement(
            product,
            movement_type,
            qty,
            movement_date,
            StockReferenceType.MANUAL,
            None,
            notes,
        )

    def record_sale_movements(
        self,
        reference_id: str,
        lines: list[dict],
        reference_type: StockReferenceType = StockReferenceType.SALES_INVOICE,
        movement_date: Optional[date] = None,
    ) -> list[StockMovement]:
        recorded: list[StockMovement] = []
        md = movement_date or date.today()
        for line in lines:
            product_id = line.get("product_id")
            if not product_id:
                continue
            product = self._product_repo.find_by_id(str(product_id))
            if not product:
                raise ValidationError(f"Product not found for sale line")
            qty = float(line.get("qty") or line.get("qty_delivered") or 0)
            if qty <= 0:
                continue
            movement = self._record_movement(
                product,
                StockMovementType.SALE,
                qty,
                md,
                reference_type,
                reference_id,
                (line.get("description") or "").strip() or "Sale",
            )
            recorded.append(movement)
        return recorded

    def apply_delivery_note_issue(
        self,
        dn_id: str,
        lines: list[dict],
        movement_date: Optional[date] = None,
    ) -> list[StockMovement]:
        return self.record_sale_movements(
            dn_id,
            lines,
            StockReferenceType.DELIVERY_NOTE,
            movement_date,
        )

    def apply_sales_return(
        self,
        return_id: str,
        lines: list[dict],
        movement_date: Optional[date] = None,
    ) -> list[StockMovement]:
        recorded: list[StockMovement] = []
        md = movement_date or date.today()
        for line in lines:
            product_id = line.get("product_id")
            if not product_id:
                continue
            product = self._product_repo.find_by_id(str(product_id))
            if not product:
                raise ValidationError("Product not found for sales return")
            qty = float(line.get("qty") or 0)
            if qty <= 0:
                continue
            movement = self._record_movement(
                product,
                StockMovementType.SALES_RETURN,
                qty,
                md,
                StockReferenceType.SALES_RETURN,
                return_id,
                (line.get("description") or "").strip() or "Sales return",
            )
            recorded.append(movement)
        return recorded

    def apply_purchase_receive(
        self,
        lines: list[dict],
        reference_id: str,
        reference_type: StockReferenceType = StockReferenceType.GRN,
        movement_date: Optional[date] = None,
    ) -> list[StockMovement]:
        recorded: list[StockMovement] = []
        md = movement_date or date.today()
        for line in lines:
            product_id = line.get("product_id")
            if not product_id:
                continue
            product = self._product_repo.find_by_id(str(product_id))
            if not product:
                raise ValidationError("Product not found for purchase receive")
            qty = float(line.get("qty") or 0)
            if qty <= 0:
                continue
            movement = self._record_movement(
                product,
                StockMovementType.PURCHASE_RECEIVE,
                qty,
                md,
                reference_type,
                reference_id,
                (line.get("description") or "").strip() or "Purchase receive",
            )
            recorded.append(movement)
        return recorded

    def apply_purchase_return(
        self,
        return_id: str,
        lines: list[dict],
        movement_date: Optional[date] = None,
    ) -> list[StockMovement]:
        recorded: list[StockMovement] = []
        md = movement_date or date.today()
        for line in lines:
            product_id = line.get("product_id")
            if not product_id:
                continue
            product = self._product_repo.find_by_id(str(product_id))
            if not product:
                raise ValidationError("Product not found for purchase return")
            qty = float(line.get("qty") or 0)
            if qty <= 0:
                continue
            movement = self._record_movement(
                product,
                StockMovementType.PURCHASE_RETURN,
                qty,
                md,
                StockReferenceType.PURCHASE_RETURN,
                return_id,
                (line.get("description") or "").strip() or "Purchase return",
            )
            recorded.append(movement)
        return recorded

    def apply_landed_cost(self, lines: list[dict]) -> None:
        for line in lines:
            product_id = line.get("product_id")
            if not product_id:
                continue
            product = self._product_repo.find_by_id(str(product_id))
            if not product:
                continue
            qty = float(line.get("qty") or 0)
            unit_cost = float(line.get("unit_cost") or 0)
            if qty <= 0 or unit_cost < 0:
                continue
            old_qty = product.current_qty - qty
            if old_qty < 0:
                old_qty = 0.0
            old_wac = product.weighted_avg_cost
            if old_qty + qty <= 0:
                new_wac = unit_cost
            else:
                new_wac = round(
                    (old_qty * old_wac + qty * unit_cost) / (old_qty + qty), 4
                )
            product.weighted_avg_cost = new_wac
            product.last_purchase_rate = round(unit_cost, 4)
            self._product_repo.save(product)

    def reverse_movements_by_reference(self, reference_id: str) -> None:
        if not reference_id:
            return
        movements = self._movement_repo.list_by_reference(reference_id)
        for movement in movements:
            product = self._product_repo.find_by_id(movement.product_id)
            if not product:
                continue
            qty = round(float(movement.qty), 2)
            if movement.movement_type in INFLOW_TYPES:
                if product.current_qty < qty - 0.001:
                    raise ValidationError(
                        f"Cannot reverse receive for {product.name}: insufficient stock"
                    )
                product.current_qty = round(product.current_qty - qty, 2)
            else:
                product.current_qty = round(product.current_qty + qty, 2)
            self._product_repo.save(product)
            self._movement_repo.delete(movement.id)

    def get_product_ledger(self, product_id: str) -> list[dict[str, Any]]:
        product = self._product_repo.find_by_id(product_id)
        if not product:
            return []
        movements = sorted(
            self._movement_repo.list_by_product(product_id), key=_movement_sort_key
        )
        running = 0.0
        rows: list[dict[str, Any]] = []
        for movement in movements:
            qty_in = movement_qty_in(movement.movement_type, movement.qty)
            qty_out = movement_qty_out(movement.movement_type, movement.qty)
            running = round(running + qty_in - qty_out, 2)
            rows.append(self._ledger_row(movement, product, qty_in, qty_out, running))
        return rows

    def get_stock_ledger(self) -> list[dict[str, Any]]:
        products = {p.id: p for p in self._product_repo.list_all(active_only=False)}
        movements = sorted(self._movement_repo.list_all(), key=_movement_sort_key)
        rows: list[dict[str, Any]] = []
        for movement in movements:
            product = products.get(movement.product_id)
            if not product:
                continue
            qty_in = movement_qty_in(movement.movement_type, movement.qty)
            qty_out = movement_qty_out(movement.movement_type, movement.qty)
            rows.append(self._ledger_row(movement, product, qty_in, qty_out, None))
        return rows

    def _record_movement(
        self,
        product: InventoryProduct,
        movement_type: StockMovementType,
        qty: float,
        movement_date: date,
        reference_type: StockReferenceType,
        reference_id: Optional[str],
        notes: str,
    ) -> StockMovement:
        qty = round(float(qty), 2)
        if qty <= 0:
            raise ValidationError("Quantity must be positive")
        if movement_type not in INFLOW_TYPES and movement_type not in {
            StockMovementType.ISSUE,
            StockMovementType.ADJUST_OUT,
            StockMovementType.SALE,
            StockMovementType.PURCHASE_RETURN,
        }:
            raise ValidationError("Unsupported movement type")
        if movement_type in INFLOW_TYPES:
            product.current_qty = round(product.current_qty + qty, 2)
        else:
            if product.current_qty < qty - 0.001:
                raise ValidationError(
                    f"Insufficient stock for {product.name} "
                    f"(available {product.current_qty:g}, need {qty:g})"
                )
            product.current_qty = round(product.current_qty - qty, 2)
        self._product_repo.save(product)
        movement = StockMovement(
            product_id=product.id,
            movement_type=movement_type,
            qty=qty,
            movement_date=movement_date,
            reference_type=reference_type,
            reference_id=reference_id,
            notes=notes,
        )
        return self._movement_repo.save(movement)

    def _ledger_row(
        self,
        movement: StockMovement,
        product: InventoryProduct,
        qty_in: float,
        qty_out: float,
        balance: Optional[float],
    ) -> dict[str, Any]:
        md = movement.movement_date
        if isinstance(md, datetime):
            md = md.date()
        row = {
            "id": movement.id,
            "product_id": product.id,
            "product_name": product.name,
            "sku": product.sku,
            "category_id": product.category_id,
            "category_name": product.category_name,
            "movement_date": md,
            "movement_type": movement.movement_type.value,
            "qty_in": qty_in,
            "qty_out": qty_out,
            "reference_type": movement.reference_type.value,
            "reference_id": movement.reference_id or "",
            "notes": movement.notes,
        }
        if balance is not None:
            row["balance"] = balance
        return row
