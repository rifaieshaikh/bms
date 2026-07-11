from datetime import date
from typing import Any, Dict, List, Optional, Union

from vaybooks.bms.domain.inventory.category_tree import build_category_path
from vaybooks.bms.domain.inventory.entities import (
    InventoryProduct,
    ProductCategory,
    ProductUnit,
)
from vaybooks.bms.domain.inventory.field_definitions import ProductFieldDefinition, ProductFieldType
from vaybooks.bms.domain.shared.item_tax import (
    ItemTaxProfile,
    ProductGstSlab,
    ProductMrpSlab,
)
from vaybooks.bms.domain.inventory.repository import (
    InventoryProductRepository,
    ProductCategoryRepository,
    ProductFieldDefinitionRepository,
    ProductUnitRepository,
    StockMovementRepository,
)
from vaybooks.bms.domain.inventory.services import InventoryDomainService
from vaybooks.bms.domain.shared.enums import StockMovementType


def _slabs_from_tax_profile(profile: ItemTaxProfile) -> tuple[list[ProductGstSlab], list[ProductMrpSlab]]:
    return (
        [InventoryProduct.default_gst_slab(gst_rate=profile.gst_rate, effective_from=date.today())],
        [InventoryProduct.default_mrp_entry(mrp=profile.mrp, effective_from=date.today())],
    )


class InventoryAppService:
    def __init__(
        self,
        category_repo: ProductCategoryRepository,
        product_repo: InventoryProductRepository,
        movement_repo: StockMovementRepository,
        unit_repo: Optional[ProductUnitRepository] = None,
        field_def_repo: Optional[ProductFieldDefinitionRepository] = None,
    ):
        self._domain = InventoryDomainService(
            category_repo,
            product_repo,
            movement_repo,
            unit_repo,
            field_def_repo,
        )
        self._product_repo = product_repo
        self._category_repo = category_repo
        self._unit_repo = unit_repo
        self._field_def_repo = field_def_repo

    def _hydrate_product(self, product: Optional[InventoryProduct]) -> Optional[InventoryProduct]:
        if not product:
            return None
        return self._domain.resolve_unit_for_product(product)

    def list_units(self, active_only: bool = True) -> List[ProductUnit]:
        return self._domain.list_units(active_only=active_only)

    def find_or_create_unit(self, code: str, label: str = "") -> ProductUnit:
        return self._domain.find_or_create_unit(code, label)

    def update_unit(self, unit_id: str, label: str, is_active: bool = True) -> ProductUnit:
        return self._domain.update_unit(unit_id, label, is_active)

    def get_category_path(self, category_id: str) -> str:
        categories = {c.id: c for c in self._category_repo.list_all(active_only=False)}
        return build_category_path(category_id, categories)

    def list_categories(self, active_only: bool = False) -> List[ProductCategory]:
        return self._category_repo.list_all(active_only=active_only)

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
        return [self._domain.resolve_unit_for_product(p) for p in products]

    def search_products(self, query: str) -> List[InventoryProduct]:
        return [self._domain.resolve_unit_for_product(p) for p in self._product_repo.search(query)]

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
        unit: str = "pcs",
        selling_rate: float = 0.0,
        opening_qty: float = 0.0,
        *,
        unit_id: str = "",
        hsn_sac: str = "",
        gst_rates: Optional[List[ProductGstSlab]] = None,
        mrp_entries: Optional[List[ProductMrpSlab]] = None,
        tax_profile: Optional[ItemTaxProfile] = None,
        specifications: Optional[Dict[str, str]] = None,
        custom_fields: Optional[Dict[str, Any]] = None,
    ) -> InventoryProduct:
        ids = [category_ids] if isinstance(category_ids, str) else list(category_ids)
        if tax_profile is not None and gst_rates is None and mrp_entries is None:
            gst_rates, mrp_entries = _slabs_from_tax_profile(tax_profile)
            if not hsn_sac:
                hsn_sac = tax_profile.hsn_sac
        return self._domain.create_product(
            sku,
            name,
            ids,
            unit_id=unit_id,
            unit_code=unit,
            selling_rate=selling_rate,
            opening_qty=opening_qty,
            hsn_sac=hsn_sac,
            gst_rates=gst_rates,
            mrp_entries=mrp_entries,
            specifications=specifications,
            custom_fields=custom_fields,
        )

    def update_product(
        self,
        product_id: str,
        sku: str,
        name: str,
        category_ids: Union[str, List[str]],
        unit_id: str,
        selling_rate: float,
        is_active: bool = True,
        *,
        hsn_sac: Optional[str] = None,
        gst_rates: Optional[List[ProductGstSlab]] = None,
        mrp_entries: Optional[List[ProductMrpSlab]] = None,
        tax_profile: Optional[ItemTaxProfile] = None,
        specifications: Optional[Dict[str, str]] = None,
        custom_fields: Optional[Dict[str, Any]] = None,
    ) -> InventoryProduct:
        ids = [category_ids] if isinstance(category_ids, str) else list(category_ids)
        if tax_profile is not None and gst_rates is None and mrp_entries is None:
            gst_rates, mrp_entries = _slabs_from_tax_profile(tax_profile)
            if hsn_sac is None:
                hsn_sac = tax_profile.hsn_sac
        return self._domain.update_product(
            product_id,
            sku,
            name,
            ids,
            unit_id,
            selling_rate,
            is_active,
            hsn_sac=hsn_sac,
            gst_rates=gst_rates,
            mrp_entries=mrp_entries,
            specifications=specifications,
            custom_fields=custom_fields,
        )

    def set_product_tax_profile(
        self, product_id: str, tax_profile: ItemTaxProfile
    ) -> InventoryProduct:
        product = self._product_repo.find_by_id(product_id)
        if not product:
            raise ValueError("Product not found")
        gst_rates, mrp_entries = _slabs_from_tax_profile(tax_profile)
        product.apply_tax_data(tax_profile.hsn_sac, gst_rates, mrp_entries)
        return self._product_repo.save(product)

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
