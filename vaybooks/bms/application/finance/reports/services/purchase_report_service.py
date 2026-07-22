"""Purchase report queries for dashboard and Reports page."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime

from vaybooks.bms.application.purchases.service import PurchaseAppService
from vaybooks.bms.application.report_filters import PurchasesByVendorFilter
from vaybooks.bms.domain.shared.enums import PurchaseOrderStatus


def _as_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


class PurchaseReportService:
    def __init__(self, purchases: PurchaseAppService):
        self._purchases = purchases

    def dashboard_summary(self) -> dict:
        today = date.today()
        start = today.replace(day=1)
        _, last_day = monthrange(today.year, today.month)
        end = today.replace(day=last_day)

        orders = self._purchases.list_purchase_orders()
        open_pos = [
            po
            for po in orders
            if po.status
            not in (
                PurchaseOrderStatus.CANCELLED,
                PurchaseOrderStatus.CLOSED,
                PurchaseOrderStatus.RECEIVED,
            )
        ]
        pending_grn_qty = 0.0
        for po in orders:
            if po.status == PurchaseOrderStatus.CANCELLED:
                continue
            for line in po.lines:
                pending_grn_qty += line.qty_pending
        pending_grn_qty = round(pending_grn_qty, 2)

        bills = self._purchases.list_purchase_bills()
        purchases_month = 0.0
        returns_month = 0.0
        for row in bills:
            bd = _as_date(row.get("bill_date"))
            if bd and start <= bd <= end:
                purchases_month += float(row.get("total") or 0)

        for ret in self._purchases.list_purchase_returns():
            rd = ret.return_date
            if start <= rd <= end:
                returns_month += ret.total_amount

        return {
            "open_po_count": len(open_pos),
            "pending_grn_qty": pending_grn_qty,
            "purchases_this_month": round(purchases_month, 2),
            "returns_this_month": round(returns_month, 2),
        }

    def purchase_orders_pipeline(self) -> list[dict]:
        rows = []
        today = date.today()
        for po in self._purchases.list_purchase_orders():
            if po.status in (
                PurchaseOrderStatus.CANCELLED,
                PurchaseOrderStatus.CLOSED,
            ):
                continue
            overdue = bool(
                po.expected_date
                and po.expected_date < today
                and po.status != PurchaseOrderStatus.RECEIVED
            )
            rows.append(
                {
                    "po_number": po.po_number,
                    "vendor_name": po.vendor_name,
                    "order_date": po.order_date,
                    "expected_date": po.expected_date,
                    "status": po.status.value,
                    "total_amount": po.total_amount,
                    "overdue": overdue,
                }
            )
        return rows

    def grn_pending(self) -> list[dict]:
        rows = []
        for po in self._purchases.list_purchase_orders():
            if po.status == PurchaseOrderStatus.CANCELLED:
                continue
            for line in po.lines:
                pending = line.qty_pending
                if pending <= 0:
                    continue
                rows.append(
                    {
                        "po_number": po.po_number,
                        "vendor_name": po.vendor_name,
                        "product_name": line.product_name or line.product_id,
                        "qty_ordered": line.qty_ordered,
                        "qty_received": line.qty_received,
                        "qty_pending": pending,
                    }
                )
        return rows

    def purchases_by_vendor(
        self, start: date | None = None, end: date | None = None
    ) -> list[dict]:
        totals: dict[str, dict] = {}
        for row in self._purchases.list_purchase_bills():
            bd = _as_date(row.get("bill_date"))
            if start and bd and bd < start:
                continue
            if end and bd and bd > end:
                continue
            vendor = row.get("vendor_name") or "Unknown"
            bucket = totals.setdefault(
                vendor, {"vendor_name": vendor, "bill_count": 0, "total": 0.0}
            )
            bucket["bill_count"] += 1
            bucket["total"] = round(bucket["total"] + float(row.get("total") or 0), 2)
        return sorted(totals.values(), key=lambda r: r["total"], reverse=True)

    def purchase_returns_summary(
        self, start: date | None = None, end: date | None = None
    ) -> list[dict]:
        rows = []
        for ret in self._purchases.list_purchase_returns():
            if start and ret.return_date < start:
                continue
            if end and ret.return_date > end:
                continue
            rows.append(
                {
                    "return_number": ret.return_number,
                    "vendor_name": ret.vendor_name,
                    "return_date": ret.return_date,
                    "total_amount": ret.total_amount,
                }
            )
        return rows

    def inventory_valuation(self, inventory_service) -> list[dict]:
        products = inventory_service.list_products(active_only=True)
        rows = []
        total_value = 0.0
        for p in products:
            value = round(p.current_qty * p.weighted_avg_cost, 2)
            total_value += value
            rows.append(
                {
                    "sku": p.sku,
                    "name": p.name,
                    "current_qty": p.current_qty,
                    "weighted_avg_cost": p.weighted_avg_cost,
                    "valuation": value,
                }
            )
        return {"rows": rows, "total_valuation": round(total_value, 2)}

    def purchase_orders_pipeline_report(self, filters=None) -> list[dict]:
        return self.purchase_orders_pipeline()

    def grn_pending_report(self, filters=None) -> list[dict]:
        return self.grn_pending()

    def purchases_by_vendor_report(
        self, filters: PurchasesByVendorFilter | None = None
    ) -> list[dict]:
        start = end = None
        if filters and filters.date_range:
            start = filters.date_range.start
            end = filters.date_range.end
        return self.purchases_by_vendor(start, end)

    def purchase_returns_summary_report(
        self, filters: PurchasesByVendorFilter | None = None
    ) -> list[dict]:
        start = end = None
        if filters and filters.date_range:
            start = filters.date_range.start
            end = filters.date_range.end
        return self.purchase_returns_summary(start, end)
