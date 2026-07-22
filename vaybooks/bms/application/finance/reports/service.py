from calendar import monthrange

from datetime import date

from vaybooks.bms.application.dtos import DashboardSummary
from vaybooks.bms.application.report_filters import (
    ActivityPendingFilter,
    CompletedFilter,
    CustomerHistoryFilter,
    DateRange,
    ExpenseFilter,
    ItemProfitabilityFilter,
    OrderMphFilter,
    OverdueFilter,
    TimeTrackingFilter,
)
from vaybooks.bms.application.finance.reports.services.business_insights_report_service import (
    BusinessInsightsReportService,
)
from vaybooks.bms.application.finance.reports.services.customer_report_service import (
    CustomerReportService,
)
from vaybooks.bms.application.finance.reports.services.labor_report_service import LaborReportService
from vaybooks.bms.application.finance.reports.services.operations_report_service import (
    OperationsReportService,
)
from vaybooks.bms.application.finance.reports.services.profitability_report_service import (
    ProfitabilityReportService,
)
from vaybooks.bms.application.finance.reports.services.inventory_report_service import (
    InventoryReportService,
)
from vaybooks.bms.application.finance.reports.services.sales_report_service import SalesReportService
from vaybooks.bms.domain.shared.enums import OrderStatus
from vaybooks.bms.infrastructure.repositories.finance.mongo_report_repository import (
    MongoReportRepository,
)


class ReportAppService:
    """Facade delegating to category report services (backward compatible)."""

    def __init__(
        self,
        report_repo: MongoReportRepository,
        business: BusinessInsightsReportService,
        profitability: ProfitabilityReportService,
        operations: OperationsReportService,
        labor: LaborReportService,
        customers: CustomerReportService,
        sales: SalesReportService | None = None,
        inventory_reports: InventoryReportService | None = None,
    ):
        self._repo = report_repo
        self._business = business
        self._profitability = profitability
        self._operations = operations
        self._labor = labor
        self._customers = customers
        self._sales = sales or SalesReportService(report_repo)
        self._inventory_reports = inventory_reports

    def get_dashboard_summary(self) -> DashboardSummary:
        today = date.today()
        start = today.replace(day=1)
        _, last_day = monthrange(today.year, today.month)
        end = today.replace(day=last_day)
        active_statuses = [
            OrderStatus.IN_PROGRESS.value,
            OrderStatus.READY_FOR_DELIVERY.value,
            OrderStatus.INVOICE_GENERATED.value,
        ]
        active = self._repo.count_orders_by_statuses(
            active_statuses + [OrderStatus.COMPLETED.value]
        )
        pending_activity_orders = self._repo.count_orders_by_statuses(active_statuses)
        in_progress = self._repo.get_orders_by_statuses(active_statuses, limit=60)
        item_snapshot = self._repo.item_delivery_snapshot()
        inv = (
            self._inventory_reports.health_summary()
            if self._inventory_reports is not None
            else {}
        )
        return DashboardSummary(
            active_orders=active,
            pending_activity_orders=pending_activity_orders,
            ready_for_delivery=0,
            invoice_generated=0,
            completed_orders=self._repo.count_orders_by_status(
                OrderStatus.COMPLETED.value
            ),
            delivered_this_month=self._repo.count_delivered_this_month(start, end),
            total_advance_this_month=self._repo.get_monthly_advance_total(start, end),
            total_invoice_this_month=self._repo.get_monthly_invoice_total(start, end),
            total_pending_activities=self._repo.get_pending_activities_count(),
            bills_pending_invoice=self._repo.get_bills_pending_invoice_count(),
            items_pending=item_snapshot["not_delivered"],
            items_awaiting_delivery=item_snapshot["awaiting"],
            etd_today=self._repo.get_etd_today(today),
            overdue_orders=self._repo.get_overdue_orders(today),
            ready_orders=[],
            in_progress_orders=in_progress,
            recently_completed=self._repo.get_orders_by_status(
                OrderStatus.COMPLETED.value, limit=20
            ),
            recently_delivered=self._repo.get_delivered_this_month(start, end),
            inventory_active_products=inv.get("active_products", 0),
            inventory_total_units=inv.get("total_units", 0.0),
            inventory_stock_value=inv.get("stock_value", 0.0),
            inventory_low_stock_count=inv.get("low_stock_count", 0),
            inventory_out_of_stock_count=inv.get("out_of_stock_count", 0),
            inventory_movements_this_month=inv.get("movements_this_month", 0),
            inventory_low_stock_items=inv.get("low_stock_items", []),
        )

    def get_period_summary(self, start: date, end: date) -> dict:
        return self._business.get_period_summary(start, end)

    def get_sales_summary(self, start: date, end: date) -> dict:
        return self._sales.get_sales_summary(start, end)

    def item_profitability_report(self, filters: ItemProfitabilityFilter) -> list:
        return self._profitability.item_profitability_report(filters)

    def mph_report(self, filters: OrderMphFilter) -> list:
        return self._profitability.mph_report(filters)

    def labor_hours_by_order(self, start: date | None = None, end: date | None = None) -> dict:
        return self._labor.labor_hours_by_order(start, end)

    def activity_pending_report(self, filters: ActivityPendingFilter) -> list:
        return self._operations.activity_pending_report(filters)

    def time_tracking_report(self, filters: TimeTrackingFilter) -> list:
        return self._labor.time_tracking_report(filters)

    def expense_report(self, filters: ExpenseFilter) -> list:
        return self._business.expense_detail_report(filters)

    def customer_order_history(self, filters: CustomerHistoryFilter) -> list:
        return self._customers.customer_order_history(filters)

    def overdue_order_report(self, filters: OverdueFilter) -> list:
        return self._operations.overdue_order_report(filters)

    def completed_order_report(self, filters: CompletedFilter) -> list:
        return self._operations.completed_order_report(filters)

    def delivered_order_report(self, filters: CompletedFilter) -> list:
        return self.completed_order_report(filters)

    def order_profitability_report(self) -> list:
        today = date.today()
        return self.item_profitability_report(
            ItemProfitabilityFilter(date_range=DateRange(today.replace(day=1), today))
        )
