from datetime import date
from typing import Any, Dict, List, Optional, Union

from vaybooks.bms.domain.inventory.category_tree import build_category_path
from vaybooks.bms.domain.inventory.entities import (
    InventoryProduct,
    ProductCategory,
    ProductUnit,
)
from vaybooks.bms.domain.inventory.field_definitions import ProductFieldDefinition, ProductFieldType
from vaybooks.bms.domain.inventory.rate_history import ProductRatePeriod
from vaybooks.bms.domain.inventory.rate_history_service import ProductRateHistoryService
from vaybooks.bms.domain.inventory.repository import (
    InventoryProductRepository,
    ProductCategoryRepository,
    ProductFieldDefinitionRepository,
    ProductUnitRepository,
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
        unit_repo: Optional[ProductUnitRepository] = None,
        field_def_repo: Optional[ProductFieldDefinitionRepository] = None,
        rate_history: Optional[ProductRateHistoryService] = None,
    ):
        self._rate_history = rate_history
        self._domain = InventoryDomainService(
            category_repo,
            product_repo,
            movement_repo,
            unit_repo,
            field_def_repo,
            rate_history,
        )
        self._product_repo = product_repo
        self._category_repo = category_repo
        self._unit_repo = unit_repo
        self._field_def_repo = field_def_repo

    def _hydrate_product(self, product: Optional[InventoryProduct]) -> Optional[InventoryProduct]:
        if not product:
            return None
        product = self._domain.resolve_unit_for_product(product)
        if self._rate_history:
            self._rate_history.hydrate_active_values(product.id, product)
        return product

    def list_units(self, active_only: bool = True) -> List[ProductUnit]:
        return self._domain.list_units(active_only=active_only)

    def search_units(
        self, query: str = "", *, active_only: bool = True, limit: int = 10
    ) -> List[ProductUnit]:
        if not self._unit_repo:
            return []
        return self._unit_repo.search(query, active_only=active_only, limit=limit)

    def get_unit(self, unit_id: str) -> Optional[ProductUnit]:
        if not self._unit_repo or not unit_id:
            return None
        return self._unit_repo.find_by_id(unit_id)

    def find_or_create_unit(self, code: str, label: str = "") -> ProductUnit:
        return self._domain.find_or_create_unit(code, label)

    def update_unit(self, unit_id: str, label: str, is_active: bool = True) -> ProductUnit:
        return self._domain.update_unit(unit_id, label, is_active)

    def get_category_path(self, category_id: str) -> str:
        paths = self.category_paths_for([category_id])
        return paths.get(category_id, "")

    def category_paths_for(self, category_ids: List[str]) -> Dict[str, str]:
        ids = [cid for cid in category_ids if cid]
        if not ids:
            return {}
        by_id: Dict[str, ProductCategory] = {
            c.id: c for c in self._category_repo.find_by_ids(ids)
        }
        missing = {
            c.parent_id
            for c in by_id.values()
            if c.parent_id and c.parent_id not in by_id
        }
        while missing:
            parents = self._category_repo.find_by_ids(list(missing))
            missing = set()
            for parent in parents:
                by_id[parent.id] = parent
                if parent.parent_id and parent.parent_id not in by_id:
                    missing.add(parent.parent_id)
        return {cid: build_category_path(cid, by_id) for cid in ids if cid in by_id}

    def list_categories(self, active_only: bool = False) -> List[ProductCategory]:
        return self._category_repo.list_all(active_only=active_only)

    def search_categories(
        self, query: str = "", *, active_only: bool = True, limit: int = 10
    ) -> List[ProductCategory]:
        return self._category_repo.search(query, active_only=active_only, limit=limit)

    def get_category(self, category_id: str) -> Optional[ProductCategory]:
        return self._category_repo.find_by_id(category_id)

    def create_category(
        self,
        name: str,
        description: str = "",
        parent_id: Optional[str] = None,
    ) -> ProductCategory:
        return self._domain.create_category(name, description, parent_id)

    def update_category(
        self,
        category_id: str,
        name: str,
        description: str = "",
        is_active: bool = True,
        parent_id: Optional[str] = None,
    ) -> ProductCategory:
        return self._domain.update_category(
            category_id, name, description, is_active, parent_id
        )

    def delete_category(self, category_id: str) -> None:
        self._domain.delete_category(category_id)

    def count_products_in_category(self, category_id: str) -> int:
        return self._product_repo.count_by_category(category_id)

    def list_field_definitions(self, active_only: bool = False) -> List[ProductFieldDefinition]:
        return self._domain.list_field_definitions(active_only=active_only)

    def create_field_definition(
        self,
        key: str,
        label: str,
        field_type: ProductFieldType,
        **kwargs,
    ) -> ProductFieldDefinition:
        return self._domain.create_field_definition(key, label, field_type, **kwargs)

    def update_field_definition(
        self, definition_id: str, **kwargs
    ) -> ProductFieldDefinition:
        return self._domain.update_field_definition(definition_id, **kwargs)

    def delete_field_definition(self, definition_id: str) -> None:
        self._domain.delete_field_definition(definition_id)

    def list_products(self, active_only: bool = False) -> List[InventoryProduct]:
        products = self._product_repo.list_all(active_only=active_only)
        return [self._hydrate_product(p) for p in products if p]

    def search_products(self, query: str) -> List[InventoryProduct]:
        return [
            self._hydrate_product(p)
            for p in self._product_repo.search(query)
            if p
        ]

    def get_product(self, product_id: str) -> Optional[InventoryProduct]:
        return self._hydrate_product(self._product_repo.find_by_id(product_id))

    def find_product_by_sku(self, sku: str) -> Optional[InventoryProduct]:
        return self._hydrate_product(self._product_repo.find_by_sku((sku or "").strip()))

    def set_product_cost_fields(
        self,
        product_id: str,
        *,
        weighted_avg_cost: Optional[float] = None,
        last_purchase_rate: Optional[float] = None,
    ) -> InventoryProduct:
        product = self._product_repo.find_by_id(product_id)
        if not product:
            raise ValueError("Product not found")
        if weighted_avg_cost is not None:
            product.weighted_avg_cost = round(max(float(weighted_avg_cost), 0.0), 2)
        if last_purchase_rate is not None:
            product.last_purchase_rate = round(max(float(last_purchase_rate), 0.0), 2)
        return self._product_repo.save(product)

    def create_product(
        self,
        sku: str,
        name: str,
        category_ids: Union[str, List[str]],
        opening_qty: float = 0.0,
        *,
        unit_id: str = "",
        unit_code: str = "",
        hsn_sac: str = "",
        selling_rate: float = 0.0,
        mrp: float = 0.0,
        gst_rate: float = 0.0,
        gst_required: bool = False,
        specifications: Optional[Dict[str, str]] = None,
        custom_fields: Optional[Dict[str, Any]] = None,
        pending_category_name: Optional[Union[str, List[str]]] = None,
        pending_unit_code: Optional[str] = None,
        last_purchase_rate: float = 0.0,
    ) -> InventoryProduct:
        ids = [category_ids] if isinstance(category_ids, str) else list(category_ids)
        ids = self._resolve_pending_category(ids, pending_category_name)
        unit_id = self._resolve_pending_unit(unit_id, pending_unit_code)
        product = self._domain.create_product(
            sku,
            name,
            ids,
            unit_id=unit_id,
            opening_qty=opening_qty,
            hsn_sac=hsn_sac,
            selling_rate=selling_rate,
            mrp=mrp,
            gst_rate=gst_rate,
            gst_required=gst_required,
            specifications=specifications,
            custom_fields=custom_fields,
        )
        if float(last_purchase_rate or 0) > 0:
            product = self.set_product_cost_fields(
                product.id, last_purchase_rate=last_purchase_rate
            )
        return self._hydrate_product(product)

    def update_product(
        self,
        product_id: str,
        sku: str,
        name: str,
        category_ids: Union[str, List[str]],
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
        pending_category_name: Optional[Union[str, List[str]]] = None,
        pending_unit_code: Optional[str] = None,
        last_purchase_rate: Optional[float] = None,
    ) -> InventoryProduct:
        ids = [category_ids] if isinstance(category_ids, str) else list(category_ids)
        ids = self._resolve_pending_category(ids, pending_category_name)
        unit_id = self._resolve_pending_unit(unit_id, pending_unit_code)
        product = self._domain.update_product(
            product_id,
            sku,
            name,
            ids,
            unit_id,
            is_active,
            hsn_sac=hsn_sac,
            selling_rate=selling_rate,
            mrp=mrp,
            gst_rate=gst_rate,
            gst_required=gst_required,
            specifications=specifications,
            custom_fields=custom_fields,
        )
        if last_purchase_rate is not None:
            product = self.set_product_cost_fields(
                product.id, last_purchase_rate=last_purchase_rate
            )
        return self._hydrate_product(product)

    def _resolve_pending_category(
        self,
        category_ids: List[str],
        pending_name: Optional[Union[str, List[str]]] = None,
    ) -> List[str]:
        if isinstance(pending_name, list):
            names = pending_name
        elif pending_name:
            names = [pending_name]
        else:
            names = []
        for raw in names:
            name = (raw or "").strip()
            if not name:
                continue
            created = self.create_category(name, parent_id=None)
            if created.id not in category_ids:
                category_ids = list(category_ids) + [created.id]
        return category_ids

    def _resolve_pending_unit(
        self, unit_id: str, pending_code: Optional[str]
    ) -> str:
        if unit_id:
            return unit_id
        code = (pending_code or "").strip()
        if not code:
            raise ValueError("Unit is required")
        return self.find_or_create_unit(code).id

    def list_selling_rate_history(self, product_id: str) -> List[ProductRatePeriod]:
        if not self._rate_history:
            return []
        return self._rate_history.list_selling_rates(product_id)

    def list_mrp_history(self, product_id: str) -> List[ProductRatePeriod]:
        if not self._rate_history:
            return []
        return self._rate_history.list_mrp(product_id)

    def list_gst_rate_history(self, product_id: str) -> List[ProductRatePeriod]:
        if not self._rate_history:
            return []
        return self._rate_history.list_gst_rates(product_id)

    def add_scheduled_rate_period(
        self,
        rate_type: str,
        product_id: str,
        *,
        value: float,
        start_date: date,
        end_date: Optional[date] = None,
    ) -> ProductRatePeriod:
        if not self._rate_history:
            raise ValueError("Rate history is not configured")
        return self._rate_history.add_scheduled_period(
            rate_type,
            product_id,
            value=value,
            start_date=start_date,
            end_date=end_date,
        )

    def rate_period_status(self, period: ProductRatePeriod, as_of: Optional[date] = None):
        if not self._rate_history:
            from vaybooks.bms.domain.inventory.rate_history import period_status

            return period_status(period, as_of or date.today())
        return self._rate_history.status_for(period, as_of)

    def get_stock_on_hand(self) -> List[InventoryProduct]:
        return self.list_products(active_only=False)

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

    def apply_sales_movements(
        self,
        voucher_id: str,
        line_items: list[dict],
        movement_date: Optional[date] = None,
    ):
        from vaybooks.bms.domain.shared.enums import StockReferenceType

        return self._domain.record_sale_movements(
            voucher_id,
            line_items,
            StockReferenceType.SALES_INVOICE,
            movement_date,
        )

    def apply_delivery_note_issue(
        self, dn_id: str, lines: list[dict], movement_date: Optional[date] = None
    ):
        return self._domain.apply_delivery_note_issue(dn_id, lines, movement_date)

    def apply_sales_return(
        self, return_id: str, lines: list[dict], movement_date: Optional[date] = None
    ):
        return self._domain.apply_sales_return(return_id, lines, movement_date)

    def apply_purchase_receive(
        self,
        lines: list[dict],
        reference_id: str,
        reference_type=None,
        movement_date: Optional[date] = None,
    ):
        from vaybooks.bms.domain.shared.enums import StockReferenceType

        ref_type = reference_type or StockReferenceType.GRN
        return self._domain.apply_purchase_receive(
            lines, reference_id, ref_type, movement_date
        )

    def apply_purchase_return(
        self, return_id: str, lines: list[dict], movement_date: Optional[date] = None
    ):
        return self._domain.apply_purchase_return(return_id, lines, movement_date)

    def apply_landed_cost(self, lines: list[dict]) -> None:
        self._domain.apply_landed_cost(lines)

    def reverse_movements_by_reference(self, reference_id: str) -> None:
        self._domain.reverse_movements_by_reference(reference_id)
