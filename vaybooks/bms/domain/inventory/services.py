from datetime import date, datetime
from typing import Any, Optional

from vaybooks.bms.domain.inventory.entities import (
    InventoryProduct,
    ProductCategory,
    StockMovement,
)
from vaybooks.bms.domain.inventory.repository import (
    InventoryProductRepository,
    ProductCategoryRepository,
    StockMovementRepository,
)
from vaybooks.bms.domain.shared.enums import StockMovementType, StockReferenceType
from vaybooks.bms.domain.shared.exceptions import ValidationError

INFLOW_TYPES = frozenset(
    {
        StockMovementType.RECEIVE,
        StockMovementType.ADJUST_IN,
        StockMovementType.PURCHASE_RECEIVE,
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
    ):
        self._category_repo = category_repo
        self._product_repo = product_repo
        self._movement_repo = movement_repo

    def create_category(self, name: str, description: str = "") -> ProductCategory:
        name = name.strip()
        if not name:
            raise ValidationError("Category name is required")
        if self._category_repo.find_by_name(name):
            raise ValidationError("A category with this name already exists")
        category = ProductCategory(name=name, description=description.strip())
        return self._category_repo.save(category)

    def update_category(
        self, category_id: str, name: str, description: str = "", is_active: bool = True
    ) -> ProductCategory:
        category = self._category_repo.find_by_id(category_id)
        if not category:
            raise ValidationError("Category not found")
        name = name.strip()
        if not name:
            raise ValidationError("Category name is required")
        existing = self._category_repo.find_by_name(name)
        if existing and existing.id != category_id:
            raise ValidationError("A category with this name already exists")
        category.update(name=name, description=description.strip(), is_active=is_active)
        return self._category_repo.save(category)

    def delete_category(self, category_id: str) -> None:
        if self._product_repo.count_by_category(category_id) > 0:
            raise ValidationError("Cannot delete a category that has products")
        self._category_repo.delete(category_id)

    def create_product(
        self,
        sku: str,
        name: str,
        category_id: str,
        unit: str = "pcs",
        selling_rate: float = 0.0,
        opening_qty: float = 0.0,
    ) -> InventoryProduct:
        sku = sku.strip()
        name = name.strip()
        if not sku:
            raise ValidationError("SKU is required")
        if not name:
            raise ValidationError("Product name is required")
        category = self._category_repo.find_by_id(category_id)
        if not category:
            raise ValidationError("Category not found")
        if self._product_repo.find_by_sku(sku):
            raise ValidationError("A product with this SKU already exists")
        opening_qty = round(max(opening_qty, 0.0), 2)
        product = InventoryProduct(
            sku=sku,
            name=name,
            category_id=category.id,
            category_name=category.name,
            unit=(unit or "pcs").strip(),
            selling_rate=round(max(selling_rate, 0.0), 2),
            opening_qty=opening_qty,
            current_qty=0.0,
        )
        saved = self._product_repo.save(product)
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

    def update_product(
        self,
        product_id: str,
        sku: str,
        name: str,
        category_id: str,
        unit: str,
        selling_rate: float,
        is_active: bool = True,
    ) -> InventoryProduct:
        product = self._product_repo.find_by_id(product_id)
        if not product:
            raise ValidationError("Product not found")
        category = self._category_repo.find_by_id(category_id)
        if not category:
            raise ValidationError("Category not found")
        sku = sku.strip()
        name = name.strip()
        if not sku or not name:
            raise ValidationError("SKU and product name are required")
        existing = self._product_repo.find_by_sku(sku)
        if existing and existing.id != product_id:
            raise ValidationError("A product with this SKU already exists")
        product.update(
            sku=sku,
            name=name,
            category_id=category.id,
            category_name=category.name,
            unit=(unit or "pcs").strip(),
            selling_rate=round(max(selling_rate, 0.0), 2),
            is_active=is_active,
        )
        return self._product_repo.save(product)

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
        self, voucher_id: str, lines: list[dict]
    ) -> list[StockMovement]:
        recorded: list[StockMovement] = []
        for line in lines:
            product_id = line.get("product_id")
            if not product_id:
                continue
            product = self._product_repo.find_by_id(str(product_id))
            if not product:
                raise ValidationError(f"Product not found for sale line")
            qty = float(line.get("qty") or 0)
            if qty <= 0:
                continue
            movement = self._record_movement(
                product,
                StockMovementType.SALE,
                qty,
                date.today(),
                StockReferenceType.SALES_INVOICE,
                voucher_id,
                (line.get("description") or "").strip() or "Sale",
            )
            recorded.append(movement)
        return recorded

    def apply_purchase_receive(
        self,
        vendor_id: str,
        lines: list[dict],
        reference_id: str,
    ) -> list[StockMovement]:
        raise NotImplementedError(
            "Vendor purchase receive is not implemented yet; hook reserved for future use."
        )

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
