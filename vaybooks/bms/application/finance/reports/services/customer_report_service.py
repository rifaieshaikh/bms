from __future__ import annotations

from vaybooks.bms.application.report_filters import CustomerHistoryFilter
from vaybooks.bms.application.finance.reports.services._helpers import _as_date
from vaybooks.bms.infrastructure.repositories.finance.mongo_report_repository import (
    MongoReportRepository,
)


class CustomerReportService:
    def __init__(self, report_repo: MongoReportRepository):
        self._repo = report_repo

    def customer_order_history(self, filters: CustomerHistoryFilter) -> list:
        orders = self._repo.get_customer_orders(
            filters.customer_id,
            filters.date_range.start,
            filters.date_range.end,
        )
        rows = []
        for o in orders:
            status = o.get("order_status")
            if filters.statuses and status not in filters.statuses:
                continue
            rows.append(
                {
                    "order_number": o.get("order_number"),
                    "order_date": _as_date(o.get("order_date")),
                    "order_status": status,
                    "expected_delivery_date": _as_date(
                        o.get("expected_delivery_date")
                    ),
                    "advance_amount": o.get("advance_amount"),
                }
            )
        return rows
