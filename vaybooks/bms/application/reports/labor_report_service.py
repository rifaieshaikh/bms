from __future__ import annotations

from datetime import date

from vaybooks.bms.application.report_filters import (
    DateRange,
    LaborMphFilter,
    OrderMphFilter,
    TimeTrackingFilter,
    WorkerProductivityFilter,
)
from vaybooks.bms.application.reports._helpers import _as_date, matches_search
from vaybooks.bms.application.reports.profitability_report_service import (
    ProfitabilityReportService,
)
from vaybooks.bms.domain.shared.date_utils import minutes_to_hours
from vaybooks.bms.infrastructure.repositories.mongo_report_repository import (
    MongoReportRepository,
)


class LaborReportService:
    def __init__(self, report_repo: MongoReportRepository):
        self._repo = report_repo
        self._profitability = ProfitabilityReportService(report_repo)

    def time_tracking_report(self, filters: TimeTrackingFilter) -> list:
        entries = self._repo.get_time_entries(
            filters.date_range.start,
            filters.date_range.end,
            worker=filters.worker or None,
            activity_name=filters.activity_name or None,
        )
        rows = []
        for e in entries:
            row = {
                "order_number": e.get("order_number"),
                "bill_number": e.get("bill_number"),
                "activity_name": e.get("activity_name"),
                "work_date": _as_date(e.get("work_date")),
                "start_time": e.get("start_time"),
                "end_time": e.get("end_time"),
                "duration_minutes": e.get("duration_minutes"),
                "worker_name": e.get("worker_name"),
            }
            if not matches_search(
                row, filters.search, "order_number", "bill_number"
            ):
                continue
            rows.append(row)
        return rows

    def worker_productivity_report(
        self, filters: WorkerProductivityFilter
    ) -> list:
        entries = self._repo.get_time_entries(
            filters.date_range.start,
            filters.date_range.end,
        )
        by_worker: dict[str, dict] = {}
        for e in entries:
            worker = (e.get("worker_name") or "Unknown").strip()
            if filters.worker and filters.worker not in worker.lower():
                continue
            bucket = by_worker.setdefault(
                worker,
                {
                    "worker_name": worker,
                    "total_minutes": 0,
                    "entry_count": 0,
                    "orders": set(),
                },
            )
            bucket["total_minutes"] += int(e.get("duration_minutes") or 0)
            bucket["entry_count"] += 1
            if e.get("order_number"):
                bucket["orders"].add(e.get("order_number"))

        rows = []
        for bucket in by_worker.values():
            hours = minutes_to_hours(bucket["total_minutes"])
            if filters.min_hours is not None and hours < filters.min_hours:
                continue
            rows.append(
                {
                    "worker_name": bucket["worker_name"],
                    "total_hours": round(hours, 2),
                    "entry_count": bucket["entry_count"],
                    "order_count": len(bucket["orders"]),
                }
            )
        return rows

    def labor_vs_mph_report(self, filters: LaborMphFilter) -> list:
        labor = self._repo.labor_minutes_by_order(
            filters.date_range.start, filters.date_range.end
        )
        mph_rows = {
            r["order_number"]: r
            for r in self._profitability.mph_report(
                OrderMphFilter(date_range=filters.date_range)
            )
        }
        rows = []
        for order_no, mins in labor.items():
            hours = minutes_to_hours(mins)
            mph_row = mph_rows.get(order_no, {})
            margin = mph_row.get("total_margin", 0)
            mph = mph_row.get("margin_per_hour")
            if filters.min_hours is not None and hours < filters.min_hours:
                continue
            rows.append(
                {
                    "order_number": order_no,
                    "customer_name": mph_row.get("customer_name"),
                    "logged_hours": round(hours, 2),
                    "margin": margin,
                    "mph": mph,
                }
            )
        return rows

    def labor_hours_by_order(
        self, start: date | None = None, end: date | None = None
    ) -> dict:
        return {
            order: minutes_to_hours(mins)
            for order, mins in self._repo.labor_minutes_by_order(start, end).items()
        }
