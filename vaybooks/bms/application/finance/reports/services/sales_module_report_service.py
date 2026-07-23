"""Sales module report queries for dashboard and Sales Reports page."""

from __future__ import annotations

from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime, timedelta

from vaybooks.bms.application.report_filters import PurchasesByVendorFilter
from vaybooks.bms.application.sales.service import SalesAppService
from vaybooks.bms.domain.shared.enums import SalesOrderStatus


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


class SalesModuleReportService:
    def __init__(self, sales: SalesAppService):
        self._sales = sales

    def dashboard_summary(
        self, start: date | None = None, end: date | None = None
    ) -> dict:
        if start is None or end is None:
            start, end = _default_month_range()

        orders = self._sales.list_sales_orders()
        open_sos = [
            so
            for so in orders
            if so.status
            not in (
                SalesOrderStatus.CANCELLED,
                SalesOrderStatus.CLOSED,
                SalesOrderStatus.DELIVERED,
            )
        ]
        pending_dn_qty = 0.0
        for so in orders:
            if so.status == SalesOrderStatus.CANCELLED:
                continue
            for line in so.lines:
                pending_dn_qty += float(getattr(line, "qty_pending", 0) or 0)
        pending_dn_qty = round(pending_dn_qty, 2)

        sales_month = 0.0
        for row in self._sales.list_sales_invoices():
            sd = _as_date(row.get("sale_date"))
            if sd and start <= sd <= end:
                sales_month += float(row.get("net") or row.get("gross") or 0)

        returns_month = 0.0
        for ret in self._sales.list_sales_returns():
            rd = ret.return_date
            if start <= rd <= end:
                returns_month += float(ret.total_amount or 0)

        return {
            "open_so_count": len(open_sos),
            "pending_dn_qty": pending_dn_qty,
            "sales_this_month": round(sales_month, 2),
            "returns_this_month": round(returns_month, 2),
        }

    def overdue_so_count(self) -> int:
        return sum(1 for row in self.sales_orders_pipeline() if row.get("overdue"))

    def sales_orders_pipeline(self) -> list[dict]:
        rows = []
        today = date.today()
        for so in self._sales.list_sales_orders():
            if so.status in (
                SalesOrderStatus.CANCELLED,
                SalesOrderStatus.CLOSED,
            ):
                continue
            overdue = bool(
                so.expected_date
                and so.expected_date < today
                and so.status != SalesOrderStatus.DELIVERED
            )
            rows.append(
                {
                    "id": so.id,
                    "so_number": so.so_number,
                    "customer_name": so.customer_name,
                    "order_date": so.order_date,
                    "expected_date": so.expected_date,
                    "status": so.status.value,
                    "total_amount": so.total_amount,
                    "overdue": overdue,
                }
            )
        return rows

    def delivery_pending(self) -> list[dict]:
        rows = []
        for so in self._sales.list_sales_orders():
            if so.status == SalesOrderStatus.CANCELLED:
                continue
            for line in so.lines:
                pending = float(getattr(line, "qty_pending", 0) or 0)
                if pending <= 0:
                    continue
                rows.append(
                    {
                        "id": so.id,
                        "so_number": so.so_number,
                        "customer_name": so.customer_name,
                        "order_date": so.order_date,
                        "product_name": line.product_name or line.product_id,
                        "qty_ordered": line.qty_ordered,
                        "qty_delivered": getattr(line, "qty_delivered", 0),
                        "qty_pending": pending,
                    }
                )
        return rows

    def sales_by_customer(
        self, start: date | None = None, end: date | None = None
    ) -> list[dict]:
        totals: dict[str, dict] = {}
        for row in self._sales.list_sales_invoices():
            sd = _as_date(row.get("sale_date"))
            if start and sd and sd < start:
                continue
            if end and sd and sd > end:
                continue
            customer = row.get("party_name") or row.get("customer_name") or "Unknown"
            bucket = totals.setdefault(
                customer,
                {"customer_name": customer, "invoice_count": 0, "total": 0.0},
            )
            bucket["invoice_count"] += 1
            bucket["total"] = round(
                bucket["total"] + float(row.get("net") or row.get("gross") or 0),
                2,
            )
        return sorted(totals.values(), key=lambda r: r["total"], reverse=True)

    def sales_returns_summary(
        self, start: date | None = None, end: date | None = None
    ) -> list[dict]:
        rows = []
        for ret in self._sales.list_sales_returns():
            if start and ret.return_date < start:
                continue
            if end and ret.return_date > end:
                continue
            rows.append(
                {
                    "return_number": ret.return_number,
                    "customer_name": ret.customer_name,
                    "return_date": ret.return_date,
                    "total_amount": ret.total_amount,
                    "status": ret.status.value if ret.status else "",
                }
            )
        return rows

    def sales_time_series(
        self, start: date, end: date, grain: str = "day"
    ) -> list[dict]:
        if grain not in ("day", "week", "month"):
            grain = "day"
        totals: dict[str, float] = defaultdict(float)
        for row in self._sales.list_sales_invoices():
            sd = _as_date(row.get("sale_date"))
            if not sd or sd < start or sd > end:
                continue
            key = _period_key(sd, grain)
            totals[key] += float(row.get("net") or row.get("gross") or 0)
        return [
            {"period": period, "amount": round(amount, 2)}
            for period, amount in sorted(totals.items())
        ]

    def so_status_breakdown(self) -> list[dict]:
        counts: dict[str, int] = defaultdict(int)
        for so in self._sales.list_sales_orders():
            if so.status in (
                SalesOrderStatus.CANCELLED,
                SalesOrderStatus.CLOSED,
            ):
                continue
            counts[so.status.value] += 1
        return [
            {"status": status, "count": count}
            for status, count in sorted(counts.items(), key=lambda r: r[0])
        ]

    def dn_pending_by_customer(self, limit: int = 10) -> list[dict]:
        totals: dict[str, float] = defaultdict(float)
        for row in self.delivery_pending():
            customer = row.get("customer_name") or "Unknown"
            totals[customer] += float(row.get("qty_pending") or 0)
        ranked = sorted(totals.items(), key=lambda r: r[1], reverse=True)
        if limit > 0:
            ranked = ranked[:limit]
        return [
            {"customer_name": customer, "qty_pending": round(qty, 2)}
            for customer, qty in ranked
        ]

    def sales_vs_returns_series(self, start: date, end: date) -> list[dict]:
        sales: dict[str, float] = defaultdict(float)
        returns: dict[str, float] = defaultdict(float)
        for row in self._sales.list_sales_invoices():
            sd = _as_date(row.get("sale_date"))
            if not sd or sd < start or sd > end:
                continue
            sales[_period_key(sd, "month")] += float(
                row.get("net") or row.get("gross") or 0
            )
        for ret in self._sales.list_sales_returns():
            rd = ret.return_date
            if rd < start or rd > end:
                continue
            returns[_period_key(rd, "month")] += float(ret.total_amount or 0)
        periods = sorted(set(sales) | set(returns))
        return [
            {
                "period": period,
                "sales": round(sales.get(period, 0.0), 2),
                "returns": round(returns.get(period, 0.0), 2),
            }
            for period in periods
        ]

    def sales_orders_pipeline_report(self, filters=None) -> list[dict]:
        return self.sales_orders_pipeline()

    def delivery_pending_report(self, filters=None) -> list[dict]:
        return self.delivery_pending()

    def sales_by_customer_report(
        self, filters: PurchasesByVendorFilter | None = None
    ) -> list[dict]:
        start = end = None
        if filters and filters.date_range:
            start = filters.date_range.start
            end = filters.date_range.end
        return self.sales_by_customer(start, end)

    def sales_returns_summary_report(
        self, filters: PurchasesByVendorFilter | None = None
    ) -> list[dict]:
        start = end = None
        if filters and filters.date_range:
            start = filters.date_range.start
            end = filters.date_range.end
        return self.sales_returns_summary(start, end)
