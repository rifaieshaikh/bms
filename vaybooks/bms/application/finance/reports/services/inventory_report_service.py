"""Inventory report queries for dashboard and Reports page."""

from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime

from vaybooks.bms.application.inventory.service import InventoryAppService
from vaybooks.bms.application.report_filters import (
    CustomerLatestPricesFilter,
    DeadStockFilter,
    FastMovingStockFilter,
    LowStockFilter,
    OpeningClosingStockFilter,
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


def _qty_in(row: dict) -> float:
    try:
        return float(row.get("qty_in") or 0)
    except (TypeError, ValueError):
        return 0.0


def _qty_out(row: dict) -> float:
    try:
        return float(row.get("qty_out") or 0)
    except (TypeError, ValueError):
        return 0.0


class InventoryReportService:
    def __init__(self, inventory: InventoryAppService, sales=None):
        self._inventory = inventory
        self._sales = sales

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

        in_stock_count = sum(
            1 for p in active if p.current_qty > LOW_STOCK_THRESHOLD
        )

        return {
            "total_products": len(products),
            "active_products": len(active),
            "active_categories": active_categories,
            "total_units": total_units,
            "stock_value": stock_value,
            "low_stock_count": len(low_stock),
            "out_of_stock_count": len(out_of_stock),
            "in_stock_count": in_stock_count,
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

    def category_stock_summary_report(self, filters: StockOnHandFilter) -> list[dict]:
        products = self._inventory.list_products(active_only=False)
        buckets: dict[str, dict] = {}
        for product in products:
            if filters.active_only and not product.is_active:
                continue
            if filters.category_id and product.category_id != filters.category_id:
                continue
            if filters.search:
                needle = filters.search.lower()
                hay = f"{product.sku} {product.name} {product.category_name}".lower()
                if needle not in hay:
                    continue
            key = product.category_id or ""
            label = (product.category_name or "").strip() or "(uncategorized)"
            bucket = buckets.get(key)
            if bucket is None:
                bucket = {
                    "category": label,
                    "product_count": 0,
                    "qty": 0.0,
                    "stock_value": 0.0,
                    "valuation": 0.0,
                }
                buckets[key] = bucket
            bucket["product_count"] += 1
            bucket["qty"] = round(bucket["qty"] + product.current_qty, 2)
            bucket["stock_value"] = round(
                bucket["stock_value"] + product.current_qty * product.selling_rate, 2
            )
            bucket["valuation"] = round(
                bucket["valuation"] + product.current_qty * product.weighted_avg_cost, 2
            )
        return sorted(buckets.values(), key=lambda r: r["category"].lower())

    def dead_stock_report(self, filters: DeadStockFilter) -> list[dict]:
        start = filters.date_range.start
        end = filters.date_range.end
        qty_out_by_product: dict[str, float] = defaultdict(float)
        for row in self._inventory.get_stock_ledger():
            md = _movement_date(row.get("movement_date"))
            if md is None or md < start or md > end:
                continue
            pid = row.get("product_id") or ""
            if not pid:
                continue
            qty_out_by_product[pid] = round(
                qty_out_by_product[pid] + _qty_out(row), 2
            )

        min_qty = float(filters.min_qty or 0)
        max_qty_out = float(filters.max_qty_out or 0)
        rows = []
        for product in self._inventory.list_products(active_only=True):
            if filters.category_id and product.category_id != filters.category_id:
                continue
            if product.current_qty <= min_qty:
                continue
            moved_out = qty_out_by_product.get(product.id, 0.0)
            if moved_out > max_qty_out:
                continue
            rows.append(
                {
                    "sku": product.sku,
                    "product_name": product.name,
                    "category": product.category_name,
                    "qty": product.current_qty,
                    "unit": product.unit,
                    "qty_out_in_period": moved_out,
                    "stock_value": round(
                        product.current_qty * product.selling_rate, 2
                    ),
                    "valuation": round(
                        product.current_qty * product.weighted_avg_cost, 2
                    ),
                }
            )
        return sorted(rows, key=lambda r: (r["qty_out_in_period"], r["product_name"]))

    def stock_movement_summary_report(
        self, filters: StockMovementsFilter
    ) -> list[dict]:
        start = filters.date_range.start
        end = filters.date_range.end
        buckets: dict[str, dict] = {}
        for row in self._inventory.get_stock_ledger():
            md = _movement_date(row.get("movement_date"))
            if md is None or md < start or md > end:
                continue
            if filters.category_id and row.get("category_id") != filters.category_id:
                continue
            if filters.product_id and row.get("product_id") != filters.product_id:
                continue
            if filters.movement_type and row.get("movement_type") != filters.movement_type:
                continue
            mtype = row.get("movement_type") or "(unknown)"
            bucket = buckets.get(mtype)
            if bucket is None:
                bucket = {
                    "movement_type": mtype,
                    "movement_count": 0,
                    "qty_in": 0.0,
                    "qty_out": 0.0,
                }
                buckets[mtype] = bucket
            bucket["movement_count"] += 1
            bucket["qty_in"] = round(bucket["qty_in"] + _qty_in(row), 2)
            bucket["qty_out"] = round(bucket["qty_out"] + _qty_out(row), 2)
        return sorted(buckets.values(), key=lambda r: r["movement_type"])

    def stock_margin_report(self, filters: StockOnHandFilter) -> list[dict]:
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
            unit_margin = round(product.selling_rate - product.weighted_avg_cost, 2)
            rows.append(
                {
                    "sku": product.sku,
                    "product_name": product.name,
                    "category": product.category_name,
                    "qty": product.current_qty,
                    "weighted_avg_cost": product.weighted_avg_cost,
                    "selling_rate": product.selling_rate,
                    "unit_margin": unit_margin,
                    "stock_margin": round(unit_margin * product.current_qty, 2),
                }
            )
        return rows

    def opening_closing_stock_report(
        self, filters: OpeningClosingStockFilter
    ) -> list[dict]:
        start = filters.date_range.start
        end = filters.date_range.end
        products = {
            p.id: p
            for p in self._inventory.list_products(active_only=False)
            if (not filters.active_only or p.is_active)
            and (not filters.category_id or p.category_id == filters.category_id)
            and (not filters.product_id or p.id == filters.product_id)
        }
        opening: dict[str, float] = defaultdict(float)
        qty_in: dict[str, float] = defaultdict(float)
        qty_out: dict[str, float] = defaultdict(float)

        for row in self._inventory.get_stock_ledger():
            pid = row.get("product_id") or ""
            if pid not in products:
                continue
            md = _movement_date(row.get("movement_date"))
            if md is None:
                continue
            q_in = _qty_in(row)
            q_out = _qty_out(row)
            if md < start:
                opening[pid] = round(opening[pid] + q_in - q_out, 2)
            elif md <= end:
                qty_in[pid] = round(qty_in[pid] + q_in, 2)
                qty_out[pid] = round(qty_out[pid] + q_out, 2)

        rows = []
        for pid, product in products.items():
            open_qty = opening.get(pid, 0.0)
            in_qty = qty_in.get(pid, 0.0)
            out_qty = qty_out.get(pid, 0.0)
            close_qty = round(open_qty + in_qty - out_qty, 2)
            if open_qty == 0 and in_qty == 0 and out_qty == 0 and close_qty == 0:
                if product.current_qty == 0:
                    continue
            rows.append(
                {
                    "sku": product.sku,
                    "product_name": product.name,
                    "category": product.category_name,
                    "unit": product.unit,
                    "opening_qty": open_qty,
                    "qty_in": in_qty,
                    "qty_out": out_qty,
                    "closing_qty": close_qty,
                    "current_qty": product.current_qty,
                    "variance": round(close_qty - product.current_qty, 2),
                    "opening_value": round(open_qty * product.weighted_avg_cost, 2),
                    "closing_value": round(close_qty * product.weighted_avg_cost, 2),
                }
            )
        return sorted(rows, key=lambda r: r["product_name"].lower())

    def hsn_stock_summary_report(self, filters: StockOnHandFilter) -> list[dict]:
        products = self._inventory.list_products(active_only=False)
        buckets: dict[str, dict] = {}
        for product in products:
            if filters.active_only and not product.is_active:
                continue
            if filters.category_id and product.category_id != filters.category_id:
                continue
            if filters.min_qty is not None and product.current_qty < filters.min_qty:
                continue
            hsn = (product.hsn_sac or "").strip() or "(blank)"
            if filters.search:
                needle = filters.search.lower()
                hay = f"{hsn} {product.sku} {product.name}".lower()
                if needle not in hay:
                    continue
            gst = float(product.active_gst_rate or 0)
            bucket = buckets.get(hsn)
            if bucket is None:
                bucket = {
                    "hsn_sac": hsn,
                    "product_count": 0,
                    "qty": 0.0,
                    "stock_value": 0.0,
                    "valuation": 0.0,
                    "_gst_rates": set(),
                }
                buckets[hsn] = bucket
            bucket["product_count"] += 1
            bucket["qty"] = round(bucket["qty"] + product.current_qty, 2)
            bucket["stock_value"] = round(
                bucket["stock_value"] + product.current_qty * product.selling_rate, 2
            )
            bucket["valuation"] = round(
                bucket["valuation"] + product.current_qty * product.weighted_avg_cost, 2
            )
            bucket["_gst_rates"].add(gst)

        rows = []
        for bucket in buckets.values():
            rates = bucket.pop("_gst_rates")
            if len(rates) == 1:
                bucket["gst_rate"] = next(iter(rates))
            else:
                bucket["gst_rate"] = "Mixed"
            rows.append(bucket)
        return sorted(rows, key=lambda r: r["hsn_sac"])

    def fast_moving_stock_report(
        self, filters: FastMovingStockFilter
    ) -> list[dict]:
        start = filters.date_range.start
        end = filters.date_range.end
        qty_out_by_product: dict[str, float] = defaultdict(float)
        for row in self._inventory.get_stock_ledger():
            md = _movement_date(row.get("movement_date"))
            if md is None or md < start or md > end:
                continue
            pid = row.get("product_id") or ""
            if not pid:
                continue
            qty_out_by_product[pid] = round(
                qty_out_by_product[pid] + _qty_out(row), 2
            )

        min_qty_out = float(filters.min_qty_out or 0)
        rows = []
        for product in self._inventory.list_products(active_only=True):
            if filters.category_id and product.category_id != filters.category_id:
                continue
            moved_out = qty_out_by_product.get(product.id, 0.0)
            if moved_out <= min_qty_out:
                continue
            rows.append(
                {
                    "sku": product.sku,
                    "product_name": product.name,
                    "category": product.category_name,
                    "qty": product.current_qty,
                    "unit": product.unit,
                    "qty_out_in_period": moved_out,
                    "stock_value": round(
                        product.current_qty * product.selling_rate, 2
                    ),
                    "valuation": round(
                        product.current_qty * product.weighted_avg_cost, 2
                    ),
                }
            )
        return sorted(
            rows,
            key=lambda r: (-r["qty_out_in_period"], r["product_name"]),
        )

    def customer_latest_prices_report(
        self, filters: CustomerLatestPricesFilter
    ) -> list[dict]:
        if self._sales is None:
            return []
        entries = self._sales.list_customer_prices(limit=5000)
        latest: dict[tuple[str, str], object] = {}
        for entry in entries:
            key = (entry.customer_id, entry.product_id)
            existing = latest.get(key)
            if existing is None:
                latest[key] = entry
                continue
            existing_date = getattr(existing, "effective_date", date.min) or date.min
            entry_date = getattr(entry, "effective_date", date.min) or date.min
            existing_created = getattr(existing, "created_at", datetime.min) or datetime.min
            entry_created = getattr(entry, "created_at", datetime.min) or datetime.min
            if isinstance(existing_date, datetime):
                existing_date = existing_date.date()
            if isinstance(entry_date, datetime):
                entry_date = entry_date.date()
            if entry_date > existing_date or (
                entry_date == existing_date and entry_created > existing_created
            ):
                latest[key] = entry

        selling_by_product: dict[str, float] = {}
        rows = []
        for entry in latest.values():
            if filters.customer_id and entry.customer_id != filters.customer_id:
                continue
            effective = getattr(entry, "effective_date", None)
            if isinstance(effective, datetime):
                effective = effective.date()
            if filters.date_range is not None:
                if not isinstance(effective, date):
                    continue
                if (
                    effective < filters.date_range.start
                    or effective > filters.date_range.end
                ):
                    continue
            product_id = entry.product_id
            if product_id not in selling_by_product:
                product = self._inventory.get_product(product_id)
                selling_by_product[product_id] = float(
                    getattr(product, "selling_rate", 0) or 0
                ) if product else 0.0
            sku = getattr(entry, "sku", "") or ""
            product_name = getattr(entry, "product_name", "") or ""
            customer_name = getattr(entry, "customer_name", "") or ""
            if filters.search:
                needle = filters.search.lower()
                hay = f"{sku} {product_name} {customer_name}".lower()
                if needle not in hay:
                    continue
            rate = round(float(getattr(entry, "rate", 0) or 0), 2)
            selling = round(selling_by_product.get(product_id, 0.0), 2)
            rows.append(
                {
                    "customer_name": customer_name,
                    "sku": sku,
                    "product_name": product_name,
                    "customer_rate": rate,
                    "selling_rate": selling,
                    "difference": round(rate - selling, 2),
                    "effective_date": effective,
                    "store_invoice_number": getattr(entry, "store_invoice_number", "")
                    or "",
                }
            )
        return sorted(
            rows,
            key=lambda r: (
                str(r.get("effective_date") or ""),
                r.get("customer_name") or "",
                r.get("sku") or "",
            ),
            reverse=True,
        )

    def inactive_products_with_stock_report(
        self, filters: StockOnHandFilter
    ) -> list[dict]:
        min_qty = float(filters.min_qty or 0)
        rows = []
        for product in self._inventory.list_products(active_only=False):
            if product.is_active:
                continue
            if filters.category_id and product.category_id != filters.category_id:
                continue
            if product.current_qty <= min_qty:
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
                    "stock_value": round(
                        product.current_qty * product.selling_rate, 2
                    ),
                    "valuation": round(
                        product.current_qty * product.weighted_avg_cost, 2
                    ),
                    "is_active": "No",
                }
            )
        return sorted(rows, key=lambda r: (-r["qty"], r["product_name"]))

    def product_rate_card_report(self, filters: StockOnHandFilter) -> list[dict]:
        rows = []
        for product in self._inventory.list_products(active_only=False):
            if filters.active_only and not product.is_active:
                continue
            if filters.category_id and product.category_id != filters.category_id:
                continue
            if filters.search:
                needle = filters.search.lower()
                hay = (
                    f"{product.sku} {product.name} {product.category_name} "
                    f"{product.hsn_sac or ''}"
                ).lower()
                if needle not in hay:
                    continue
            rows.append(
                {
                    "sku": product.sku,
                    "product_name": product.name,
                    "category": product.category_name,
                    "unit": product.unit,
                    "hsn_sac": (product.hsn_sac or "").strip(),
                    "selling_rate": product.selling_rate,
                    "mrp": float(product.active_mrp or 0),
                    "gst_rate": float(product.active_gst_rate or 0),
                    "last_purchase_rate": float(product.last_purchase_rate or 0),
                    "weighted_avg_cost": product.weighted_avg_cost,
                    "is_active": "Yes" if product.is_active else "No",
                }
            )
        return sorted(rows, key=lambda r: (r["sku"] or "", r["product_name"] or ""))
