"""List schemas for Inventory sidebar pages."""

from __future__ import annotations

import re
from datetime import date

from vaybooks.bms.domain.shared.enums import (
    LocationType,
    StockMovementType,
    StockReferenceType,
    StockTransferStatus,
)
from vaybooks.bms.ui import filtering as F
from vaybooks.bms.ui.filtering import FilterField, ListSchema, SortOption
from vaybooks.bms.ui.pagination import CARD_PAGE_SIZE, VOUCHER_PAGE_SIZE


def _mtd() -> tuple[date, date]:
    today = date.today()
    return today.replace(day=1), today


def _enum_opts(enum_cls) -> list[tuple]:
    return [(e.value, e.value) for e in enum_cls]


def _match_inv_product_category(product, value) -> bool:
    ids = list(getattr(product, "category_ids", None) or [])
    if not ids and getattr(product, "category_id", ""):
        ids = [product.category_id]
    return value in ids


def _match_inv_category_active(category, _value) -> bool:
    return bool(getattr(category, "is_active", False))


def _match_inv_warehouse_active(warehouse, _value) -> bool:
    return bool(getattr(warehouse, "is_active", False))


def _match_location_active(location, _value) -> bool:
    return bool(getattr(location, "is_active", False))


def _match_location_type(location, value) -> bool:
    loc_type = getattr(location, "location_type", None)
    return getattr(loc_type, "value", loc_type) == value


def _match_stock_ledger_location(row, value) -> bool:
    return row.get("location_id") == value


def _match_transfer_status(transfer, value) -> bool:
    status = getattr(transfer, "status", None)
    return getattr(status, "value", status) == value


def _match_transfer_location(transfer, value) -> bool:
    return (
        getattr(transfer, "from_location_id", None) == value
        or getattr(transfer, "to_location_id", None) == value
    )


def _match_inv_product_active(product, _value) -> bool:
    return bool(getattr(product, "is_active", False))


def _match_stock_ledger_product(row, value) -> bool:
    return row.get("product_id") == value


def _match_stock_ledger_category(row, value) -> bool:
    return row.get("category_id") == value


def _match_stock_ledger_reference(row, value) -> bool:
    return row.get("reference_type") == value


def _match_customer_price_customer(row, value) -> bool:
    return row.get("customer_id") == value


def _match_customer_price_product(row, value) -> bool:
    sku = (row.get("sku") or "").lower()
    name = (row.get("product_name") or "").lower()
    needle = str(value or "").lower()
    if not needle:
        return True
    try:
        return (
            re.search(needle, sku, re.IGNORECASE) is not None
            or re.search(needle, name, re.IGNORECASE) is not None
        )
    except re.error:
        return needle in sku or needle in name


def _match_product_category_names(product, pattern: str) -> bool:
    names = list(getattr(product, "category_names", None) or [])
    if not names and getattr(product, "category_name", ""):
        names = [product.category_name]
    joined = " | ".join(names)
    try:
        return re.search(str(pattern), joined, re.IGNORECASE) is not None
    except re.error:
        return False


INVENTORY_OVERVIEW = ListSchema(
    entity_key="inventory_overview",
    title="Inventory Overview",
    filter_fields=[
        FilterField(
            "date_range",
            "Period",
            F.DATE_RANGE,
            default=_mtd,
        ),
    ],
    sort_options=[
        SortOption("date_range", "Period"),
    ],
    default_sort="date_range",
    page_size=CARD_PAGE_SIZE,
)

INVENTORY_CATEGORIES = ListSchema(
    entity_key="inventory_categories",
    title="Product Categories",
    filter_fields=[
        FilterField("name", "Category name", F.REGEX),
        FilterField("path", "Category path", F.REGEX, record_attr="path"),
        FilterField("active_only", "Active only", F.CHECKBOX,
                    match=_match_inv_category_active),
    ],
    sort_options=[
        SortOption("created_at", "Created"),
        SortOption("name", "Category name"),
    ],
    default_sort="created_at",
    page_size=CARD_PAGE_SIZE,
)

INVENTORY_WAREHOUSES = ListSchema(
    entity_key="inventory_warehouses",
    title="Warehouses",
    filter_fields=[
        FilterField("code", "Code", F.REGEX),
        FilterField("name", "Name", F.REGEX),
        FilterField("address", "Address", F.REGEX),
        FilterField("active_only", "Active only", F.CHECKBOX,
                    match=_match_inv_warehouse_active),
    ],
    sort_options=[
        SortOption("created_at", "Created"),
        SortOption("code", "Code"),
        SortOption("name", "Name"),
    ],
    default_sort="code",
    page_size=CARD_PAGE_SIZE,
)

# Locations now live under Settings → Locations (warehouses/list.py redirects here).
SETTINGS_LOCATIONS = ListSchema(
    entity_key="settings_locations",
    title="Locations",
    filter_fields=[
        FilterField("code", "Code", F.REGEX),
        FilterField("name", "Name", F.REGEX),
        FilterField("address", "Address", F.REGEX),
        FilterField(
            "location_type",
            "Type",
            F.SELECT,
            options=_enum_opts(LocationType),
            multi=False,
            match=_match_location_type,
        ),
        FilterField("active_only", "Active only", F.CHECKBOX,
                    match=_match_location_active),
    ],
    sort_options=[
        SortOption("created_at", "Created"),
        SortOption("code", "Code"),
        SortOption("name", "Name"),
        SortOption("location_type", "Type"),
    ],
    default_sort="code",
    page_size=CARD_PAGE_SIZE,
)

INVENTORY_PRODUCTS = ListSchema(
    entity_key="inventory_products",
    title="Inventory Products",
    filter_fields=[
        FilterField("sku", "SKU", F.REGEX),
        FilterField("name", "Product name", F.REGEX),
        FilterField("hsn_sac", "HSN", F.REGEX),
        FilterField(
            "category_path",
            "Category path",
            F.REGEX,
            match=_match_product_category_names,
        ),
        FilterField("category_id", "Category", F.ENTITY_SELECT,
                    options_loader="inventory_categories",
                    match=_match_inv_product_category),
        FilterField("active_only", "Active only", F.CHECKBOX,
                    match=_match_inv_product_active),
    ],
    sort_options=[
        SortOption("created_at", "Created"),
        SortOption("name", "Product name"),
        SortOption("sku", "SKU"),
        SortOption("current_qty", "Stock qty"),
    ],
    default_sort="created_at",
    page_size=CARD_PAGE_SIZE,
)

INVENTORY_STOCK = ListSchema(
    entity_key="inventory_stock",
    title="Stock on Hand",
    filter_fields=[
        FilterField("sku", "SKU", F.REGEX),
        FilterField("name", "Product name", F.REGEX),
        FilterField("category_id", "Category", F.ENTITY_SELECT,
                    options_loader="inventory_categories",
                    match=_match_inv_product_category),
        FilterField("active_only", "Active only", F.CHECKBOX,
                    match=_match_inv_product_active),
    ],
    sort_options=[
        SortOption("name", "Product name"),
        SortOption("current_qty", "Stock qty (high)"),
        SortOption("sku", "SKU"),
    ],
    default_sort="name",
    page_size=CARD_PAGE_SIZE,
)

INVENTORY_STOCK_LEDGER = ListSchema(
    entity_key="inventory_stock_ledger",
    title="Stock Ledger",
    filter_fields=[
        FilterField("movement_date", "Movement date", F.DATE_RANGE),
        FilterField("product_id", "Product", F.ENTITY_SELECT,
                    options_loader="inventory_products",
                    match=_match_stock_ledger_product),
        FilterField("category_id", "Category", F.ENTITY_SELECT,
                    options_loader="inventory_categories",
                    match=_match_stock_ledger_category),
        FilterField("movement_type", "Movement type", F.SELECT,
                    options=_enum_opts(StockMovementType),
                    match=lambda row, v: row.get("movement_type") == v),
        FilterField("reference_type", "Reference type", F.SELECT,
                    options=_enum_opts(StockReferenceType),
                    match=_match_stock_ledger_reference),
        FilterField("location_id", "Location", F.ENTITY_SELECT,
                    options_loader="inventory_locations",
                    multi=False,
                    match=_match_stock_ledger_location),
    ],
    sort_options=[
        SortOption("movement_date", "Date"),
        SortOption("product_name", "Product name"),
        SortOption("movement_type", "Movement type"),
    ],
    default_sort="movement_date",
    page_size=VOUCHER_PAGE_SIZE,
)

INVENTORY_MOVEMENTS = ListSchema(
    entity_key="inventory_movements",
    title="Stock Movements",
    filter_fields=[
        FilterField("movement_date", "Movement date", F.DATE_RANGE),
        FilterField("product_id", "Product", F.ENTITY_SELECT,
                    options_loader="inventory_products",
                    match=_match_stock_ledger_product),
        FilterField("category_id", "Category", F.ENTITY_SELECT,
                    options_loader="inventory_categories",
                    match=_match_stock_ledger_category),
        FilterField("movement_type", "Movement type", F.SELECT,
                    options=_enum_opts(StockMovementType),
                    match=lambda row, v: row.get("movement_type") == v),
        FilterField("location_id", "Location", F.ENTITY_SELECT,
                    options_loader="inventory_locations",
                    multi=False,
                    match=_match_stock_ledger_location),
    ],
    sort_options=[
        SortOption("movement_date", "Date"),
        SortOption("product_name", "Product name"),
        SortOption("movement_type", "Movement type"),
    ],
    default_sort="movement_date",
    page_size=VOUCHER_PAGE_SIZE,
)

INVENTORY_CUSTOMER_PRICES = ListSchema(
    entity_key="inventory_customer_prices",
    title="Customer Prices",
    filter_fields=[
        FilterField(
            "customer_id",
            "Customer",
            F.ENTITY_SELECT,
            options_loader="customers",
            match=_match_customer_price_customer,
        ),
        FilterField(
            "sku",
            "SKU / Product",
            F.REGEX,
            match=_match_customer_price_product,
        ),
        FilterField("effective_date", "Effective date", F.DATE_RANGE),
    ],
    sort_options=[
        SortOption("effective_date", "Effective date"),
        SortOption("customer_name", "Customer"),
        SortOption("sku", "SKU"),
        SortOption("product_name", "Product"),
    ],
    default_sort="effective_date",
    page_size=VOUCHER_PAGE_SIZE,
)

INVENTORY_TRANSFERS = ListSchema(
    entity_key="inventory_transfers",
    title="Stock Transfers",
    filter_fields=[
        FilterField("transfer_number", "Transfer #", F.REGEX),
        FilterField("transfer_date", "Transfer date", F.DATE_RANGE),
        FilterField(
            "status",
            "Status",
            F.SELECT,
            options=_enum_opts(StockTransferStatus),
            multi=False,
            match=_match_transfer_status,
        ),
        FilterField(
            "location_id",
            "Location (from/to)",
            F.ENTITY_SELECT,
            options_loader="inventory_locations",
            multi=False,
            match=_match_transfer_location,
        ),
    ],
    sort_options=[
        SortOption("created_at", "Created"),
        SortOption("transfer_date", "Transfer date"),
        SortOption("transfer_number", "Transfer #"),
        SortOption("status", "Status"),
    ],
    default_sort="created_at",
    page_size=CARD_PAGE_SIZE,
)

INVENTORY_SCHEMAS = {
    s.entity_key: s
    for s in [
        INVENTORY_OVERVIEW,
        INVENTORY_CATEGORIES,
        INVENTORY_WAREHOUSES,
        SETTINGS_LOCATIONS,
        INVENTORY_PRODUCTS,
        INVENTORY_STOCK,
        INVENTORY_STOCK_LEDGER,
        INVENTORY_MOVEMENTS,
        INVENTORY_CUSTOMER_PRICES,
        INVENTORY_TRANSFERS,
    ]
}
