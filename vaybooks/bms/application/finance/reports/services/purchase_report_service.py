"""Purchase report queries for dashboard and Reports page."""

from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime, timedelta

from vaybooks.bms.application.purchases.service import PurchaseAppService
from vaybooks.bms.application.report_filters import PurchasesByVendorFilter
from vaybooks.bms.domain.shared.enums import PurchaseOrderStatus


def _as_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _default_month_range(today: date | None = None) -> tuple[date, date]:
    today = today or date.today()
    start = today.replace(day=1)
    _, last_day = monthrange(today.year, today.month)
    end = today.replace(day=last_day)
    return start, end


def _period_key(d: date, grain: str) -> str:
    if grain == "week":
        monday = d - timedelta(days=d.weekday())
        return monday.isoformat()
    if grain == "month":
        return f"{d.year:04d}-{d.month:02d}"
    return d.isoformat()


class PurchaseReportService:
    def __init__(self, purchases: PurchaseAppService):
        self._purchases = purchases

    def dashboard_summary(
        self, start: date | None = None, end: date | None = None
    ) -> dict:
        if start is None or end is None:
            start, end = _default_month_range()

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

    def overdue_po_count(self) -> int:
        return sum(1 for row in self.purchase_orders_pipeline() if row.get("overdue"))

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
                    "id": po.id,
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
                        "id": po.id,
                        "po_number": po.po_number,
                        "vendor_name": po.vendor_name,
                        "order_date": po.order_date,
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

    def spend_time_series(
        self, start: date, end: date, grain: str = "day"
    ) -> list[dict]:
        if grain not in ("day", "week", "month"):
            grain = "day"
        totals: dict[str, float] = defaultdict(float)
        for row in self._purchases.list_purchase_bills():
            bd = _as_date(row.get("bill_date"))
            if not bd or bd < start or bd > end:
                continue
            key = _period_key(bd, grain)
            totals[key] += float(row.get("total") or 0)
        return [
            {"period": period, "amount": round(amount, 2)}
            for period, amount in sorted(totals.items())
        ]

    def po_status_breakdown(self) -> list[dict]:
        counts: dict[str, int] = defaultdict(int)
        for po in self._purchases.list_purchase_orders():
            if po.status in (
                PurchaseOrderStatus.CANCELLED,
                PurchaseOrderStatus.CLOSED,
            ):
                continue
            counts[po.status.value] += 1
        return [
            {"status": status, "count": count}
            for status, count in sorted(counts.items(), key=lambda r: r[0])
        ]

    def grn_pending_by_vendor(self, limit: int = 10) -> list[dict]:
        totals: dict[str, float] = defaultdict(float)
        for row in self.grn_pending():
            vendor = row.get("vendor_name") or "Unknown"
            totals[vendor] += float(row.get("qty_pending") or 0)
        ranked = sorted(totals.items(), key=lambda r: r[1], reverse=True)
        if limit > 0:
            ranked = ranked[:limit]
        return [
            {"vendor_name": vendor, "qty_pending": round(qty, 2)}
            for vendor, qty in ranked
        ]

    def purchases_vs_returns_series(
        self, start: date, end: date
    ) -> list[dict]:
        purchases: dict[str, float] = defaultdict(float)
        returns: dict[str, float] = defaultdict(float)
        for row in self._purchases.list_purchase_bills():
            bd = _as_date(row.get("bill_date"))
            if not bd or bd < start or bd > end:
                continue
            purchases[_period_key(bd, "month")] += float(row.get("total") or 0)
        for ret in self._purchases.list_purchase_returns():
            rd = ret.return_date
            if rd < start or rd > end:
                continue
            returns[_period_key(rd, "month")] += float(ret.total_amount or 0)
        periods = sorted(set(purchases) | set(returns))
        return [
            {
                "period": period,
                "purchases": round(purchases.get(period, 0.0), 2),
                "returns": round(returns.get(period, 0.0), 2),
            }
            for period in periods
        ]

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

    def purchase_gst_line_items(
        self, start: date | None = None, end: date | None = None
    ) -> list[dict]:
        """Flatten purchase bill lines for GST calculation / CSV export."""
        party_cache: dict[str, dict] = {}

        def _party_facts(vendor_id: str | None) -> dict:
            key = vendor_id or ""
            if key in party_cache:
                return party_cache[key]
            facts_fn = getattr(self._purchases, "party_gst_facts", None)
            if callable(facts_fn) and key:
                facts = facts_fn(key) or {}
            else:
                facts = {"gstin": "", "place_of_supply": ""}
            party_cache[key] = {
                "gstin": (facts.get("gstin") or "").strip(),
                "place_of_supply": facts.get("place_of_supply") or "",
            }
            return party_cache[key]

        rows: list[dict] = []
        for bill in self._purchases.list_purchase_bills():
            line_items = bill.get("line_items") or []
            if not line_items:
                continue
            bd = _as_date(bill.get("bill_date"))
            if start and bd and bd < start:
                continue
            if end and bd and bd > end:
                continue

            party = _party_facts(bill.get("vendor_id"))
            gstin = party["gstin"]
            supply_type = "B2B" if gstin else "B2C"
            document_number = (
                bill.get("vendor_bill_number")
                or bill.get("voucher_number")
                or ""
            )
            party_name = bill.get("vendor_name") or ""

            for item in line_items:
                taxable = round(float(item.get("taxable_amount") or 0), 2)
                cgst = round(float(item.get("cgst_amount") or 0), 2)
                sgst = round(float(item.get("sgst_amount") or 0), 2)
                igst = round(float(item.get("igst_amount") or 0), 2)
                utgst = round(float(item.get("utgst_amount") or 0), 2)
                tax_total = round(cgst + sgst + igst + utgst, 2)
                if item.get("gst_rate") is not None and float(item.get("gst_rate") or 0):
                    gst_rate = round(float(item.get("gst_rate") or 0), 2)
                elif taxable > 0 and tax_total > 0:
                    gst_rate = round(tax_total / taxable * 100.0, 2)
                else:
                    gst_rate = 0.0
                line_total = round(
                    float(
                        item.get("line_total")
                        or item.get("amount")
                        or (taxable + tax_total)
                    ),
                    2,
                )
                rows.append(
                    {
                        "document_type": "Purchase Bill",
                        "document_number": document_number,
                        "document_date": bd,
                        "party_name": party_name,
                        "party_gstin": gstin,
                        "place_of_supply": party["place_of_supply"],
                        "supply_type": supply_type,
                        "item_name": item.get("item_name")
                        or item.get("description")
                        or "",
                        "hsn_sac": item.get("hsn_sac") or "",
                        "qty": float(item.get("qty") or 0),
                        "rate": float(item.get("rate") or 0),
                        "taxable_amount": taxable,
                        "gst_rate": gst_rate,
                        "cgst_amount": cgst,
                        "sgst_amount": sgst,
                        "igst_amount": igst,
                        "utgst_amount": utgst,
                        "line_total": line_total,
                    }
                )
        return rows

    def purchase_gst_line_items_report(
        self, filters: PurchasesByVendorFilter | None = None
    ) -> list[dict]:
        start = end = None
        if filters and filters.date_range:
            start = filters.date_range.start
            end = filters.date_range.end
        return self.purchase_gst_line_items(start, end)
