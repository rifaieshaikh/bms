"""Inventory report queries for dashboard and Reports page."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime

from vaybooks.bms.application.inventory_app_service import InventoryAppService
from vaybooks.bms.application.report_filters import (
    LowStockFilter,
    StockMovementsFilter,
    StockOnHandFilter,
)

LOW_STOCK_THRESHOLD = 2.0


def _movement_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _stock_status(qty: float, threshold: float = LOW_STOCK_THRESHOLD) -> str:
    if qty <= 0:
        return "Out of stock"
    if qty <= threshold:
        return "Low stock"
    return "In stock"


class InventoryReportService:
    def __init__(self, inventory: InventoryAppService):
        self._inventory = inventory

    def health_summary(self) -> dict:
        products = self._inventory.list_products(active_only=False)
        active = [p for p in products if p.is_active]
        total_units = round(sum(p.current_qty for p in active), 2)
        stock_value = round(
            sum(p.current_qty * p.selling_rate for p in active), 2
        )
        low_stock = [
            p for p in active if 0 < p.current_qty <= LOW_STOCK_THRESHOLD
        ]
        out_of_stock = [p for p in active if p.current_qty <= 0]
        categories = self._inventory.list_categories(active_only=False)
        active_categories = sum(1 for c in categories if c.is_active)

        today = date.today()
        start = today.replace(day=1)
        _, last_day = monthrange(today.year, today.month)
        end = today.replace(day=last_day)
        movements_month = [
            row
            for row in self._inventory.get_stock_ledger()
            if (md := _movement_date(row.get("movement_date"))) is not None
            and start <= md <= end
        ]

        low_stock_items = sorted(
            [p for p in active if p.current_qty <= LOW_STOCK_THRESHOLD],
            key=lambda p: p.current_qty,
        )[:6]
        low_stock_rows = [
            {
                "id": p.id,
                "sku": p.sku,
                "name": p.name,
                "category_name": p.category_name,
                "current_qty": p.current_qty,
                "unit": p.unit,
                "stock_status": _stock_status(p.current_qty),
            }
            for p in low_stock_items
        ]

        return {
            "total_products": len(products),
            "active_products": len(active),
            "active_categories": active_categories,
            "total_units": total_units,
            "stock_value": stock_value,
            "low_stock_count": len(low_stock),
            "out_of_stock_count": len(out_of_stock),
            "movements_this_month": len(movements_month),
            "low_stock_items": low_stock_rows,
        }

    def stock_on_hand_report(self, filters: StockOnHandFilter) -> list[dict]:
        products = self._inventory.list_products(active_only=False)
        rows = []
        for product in products:
            if filters.active_only and not product.is_active:
                continue
            if filters.category_id and product.category_id != filters.category_id:
                continue
            if filters.min_qty is not None and product.current_qty < filters.min_qty:
                continue
            if filters.search:
                needle = filters.search.lower()
                hay = f"{product.sku} {product.name} {product.category_name}".lower()
                if needle not in hay:
                    continue
            rows.append(
                {
                    "sku": product.sku,
                    "product_name": product.name,
                    "category": product.category_name,
                    "qty": product.current_qty,
                    "unit": product.unit,
                    "selling_rate": product.selling_rate,
                    "stock_value": round(product.current_qty * product.selling_rate, 2),
                    "stock_status": _stock_status(product.current_qty),
                    "is_active": "Yes" if product.is_active else "No",
                }
            )
        return rows

    def low_stock_report(self, filters: LowStockFilter) -> list[dict]:
        threshold = filters.threshold if filters.threshold > 0 else LOW_STOCK_THRESHOLD
        products = self._inventory.list_products(active_only=True)
        rows = []
        for product in products:
            if filters.category_id and product.category_id != filters.category_id:
                continue
            if product.current_qty > threshold:
                continue
            if not filters.include_out_of_stock and product.current_qty <= 0:
                continue
            rows.append(
                {
                    "sku": product.sku,
                    "product_name": product.name,
                    "category": product.category_name,
                    "qty": product.current_qty,
                    "unit": product.unit,
                    "threshold": threshold,
                    "stock_status": _stock_status(product.current_qty, threshold),
                    "selling_rate": product.selling_rate,
                }
            )
        return sorted(rows, key=lambda r: (r["qty"], r["product_name"]))

    def stock_movements_report(self, filters: StockMovementsFilter) -> list[dict]:
        start = filters.date_range.start
        end = filters.date_range.end
        rows = []
        for row in self._inventory.get_stock_ledger():
            md = _movement_date(row.get("movement_date"))
            if md is None or md < start or md > end:
                continue
            if filters.product_id and row.get("product_id") != filters.product_id:
                continue
            if filters.movement_type and row.get("movement_type") != filters.movement_type:
                continue
            if filters.category_id and row.get("category_id") != filters.category_id:
                continue
            rows.append(
                {
                    "movement_date": md,
                    "product_name": row.get("product_name", ""),
                    "sku": row.get("sku", ""),
                    "category": row.get("category_name", ""),
                    "movement_type": row.get("movement_type", ""),
                    "qty_in": row.get("qty_in") or "",
                    "qty_out": row.get("qty_out") or "",
                    "reference": row.get("reference_id")
                    or row.get("reference_type", ""),
                    "notes": row.get("notes", ""),
                }
            )
        return rows

    def inventory_valuation_report(self, filters: StockOnHandFilter) -> list[dict]:
        products = self._inventory.list_products(active_only=filters.active_only)
        rows = []
        for product in products:
            if filters.category_id and product.category_id != filters.category_id:
                continue
            if filters.search:
                needle = filters.search.lower()
                hay = f"{product.sku} {product.name} {product.category_name}".lower()
                if needle not in hay:
                    continue
            rows.append(
                {
                    "sku": product.sku,
                    "product_name": product.name,
                    "category": product.category_name,
                    "qty": product.current_qty,
                    "weighted_avg_cost": product.weighted_avg_cost,
                    "valuation": round(
                        product.current_qty * product.weighted_avg_cost, 2
                    ),
                }
            )
        return rows
