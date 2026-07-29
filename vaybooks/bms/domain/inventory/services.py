from datetime import date, datetime
from typing import Any, Dict, List, Optional

from vaybooks.bms.domain.inventory.category_tree import (
    build_category_paths,
    normalize_parent_id,
    validate_category_parent,
)
from vaybooks.bms.domain.inventory.entities import (
    InventoryProduct,
    Location,
    ProductCategory,
    ProductUnit,
    StockBalance,
    StockMovement,
    StockTransfer,
    StockTransferLine,
    Warehouse,
)
from vaybooks.bms.domain.inventory.field_definitions import (
    ProductFieldDefinition,
    ProductFieldType,
    normalize_field_key,
    validate_custom_field_values,
)
from vaybooks.bms.domain.inventory.repository import (
    InventoryProductRepository,
    LocationRepository,
    ProductCategoryRepository,
    ProductFieldDefinitionRepository,
    ProductUnitRepository,
    StockBalanceRepository,
    StockMovementRepository,
    StockTransferRepository,
    WarehouseRepository,
)
from vaybooks.bms.domain.inventory.rate_history_service import ProductRateHistoryService
from vaybooks.bms.domain.inventory.units import default_unit_label, normalize_unit_code
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import (
    LocationType,
    StockMovementType,
    StockReferenceType,
    StockTransferStatus,
)
from vaybooks.bms.domain.shared.exceptions import ValidationError

INFLOW_TYPES = frozenset(
    {
        StockMovementType.RECEIVE,
        StockMovementType.ADJUST_IN,
        StockMovementType.PURCHASE_RECEIVE,
        StockMovementType.SALES_RETURN,
        StockMovementType.TRANSFER_IN,
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
        warehouse_repo: Optional[WarehouseRepository] = None,
        location_repo: Optional[LocationRepository] = None,
        balance_repo: Optional[StockBalanceRepository] = None,
        transfer_repo: Optional[StockTransferRepository] = None,
    ):
        self._category_repo = category_repo
        self._product_repo = product_repo
        self._movement_repo = movement_repo
        self._unit_repo = unit_repo
        self._field_def_repo = field_def_repo
        self._rate_history = rate_history
        self._location_repo = location_repo or warehouse_repo
        self._warehouse_repo = self._location_repo
        self._balance_repo = balance_repo
        self._transfer_repo = transfer_repo

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

    def list_locations(
        self,
        active_only: bool = True,
        location_type: Optional[LocationType] = None,
    ) -> List[Location]:
        if not self._location_repo:
            return []
        return self._location_repo.list_all(
            active_only=active_only, location_type=location_type
        )

    def get_location(self, location_id: str) -> Optional[Location]:
        if not self._location_repo or not location_id:
            return None
        return self._location_repo.find_by_id(location_id)

    def create_location(
        self,
        code: str,
        name: str,
        address: str = "",
        location_type: LocationType = LocationType.WAREHOUSE,
    ) -> Location:
        if not self._location_repo:
            raise ValidationError("Location repository not configured")
        code = (code or "").strip().upper()
        name = (name or "").strip()
        if not code:
            raise ValidationError("Location code is required")
        if not name:
            raise ValidationError("Location name is required")
        if self._location_repo.find_by_code(code):
            raise ValidationError("A location with this code already exists")
        location = Location(
            code=code,
            name=name,
            address=(address or "").strip(),
            location_type=location_type or LocationType.WAREHOUSE,
        )
        return self._location_repo.save(location)

    def update_location(
        self,
        location_id: str,
        code: str,
        name: str,
        address: str = "",
        is_active: bool = True,
        location_type: Optional[LocationType] = None,
    ) -> Location:
        if not self._location_repo:
            raise ValidationError("Location repository not configured")
        location = self._location_repo.find_by_id(location_id)
        if not location:
            raise ValidationError("Location not found")
        code = (code or "").strip().upper()
        name = (name or "").strip()
        if not code:
            raise ValidationError("Location code is required")
        if not name:
            raise ValidationError("Location name is required")
        existing = self._location_repo.find_by_code(code)
        if existing and existing.id != location_id:
            raise ValidationError("A location with this code already exists")
        updates = {
            "code": code,
            "name": name,
            "address": (address or "").strip(),
            "is_active": is_active,
        }
        if location_type is not None:
            updates["location_type"] = location_type
        location.update(**updates)
        return self._location_repo.save(location)

    def delete_location(self, location_id: str) -> None:
        if not self._location_repo:
            raise ValidationError("Location repository not configured")
        location = self._location_repo.find_by_id(location_id)
        if not location:
            raise ValidationError("Location not found")
        self._location_repo.delete(location_id)

    def list_warehouses(self, active_only: bool = True) -> List[Warehouse]:
        return self.list_locations(active_only=active_only)

    def get_warehouse(self, warehouse_id: str) -> Optional[Warehouse]:
        return self.get_location(warehouse_id)

    def create_warehouse(
        self,
        code: str,
        name: str,
        address: str = "",
        location_type: LocationType = LocationType.WAREHOUSE,
    ) -> Warehouse:
        return self.create_location(code, name, address, location_type=location_type)

    def update_warehouse(
        self,
        warehouse_id: str,
        code: str,
        name: str,
        address: str = "",
        is_active: bool = True,
        location_type: Optional[LocationType] = None,
    ) -> Warehouse:
        return self.update_location(
            warehouse_id,
            code,
            name,
            address,
            is_active,
            location_type=location_type,
        )

    def delete_warehouse(self, warehouse_id: str) -> None:
        self.delete_location(warehouse_id)

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
        track_batch: bool = False,
        track_serial: bool = False,
        location_id: str = "",
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
        opening_location_id = (location_id or "").strip()
        if opening_qty > 0 and not opening_location_id:
            raise ValidationError("Location is required for opening stock")
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
            track_batch=bool(track_batch),
            track_serial=bool(track_serial),
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
                location_id=opening_location_id,
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
        track_batch: Optional[bool] = None,
        track_serial: Optional[bool] = None,
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
        was_active = bool(product.is_active)
        has_stock = float(product.current_qty or 0) > 0.001 or any(
            float(bal.qty or 0) > 0.001
            for bal in self.list_balances_by_product(product_id)
        )
        if not is_active and (was_active or has_stock):
            self._clear_stock_on_discontinue(product)
            product = self._product_repo.find_by_id(product_id)
            if not product:
                raise ValidationError("Product not found")
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
        if track_batch is not None:
            product.track_batch = bool(track_batch)
        if track_serial is not None:
            product.track_serial = bool(track_serial)
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

    def discontinue_product(self, product_id: str) -> InventoryProduct:
        """Deactivate a product and clear remaining stock with ADJUST_OUT movements."""
        product = self._product_repo.find_by_id(product_id)
        if not product:
            raise ValidationError("Product not found")
        if not product.is_active and float(product.current_qty or 0) <= 0.001:
            return product
        self._clear_stock_on_discontinue(product)
        product = self._product_repo.find_by_id(product_id)
        if not product:
            raise ValidationError("Product not found")
        product.update(is_active=False)
        return self._product_repo.save(product)

    def _fallback_location_id_for_clear(self, product_id: str) -> Optional[str]:
        balances = self.list_balances_by_product(product_id)
        if balances:
            return balances[0].location_id
        for active_only in (True, False):
            locations = self.list_locations(active_only=active_only)
            if locations:
                return locations[0].id
        return None

    def _clear_stock_on_discontinue(self, product: InventoryProduct) -> InventoryProduct:
        """Zero on-hand qty via ADJUST_OUT per location; leave an audit trail."""
        product_id = product.id
        notes = "Stock cleared on discontinue"
        md = date.today()
        balances = [
            bal
            for bal in self.list_balances_by_product(product_id)
            if float(bal.qty or 0) > 0.001
        ]
        for bal in balances:
            product = self._product_repo.find_by_id(product_id)
            if not product:
                raise ValidationError("Product not found")
            available = min(
                float(bal.qty or 0),
                self.get_stock_balance(product_id, bal.location_id),
                float(product.current_qty or 0),
            )
            qty = round(available, 2)
            if qty <= 0.001:
                continue
            self._record_movement(
                product,
                StockMovementType.ADJUST_OUT,
                qty,
                md,
                StockReferenceType.MANUAL,
                None,
                notes,
                location_id=bal.location_id,
            )

        product = self._product_repo.find_by_id(product_id)
        if not product:
            raise ValidationError("Product not found")
        residual = round(float(product.current_qty or 0), 2)
        if residual > 0.001:
            loc_id = self._fallback_location_id_for_clear(product_id)
            if not loc_id:
                raise ValidationError(
                    "Cannot discontinue: stock remains but no location is available "
                    "to clear it"
                )
            loc_qty = self.get_stock_balance(product_id, loc_id)
            if loc_qty + 0.001 < residual:
                self._apply_balance_delta(product_id, loc_id, residual - loc_qty)
            self._record_movement(
                product,
                StockMovementType.ADJUST_OUT,
                residual,
                md,
                StockReferenceType.MANUAL,
                None,
                notes,
                location_id=loc_id,
            )
            product = self._product_repo.find_by_id(product_id)
            if not product:
                raise ValidationError("Product not found")
        return product

    def record_manual_movement(
        self,
        product_id: str,
        movement_type: StockMovementType,
        qty: float,
        movement_date: date,
        notes: str = "",
        location_id: Optional[str] = None,
    ) -> StockMovement:
        product = self._product_repo.find_by_id(product_id)
        if not product:
            raise ValidationError("Product not found")
        loc = (location_id or "").strip() or None
        return self._record_movement(
            product,
            movement_type,
            qty,
            movement_date,
            StockReferenceType.MANUAL,
            None,
            notes,
            location_id=loc,
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
            loc = (
                str(line.get("location_id") or line.get("warehouse_id") or "").strip()
                or None
            )
            movement = self._record_movement(
                product,
                StockMovementType.SALE,
                qty,
                md,
                reference_type,
                reference_id,
                (line.get("description") or "").strip() or "Sale",
                location_id=loc,
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
            loc = (
                str(line.get("location_id") or line.get("warehouse_id") or "").strip()
                or None
            )
            movement = self._record_movement(
                product,
                StockMovementType.SALES_RETURN,
                qty,
                md,
                StockReferenceType.SALES_RETURN,
                return_id,
                (line.get("description") or "").strip() or "Sales return",
                location_id=loc,
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
                location_id=str(
                    line.get("location_id") or line.get("warehouse_id") or ""
                )
                or None,
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
                location_id=str(
                    line.get("location_id") or line.get("warehouse_id") or ""
                )
                or None,
            )
            recorded.append(movement)
        return recorded

    def apply_production_issue(
        self,
        batch_id: str,
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
                raise ValidationError("Product not found for production issue")
            qty = float(line.get("qty") or 0)
            if qty <= 0:
                continue
            recorded.append(
                self._record_movement(
                    product,
                    StockMovementType.ISSUE,
                    qty,
                    md,
                    StockReferenceType.PRODUCTION_BATCH,
                    batch_id,
                    (line.get("description") or "").strip()
                    or "Production material issue",
                    location_id=str(
                        line.get("location_id") or line.get("warehouse_id") or ""
                    )
                    or None,
                )
            )
        return recorded

    def apply_production_receive(
        self,
        batch_id: str,
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
                raise ValidationError("Product not found for production receipt")
            qty = float(line.get("qty") or 0)
            if qty <= 0:
                continue
            recorded.append(
                self._record_movement(
                    product,
                    StockMovementType.RECEIVE,
                    qty,
                    md,
                    StockReferenceType.PRODUCTION_BATCH,
                    batch_id,
                    (line.get("description") or "").strip()
                    or "Production output receipt",
                    location_id=str(
                        line.get("location_id") or line.get("warehouse_id") or ""
                    )
                    or None,
                )
            )
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
                self._apply_balance_delta(
                    product.id, movement.location_id, -qty
                )
            else:
                product.current_qty = round(product.current_qty + qty, 2)
                self._apply_balance_delta(
                    product.id, movement.location_id, qty
                )
            self._product_repo.save(product)
            self._movement_repo.delete(movement.id)

    def get_stock_balance(
        self, product_id: str, location_id: str
    ) -> float:
        if not self._balance_repo or not product_id or not location_id:
            return 0.0
        bal = self._balance_repo.get(product_id, location_id)
        return float(bal.qty) if bal else 0.0

    def list_balances_by_product(self, product_id: str) -> List[StockBalance]:
        if not self._balance_repo or not product_id:
            return []
        return self._balance_repo.list_by_product(product_id)

    def list_balances_by_location(self, location_id: str) -> List[StockBalance]:
        if not self._balance_repo or not location_id:
            return []
        return self._balance_repo.list_by_location(location_id)

    def on_hand_by_location(self) -> list[dict[str, Any]]:
        if not self._balance_repo:
            return []
        products = {p.id: p for p in self._product_repo.list_all(active_only=False)}
        locations = {
            loc.id: loc for loc in self.list_locations(active_only=False)
        }
        rows: list[dict[str, Any]] = []
        for bal in self._balance_repo.list_all():
            product = products.get(bal.product_id)
            location = locations.get(bal.location_id)
            if not product:
                continue
            rows.append(
                {
                    "product_id": bal.product_id,
                    "product_name": product.name,
                    "sku": product.sku,
                    "location_id": bal.location_id,
                    "location_name": location.name if location else "Unassigned",
                    "location_type": (
                        location.location_type.value if location else ""
                    ),
                    "qty": bal.qty,
                    "unit": product.unit,
                    "stock_value": round(
                        bal.qty * float(product.selling_rate or 0), 2
                    ),
                    "valuation": round(
                        bal.qty * float(product.weighted_avg_cost or 0), 2
                    ),
                }
            )
        return rows

    def _apply_balance_delta(
        self,
        product_id: str,
        location_id: Optional[str],
        delta: float,
    ) -> None:
        if not self._balance_repo or not location_id or abs(delta) < 0.0001:
            return
        bal = self._balance_repo.get(product_id, location_id)
        if bal:
            bal.qty = round(bal.qty + delta, 2)
            bal.updated_at = utc_now()
        else:
            bal = StockBalance(
                product_id=product_id,
                location_id=location_id,
                qty=round(delta, 2),
            )
        self._balance_repo.save(bal)

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
        locations = {
            loc.id: loc for loc in self.list_locations(active_only=False)
        }
        movements = sorted(self._movement_repo.list_all(), key=_movement_sort_key)
        rows: list[dict[str, Any]] = []
        for movement in movements:
            product = products.get(movement.product_id)
            if not product:
                continue
            qty_in = movement_qty_in(movement.movement_type, movement.qty)
            qty_out = movement_qty_out(movement.movement_type, movement.qty)
            row = self._ledger_row(movement, product, qty_in, qty_out, None)
            loc = locations.get(movement.location_id or "")
            row["location_name"] = loc.name if loc else (
                "Unassigned" if not movement.location_id else movement.location_id
            )
            rows.append(row)
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
        location_id: Optional[str] = None,
        warehouse_id: Optional[str] = None,
    ) -> StockMovement:
        qty = round(float(qty), 2)
        if qty <= 0:
            raise ValidationError("Quantity must be positive")
        if movement_type not in INFLOW_TYPES and movement_type not in {
            StockMovementType.ISSUE,
            StockMovementType.ADJUST_OUT,
            StockMovementType.SALE,
            StockMovementType.PURCHASE_RETURN,
            StockMovementType.TRANSFER_OUT,
        }:
            raise ValidationError("Unsupported movement type")
        loc = (location_id or warehouse_id or "").strip() or None
        if not loc:
            raise ValidationError("Location is required for stock movements")
        if movement_type in INFLOW_TYPES:
            product.current_qty = round(product.current_qty + qty, 2)
            self._apply_balance_delta(product.id, loc, qty)
        else:
            if movement_type == StockMovementType.TRANSFER_OUT and self._balance_repo is not None:
                bal = self._balance_repo.get(product.id, loc) if loc else None
                available = float(bal.qty) if bal is not None else 0.0
                if available < qty - 0.001:
                    raise ValidationError(
                        f"Insufficient stock at location for {product.name} "
                        f"(available {available:g}, need {qty:g})"
                    )
            elif product.current_qty < qty - 0.001:
                raise ValidationError(
                    f"Insufficient stock for {product.name} "
                    f"(available {product.current_qty:g}, need {qty:g})"
                )
            product.current_qty = round(product.current_qty - qty, 2)
            self._apply_balance_delta(product.id, loc, -qty)
        self._product_repo.save(product)
        movement = StockMovement(
            product_id=product.id,
            movement_type=movement_type,
            qty=qty,
            movement_date=movement_date,
            reference_type=reference_type,
            reference_id=reference_id,
            location_id=loc,
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
            "location_id": movement.location_id or "",
            "notes": movement.notes,
        }
        if balance is not None:
            row["balance"] = balance
        return row

    def create_stock_transfer(
        self,
        transfer_number: str,
        from_location_id: str,
        to_location_id: str,
        transfer_date: date,
        lines: list[dict],
        notes: str = "",
        *,
        allowed_location_ids: list[str] | None = None,
        send_in_transit: bool = False,
    ) -> StockTransfer:
        if not self._transfer_repo:
            raise ValidationError("Transfer repository not configured")
        from_loc = self.get_location(from_location_id)
        to_loc = self.get_location(to_location_id)
        if not from_loc or not from_loc.is_active:
            raise ValidationError("Source location not found or inactive")
        if not to_loc or not to_loc.is_active:
            raise ValidationError("Destination location not found or inactive")
        if from_location_id == to_location_id:
            raise ValidationError("Source and destination must differ")
        if allowed_location_ids is not None:
            allowed = {str(i).strip() for i in allowed_location_ids if str(i).strip()}
            if from_loc.id not in allowed or to_loc.id not in allowed:
                raise ValidationError(
                    "You can only transfer stock between locations you have access to."
                )
        if not lines:
            raise ValidationError("At least one transfer line is required")
        transfer_lines: List[StockTransferLine] = []
        for raw in lines:
            qty = float(raw.get("qty") or 0)
            if qty <= 0:
                raise ValidationError("Transfer quantity must be positive")
            transfer_lines.append(
                StockTransferLine(
                    product_id=str(raw.get("product_id") or ""),
                    product_name=(raw.get("product_name") or "").strip(),
                    qty=round(qty, 2),
                )
            )
        transfer = StockTransfer(
            transfer_number=transfer_number,
            from_location_id=from_loc.id,
            from_location_name=from_loc.name,
            to_location_id=to_loc.id,
            to_location_name=to_loc.name,
            transfer_date=transfer_date,
            lines=transfer_lines,
            notes=(notes or "").strip(),
            status=StockTransferStatus.DRAFT,
        )
        transfer = self._transfer_repo.save(transfer)
        if send_in_transit:
            transfer = self.dispatch_stock_transfer(
                transfer.id, allowed_location_ids=allowed_location_ids
            )
        return transfer

    def dispatch_stock_transfer(
        self,
        transfer_id: str,
        *,
        allowed_location_ids: list[str] | None = None,
    ) -> StockTransfer:
        if not self._transfer_repo:
            raise ValidationError("Transfer repository not configured")
        transfer = self._transfer_repo.find_by_id(transfer_id)
        if not transfer:
            raise ValidationError("Stock transfer not found")
        if transfer.status != StockTransferStatus.DRAFT:
            raise ValidationError("Only draft transfers can be sent in transit")
        if allowed_location_ids is not None:
            allowed = {str(i).strip() for i in allowed_location_ids if str(i).strip()}
            if (
                transfer.from_location_id not in allowed
                or transfer.to_location_id not in allowed
            ):
                raise ValidationError(
                    "You can only transfer stock between locations you have access to."
                )
        for line in transfer.lines:
            product = self._product_repo.find_by_id(line.product_id)
            if not product:
                raise ValidationError(
                    f"Product not found for transfer line {line.product_name or line.product_id}"
                )
            self._record_movement(
                product,
                StockMovementType.TRANSFER_OUT,
                line.qty,
                transfer.transfer_date,
                StockReferenceType.STOCK_TRANSFER,
                transfer.id,
                f"In transit to {transfer.to_location_name}",
                location_id=transfer.from_location_id,
            )
        transfer.status = StockTransferStatus.IN_TRANSIT
        transfer.updated_at = utc_now()
        return self._transfer_repo.save(transfer)

    def receive_stock_transfer(
        self,
        transfer_id: str,
        *,
        allowed_location_ids: list[str] | None = None,
    ) -> StockTransfer:
        if not self._transfer_repo:
            raise ValidationError("Transfer repository not configured")
        transfer = self._transfer_repo.find_by_id(transfer_id)
        if not transfer:
            raise ValidationError("Stock transfer not found")
        if transfer.status != StockTransferStatus.IN_TRANSIT:
            raise ValidationError("Only in-transit transfers can be received")
        if allowed_location_ids is not None:
            allowed = {str(i).strip() for i in allowed_location_ids if str(i).strip()}
            # Receiver must have access to destination (and typically source).
            if transfer.to_location_id not in allowed:
                raise ValidationError(
                    "You can only receive transfers at locations you have access to."
                )
        for line in transfer.lines:
            product = self._product_repo.find_by_id(line.product_id)
            if not product:
                raise ValidationError(
                    f"Product not found for transfer line {line.product_name or line.product_id}"
                )
            self._record_movement(
                product,
                StockMovementType.TRANSFER_IN,
                line.qty,
                transfer.transfer_date,
                StockReferenceType.STOCK_TRANSFER,
                transfer.id,
                f"Received from {transfer.from_location_name}",
                location_id=transfer.to_location_id,
            )
        transfer.status = StockTransferStatus.RECEIVED
        transfer.updated_at = utc_now()
        return self._transfer_repo.save(transfer)

    def cancel_stock_transfer(self, transfer_id: str) -> StockTransfer:
        if not self._transfer_repo:
            raise ValidationError("Transfer repository not configured")
        transfer = self._transfer_repo.find_by_id(transfer_id)
        if not transfer:
            raise ValidationError("Stock transfer not found")
        if transfer.status == StockTransferStatus.RECEIVED:
            raise ValidationError("Cannot cancel a received transfer")
        if transfer.status == StockTransferStatus.IN_TRANSIT:
            self.reverse_movements_by_reference(transfer.id)
        transfer.status = StockTransferStatus.CANCELLED
        transfer.updated_at = utc_now()
        return self._transfer_repo.save(transfer)

    def list_stock_transfers(self) -> List[StockTransfer]:
        if not self._transfer_repo:
            return []
        return self._transfer_repo.list_all()

    def get_stock_transfer(self, transfer_id: str) -> Optional[StockTransfer]:
        if not self._transfer_repo or not transfer_id:
            return None
        return self._transfer_repo.find_by_id(transfer_id)
