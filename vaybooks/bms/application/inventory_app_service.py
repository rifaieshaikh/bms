from datetime import date
from typing import Any, List, Optional

from vaybooks.bms.domain.inventory.entities import InventoryProduct, ProductCategory
from vaybooks.bms.domain.inventory.repository import (
    InventoryProductRepository,
    ProductCategoryRepository,
    StockMovementRepository,
)
from vaybooks.bms.domain.inventory.services import InventoryDomainService
from vaybooks.bms.domain.shared.enums import StockMovementType


class InventoryAppService:
    def __init__(
        self,
        category_repo: ProductCategoryRepository,
        product_repo: InventoryProductRepository,
        movement_repo: StockMovementRepository,
    ):
        self._domain = InventoryDomainService(
            category_repo, product_repo, movement_repo
        )
        self._product_repo = product_repo
        self._category_repo = category_repo

    def list_categories(self, active_only: bool = False) -> List[ProductCategory]:
        return self._category_repo.list_all(active_only=active_only)

    def get_category(self, category_id: str) -> Optional[ProductCategory]:
        return self._category_repo.find_by_id(category_id)

    def create_category(self, name: str, description: str = "") -> ProductCategory:
        return self._domain.create_category(name, description)

    def update_category(
        self, category_id: str, name: str, description: str = "", is_active: bool = True
    ) -> ProductCategory:
        return self._domain.update_category(category_id, name, description, is_active)

    def delete_category(self, category_id: str) -> None:
        self._domain.delete_category(category_id)

    def list_products(self, active_only: bool = False) -> List[InventoryProduct]:
        return self._product_repo.list_all(active_only=active_only)

    def search_products(self, query: str) -> List[InventoryProduct]:
        return self._product_repo.search(query)

    def get_product(self, product_id: str) -> Optional[InventoryProduct]:
        return self._product_repo.find_by_id(product_id)

    def create_product(
        self,
        sku: str,
        name: str,
        category_id: str,
        unit: str = "pcs",
        selling_rate: float = 0.0,
        opening_qty: float = 0.0,
    ) -> InventoryProduct:
        return self._domain.create_product(
            sku, name, category_id, unit, selling_rate, opening_qty
        )

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
        return self._domain.update_product(
            product_id, sku, name, category_id, unit, selling_rate, is_active
        )

    def get_stock_on_hand(self) -> List[InventoryProduct]:
        return self._product_repo.list_all(active_only=False)

    def record_manual_movement(
        self,
        product_id: str,
        movement_type: StockMovementType,
        qty: float,
        movement_date: date,
        notes: str = "",
    ):
        return self._domain.record_manual_movement(
            product_id, movement_type, qty, movement_date, notes
        )

    def get_product_ledger(self, product_id: str) -> List[dict[str, Any]]:
        return self._domain.get_product_ledger(product_id)

    def get_stock_ledger(self) -> List[dict[str, Any]]:
        return self._domain.get_stock_ledger()

    def apply_sales_movements(self, voucher_id: str, line_items: list[dict]):
        return self._domain.record_sale_movements(voucher_id, line_items)

    def apply_purchase_receive(
        self, vendor_id: str, lines: list[dict], reference_id: str
    ):
        return self._domain.apply_purchase_receive(vendor_id, lines, reference_id)
