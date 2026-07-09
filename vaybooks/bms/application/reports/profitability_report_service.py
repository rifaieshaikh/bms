from __future__ import annotations

from vaybooks.bms.application.report_filters import (
    ItemProfitabilityFilter,
    OrderMphFilter,
)
from vaybooks.bms.application.reports._helpers import (
    _as_date,
    matches_search,
    passes_min_mph,
)
from vaybooks.bms.infrastructure.repositories.mongo_report_repository import (
    MongoReportRepository,
)


class ProfitabilityReportService:
    def __init__(self, report_repo: MongoReportRepository):
        self._repo = report_repo

    def item_profitability_report(self, filters: ItemProfitabilityFilter) -> list:
        items = self._repo.get_item_profitability(
            filters.date_range.start, filters.date_range.end
        )
        rows = []
        for it in items:
            row = {
                "order_number": it.get("order_number"),
                "customer_name": it.get("customer_name"),
                "bill_number": it.get("bill_number"),
                "description": it.get("description"),
                "revenue_net": it.get("sell_amount"),
                "expense_selling": it.get("expense_selling_total"),
                "expense_purchase": it.get("expense_purchase_total"),
                "in_house_hours": it.get("in_house_hours"),
                "margin_amount": it.get("margin_amount"),
                "margin_per_hour": it.get("margin_per_hour"),
                "delivered_on": _as_date(it.get("delivered_on")),
            }
            if not matches_search(row, filters.customer_query, "customer_name"):
                continue
            if not matches_search(
                row, filters.bill_query, "bill_number", "order_number"
            ):
                continue
            mph = row.get("margin_per_hour")
            if filters.min_mph is not None and not passes_min_mph(mph, filters.min_mph):
                continue
            margin = row.get("margin_amount") or 0
            if filters.min_margin is not None and margin < filters.min_margin:
                continue
            rows.append(row)
        return rows

    def mph_report(self, filters: OrderMphFilter) -> list:
        items = self._repo.get_item_profitability(
            filters.date_range.start, filters.date_range.end
        )
        by_order: dict[str, dict] = {}
        for it in items:
            order_no = it.get("order_number") or ""
            if filters.customer_query:
                customer = (it.get("customer_name") or "").lower()
                if filters.customer_query not in customer:
                    continue
            bucket = by_order.setdefault(
                order_no,
                {
                    "order_number": order_no,
                    "customer_name": it.get("customer_name"),
                    "item_count": 0,
                    "total_margin": 0.0,
                    "total_hours": 0.0,
                    "delivered_through": None,
                },
            )
            bucket["item_count"] += 1
            bucket["total_margin"] += float(it.get("margin_amount") or 0)
            bucket["total_hours"] += float(it.get("in_house_hours") or 0)
            snap = _as_date(it.get("delivered_on"))
            if snap and (
                bucket["delivered_through"] is None
                or snap > bucket["delivered_through"]
            ):
                bucket["delivered_through"] = snap

        rows = []
        for bucket in by_order.values():
            hours = bucket["total_hours"]
            mph = round(bucket["total_margin"] / hours, 2) if hours > 0 else None
            if filters.min_mph is not None and not passes_min_mph(mph, filters.min_mph):
                continue
            rows.append(
                {
                    **bucket,
                    "total_margin": round(bucket["total_margin"], 2),
                    "total_hours": round(hours, 2),
                    "margin_per_hour": mph,
                }
            )
        return rows
