"""List schemas for Inventory sidebar pages."""

from __future__ import annotations

import re

from vaybooks.bms.domain.shared.enums import StockMovementType, StockReferenceType
from vaybooks.bms.ui import filtering as F
from vaybooks.bms.ui.filtering import FilterField, ListSchema, SortOption
from vaybooks.bms.ui.pagination import CARD_PAGE_SIZE, VOUCHER_PAGE_SIZE


def _enum_opts(enum_cls) -> list[tuple]:
    return [(e.value, e.value) for e in enum_cls]


def _match_inv_product_category(product, value) -> bool:
    ids = list(getattr(product, "category_ids", None) or [])
    if not ids and getattr(product, "category_id", ""):
        ids = [product.category_id]
    return value in ids


def _match_inv_category_active(category, _value) -> bool:
    return bool(getattr(category, "is_active", False))


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
        SortOption("created_at", "Created (newest)"),
        SortOption("name", "Category name"),
    ],
    default_sort="created_at",
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
        SortOption("created_at", "Created (newest)"),
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
    ],
    sort_options=[
        SortOption("movement_date", "Date (newest)"),
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
        SortOption("effective_date", "Effective date (newest)"),
        SortOption("customer_name", "Customer"),
        SortOption("sku", "SKU"),
        SortOption("product_name", "Product"),
    ],
    default_sort="effective_date",
    page_size=VOUCHER_PAGE_SIZE,
)

INVENTORY_SCHEMAS = {
    s.entity_key: s
    for s in [
        INVENTORY_CATEGORIES,
        INVENTORY_PRODUCTS,
        INVENTORY_STOCK,
        INVENTORY_STOCK_LEDGER,
        INVENTORY_CUSTOMER_PRICES,
    ]
}
