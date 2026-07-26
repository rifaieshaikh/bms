"""Maps each domain's existing report catalog onto scheduled report runners.

No report logic lives here: every runner calls the same application service the
interactive Reports page uses, so scheduled output always matches on-demand
output.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Callable, Dict, List, Optional

from vaybooks.bms.application.schedulers.reports_protocol import (
    ReportContext,
    ReportDefinition,
    ReportRunResult,
    slugify_report_id,
)
from vaybooks.bms.domain.schedulers.entities import (
    DOMAIN_BOUTIQUE,
    DOMAIN_CRM,
    DOMAIN_INVENTORY,
    DOMAIN_PRODUCTION,
    DOMAIN_ORDER,
    DOMAIN_PROJECTS,
    DOMAIN_PURCHASES,
    DOMAIN_SALES,
)


class ReportSkipped(Exception):
    """Raised when a report cannot run because required inputs are missing."""


@dataclass
class _Entry:
    definition: ReportDefinition
    run: Callable[[ReportContext], Any]


class ReportRegistry:
    def __init__(self) -> None:
        self._entries: Dict[str, _Entry] = {}
        self._by_domain: Dict[str, List[str]] = {d: [] for d in DOMAIN_ORDER}

    @staticmethod
    def _key(domain: str, report_id: str) -> str:
        return f"{domain}:{report_id}"

    def register(
        self, definition: ReportDefinition, run: Callable[[ReportContext], Any]
    ) -> None:
        key = self._key(definition.domain, definition.report_id)
        if key not in self._entries:
            self._by_domain.setdefault(definition.domain, []).append(
                definition.report_id
            )
        self._entries[key] = _Entry(definition=definition, run=run)

    def definitions_for_domain(self, domain: str) -> List[ReportDefinition]:
        ids = self._by_domain.get(domain, [])
        return [self._entries[self._key(domain, rid)].definition for rid in ids]

    def definition(self, domain: str, report_id: str) -> Optional[ReportDefinition]:
        entry = self._entries.get(self._key(domain, report_id))
        return entry.definition if entry else None

    def run(self, ctx: ReportContext) -> ReportRunResult:
        entry = self._entries.get(self._key(ctx.domain, ctx.report_id))
        if entry is None:
            raise ReportSkipped(
                f"No runner registered for {ctx.domain}/{ctx.report_id}"
            )
        rows = entry.run(ctx)
        if isinstance(rows, ReportRunResult):
            return rows
        return ReportRunResult(rows=_normalise_rows(rows))


def _normalise_rows(payload: Any) -> List[Dict[str, Any]]:
    """Coerce a service response into CSV-friendly dict rows."""
    if payload is None:
        return []
    if isinstance(payload, dict):
        for key in ("rows", "items", "entries", "lines"):
            nested = payload.get(key)
            if isinstance(nested, list):
                return [_as_row(r) for r in nested]
        return [_as_row(payload)]
    if isinstance(payload, list):
        return [_as_row(r) for r in payload]
    return [_as_row(payload)]


def _as_row(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return {k: v for k, v in value.items() if not isinstance(v, (list, dict)) or True}
    if hasattr(value, "__dict__"):
        return dict(vars(value))
    return {"value": value}


def _date_range_filters(ctx: ReportContext) -> Dict[str, Any]:
    if ctx.start and ctx.end:
        return {"date_range": (ctx.start, ctx.end)}
    return {}


def _ui_filters(ctx: ReportContext) -> Dict[str, Any]:
    """Committed filter-bar state expected by ``build_report_filter``."""
    filters = {
        k: v
        for k, v in (ctx.filters or {}).items()
        if k not in ("range_key", "range_days")
    }
    filters.update(_date_range_filters(ctx))
    return filters


def build_report_registry(services: Dict[str, Any]) -> ReportRegistry:
    registry = ReportRegistry()
    _register_crm(registry, services)
    _register_sales(registry, services)
    _register_purchases(registry, services)
    _register_inventory(registry, services)
    _register_production(registry, services)
    _register_boutique(registry, services)
    _register_projects(registry, services)
    return registry


# --- CRM ---------------------------------------------------------------------


def _register_crm(registry: ReportRegistry, services: Dict[str, Any]) -> None:
    from vaybooks.bms.domain.crm.enums import CRM_REPORT_DEFINITIONS

    def make_runner(report_id: str):
        def run(ctx: ReportContext) -> Any:
            svc = services.get("crm_reports")
            if svc is None:
                raise ReportSkipped("CRM reports service is unavailable")
            from datetime import datetime, time as dt_time

            from vaybooks.bms.application.crm.reports import CrmReportFilters

            filters = CrmReportFilters(
                date_from=(
                    datetime.combine(ctx.start, dt_time.min) if ctx.start else None
                ),
                date_to=datetime.combine(ctx.end, dt_time.max) if ctx.end else None,
                branch=str(ctx.option("branch", "") or ""),
                assigned_user_id=str(ctx.option("assigned_user_id", "") or ""),
                customer_id=str(ctx.option("customer_id", "") or ""),
                area=str(ctx.option("area", "") or ""),
                activity_type=str(ctx.option("activity_type", "") or ""),
            )
            inactivity = ctx.option("inactivity_days")
            if inactivity:
                filters.inactivity_days = int(inactivity)
            threshold = ctx.option("high_value_threshold")
            if threshold:
                filters.high_value_threshold = float(threshold)
            result = svc.run_report(report_id, filters)
            return list(getattr(result, "rows", []) or [])

        return run

    for report_id, title, category in CRM_REPORT_DEFINITIONS:
        registry.register(
            ReportDefinition(
                domain=DOMAIN_CRM,
                report_id=report_id,
                title=title,
                category=category,
            ),
            make_runner(report_id),
        )


# --- Title-keyed modules -----------------------------------------------------


def _register_schema_module(
    registry: ReportRegistry,
    services: Dict[str, Any],
    *,
    domain: str,
    service_key: str,
    titles: List[str],
    methods: Dict[str, str],
    service_label: str,
) -> None:
    from vaybooks.bms.ui.components.common.report_filters import build_report_filter

    def make_runner(title: str, method_name: str):
        def run(ctx: ReportContext) -> Any:
            svc = services.get(service_key)
            if svc is None:
                raise ReportSkipped(f"{service_label} is unavailable")
            method = getattr(svc, method_name, None)
            if method is None:
                raise ReportSkipped(f"{service_label} cannot run {title}")
            try:
                service_filters = build_report_filter(title, _ui_filters(ctx))
            except KeyError:
                service_filters = None
            return method(service_filters)

        return run

    for title in titles:
        method_name = methods.get(title)
        if not method_name:
            continue
        registry.register(
            ReportDefinition(
                domain=domain,
                report_id=slugify_report_id(title),
                title=title,
            ),
            make_runner(title, method_name),
        )


def _register_sales(registry: ReportRegistry, services: Dict[str, Any]) -> None:
    from vaybooks.bms.ui.report_schemas import SALES_MODULE_REPORT_TYPES

    _register_schema_module(
        registry,
        services,
        domain=DOMAIN_SALES,
        service_key="reports_sales_module",
        titles=list(SALES_MODULE_REPORT_TYPES),
        methods={
            "Sales Orders Pipeline": "sales_orders_pipeline_report",
            "Delivery Pending": "delivery_pending_report",
            "Sales by Customer": "sales_by_customer_report",
            "Sales Returns Summary": "sales_returns_summary_report",
        },
        service_label="Sales reports service",
    )


def _register_purchases(registry: ReportRegistry, services: Dict[str, Any]) -> None:
    from vaybooks.bms.ui.report_schemas import PURCHASE_MODULE_REPORT_TYPES

    _register_schema_module(
        registry,
        services,
        domain=DOMAIN_PURCHASES,
        service_key="reports_purchases",
        titles=list(PURCHASE_MODULE_REPORT_TYPES),
        methods={
            "Purchase Orders Pipeline": "purchase_orders_pipeline_report",
            "GRN Pending": "grn_pending_report",
            "Purchases by Vendor": "purchases_by_vendor_report",
            "Purchase Returns Summary": "purchase_returns_summary_report",
        },
        service_label="Purchase reports service",
    )


def _register_inventory(registry: ReportRegistry, services: Dict[str, Any]) -> None:
    from vaybooks.bms.ui.report_schemas import INVENTORY_REPORT_TYPES

    _register_schema_module(
        registry,
        services,
        domain=DOMAIN_INVENTORY,
        service_key="reports_inventory",
        titles=list(INVENTORY_REPORT_TYPES),
        methods={
            "Stock on Hand": "stock_on_hand_report",
            "Stock by Location": "stock_by_location_report",
            "Low Stock Alert": "low_stock_report",
            "Stock Movements": "stock_movements_report",
            "Inventory Valuation": "inventory_valuation_report",
            "Category Stock Summary": "category_stock_summary_report",
            "Dead / Slow-Moving Stock": "dead_stock_report",
            "Stock Movement Summary": "stock_movement_summary_report",
            "Cost vs Selling (Stock Margin)": "stock_margin_report",
            "Opening → Closing Stock": "opening_closing_stock_report",
            "HSN Stock Summary": "hsn_stock_summary_report",
            "Fast-Moving Stock": "fast_moving_stock_report",
            "Customer Latest Prices": "customer_latest_prices_report",
            "Inactive Products with Stock": "inactive_products_with_stock_report",
            "Product Rate Card": "product_rate_card_report",
        },
        service_label="Inventory reports service",
    )


def _register_production(registry: ReportRegistry, services: Dict[str, Any]) -> None:
    from vaybooks.bms.ui.report_schemas import PRODUCTION_REPORT_TYPES

    _register_schema_module(
        registry,
        services,
        domain=DOMAIN_PRODUCTION,
        service_key="reports_production",
        titles=list(PRODUCTION_REPORT_TYPES),
        methods={
            "Batch Register": "batch_register_report",
            "Batch Cost Sheet": "batch_cost_sheet_report",
            "Batch Margin": "batch_margin_report",
            "Yield vs Recipe (variance)": "yield_variance_report",
            "Production Expenses (by type / activity)": "production_expense_report",
            "Output Summary (by product / period)": "output_summary_report",
            "RM Consumption": "rm_consumption_report",
            "WIP / Unposted Batches": "wip_open_batches_report",
            "Cost per Unit Trend": "cost_per_unit_trend_report",
            "Recipe Master List": "recipe_master_report",
        },
        service_label="Production reports service",
    )

    def run_batch_cost_sheet(ctx: ReportContext) -> Any:
        batch_id = str(ctx.option("batch_id", "") or "")
        if not batch_id:
            raise ReportSkipped(
                "Batch Cost Sheet needs a production batch selected in the filters"
            )
        service = services.get("reports_production")
        if service is None:
            raise ReportSkipped("Production reports service is unavailable")
        filters = dict(ctx.filters or {})
        filters["batch_id"] = batch_id
        if ctx.start and ctx.end:
            filters["date_range"] = (ctx.start, ctx.end)
        return service.batch_cost_sheet_report(filters)

    registry.register(
        ReportDefinition(
            domain=DOMAIN_PRODUCTION,
            report_id=slugify_report_id("Batch Cost Sheet"),
            title="Batch Cost Sheet",
        ),
        run_batch_cost_sheet,
    )


def _register_boutique(registry: ReportRegistry, services: Dict[str, Any]) -> None:
    from vaybooks.bms.ui.report_schemas import BOUTIQUE_REPORT_TYPES

    _register_schema_module(
        registry,
        services,
        domain=DOMAIN_BOUTIQUE,
        service_key="reports_boutique_module",
        titles=list(BOUTIQUE_REPORT_TYPES),
        methods={
            "Order Pipeline": "order_pipeline_report",
            "Overdue Orders": "overdue_order_report",
            "Bills Pending Invoice": "bills_pending_invoice_report",
            "Activity Pending": "activity_pending_report",
            "Activity Bottleneck": "activity_bottleneck_report",
            "Delivery Performance": "delivery_performance_report",
            "Completed Orders": "completed_order_report",
            "Time Tracking": "time_tracking_report",
            "Employee Productivity": "worker_productivity_report",
            "Labor vs MPH": "labor_vs_mph_report",
        },
        service_label="Boutique reports service",
    )

    # Customer Order History is per-customer; it is schedulable only when the
    # saved filter profile pins a customer.
    def run_customer_history(ctx: ReportContext) -> Any:
        customer_id = str(ctx.option("customer_id", "") or "")
        if not customer_id:
            raise ReportSkipped(
                "Customer Order History needs a customer selected in the filters"
            )
        svc = services.get("reports_customers")
        if svc is None:
            raise ReportSkipped("Customer reports service is unavailable")
        from vaybooks.bms.ui.components.common.report_filters import build_report_filter

        service_filters = build_report_filter(
            "Customer Order History", _ui_filters(ctx), customer_id=customer_id
        )
        return svc.customer_order_history(service_filters)

    registry.register(
        ReportDefinition(
            domain=DOMAIN_BOUTIQUE,
            report_id=slugify_report_id("Customer Order History"),
            title="Customer Order History",
        ),
        run_customer_history,
    )


# --- Projects ----------------------------------------------------------------

# Portfolio Summary spans every project; the rest need a project pinned in the
# saved filter profile.
_PROJECT_PORTFOLIO_METHOD = "portfolio_summary"
_PROJECT_SCOPED_METHODS: Dict[str, str] = {
    "Activity Profitability": "activity_profitability",
    "Man-hours by Worker": "man_hours_by_worker",
    "Unallocated Costs": "unallocated_costs",
    "WIP / Unbilled Cost": "wip_unbilled",
    "Billing Register": "billing_register",
    "Customer Outstanding": "customer_outstanding",
    "Vendor Payables": "vendor_payables",
    "Quotation Pipeline": "quotation_pipeline",
    "Retention Register": "retention_register",
    "Collections & Outstanding": "collections_outstanding",
    "At-Risk Projects": "at_risk",
    "Variations Log": "variations_log",
    "Cost Transfers": "transfers",
    "Write-offs": "write_offs",
    "TDS Deducted": "tds_deducted",
    "PO Committed Cost": "po_committed",
    "Document Inventory": "document_inventory",
    "BOQ Status": "boq_status_report",
    "Measurement Register": "measurement_register",
    "RA Register (Claimed vs Certified)": "ra_register_dual",
    "Budget vs Actual": "budget_vs_actual",
}


def _register_projects(registry: ReportRegistry, services: Dict[str, Any]) -> None:
    def run_portfolio(ctx: ReportContext) -> Any:
        svc = services.get("reports_projects")
        if svc is None:
            raise ReportSkipped("Project reports service is unavailable")
        return getattr(svc, _PROJECT_PORTFOLIO_METHOD)()

    registry.register(
        ReportDefinition(
            domain=DOMAIN_PROJECTS,
            report_id=slugify_report_id("Portfolio Summary"),
            title="Portfolio Summary",
            supports_date_range=False,
        ),
        run_portfolio,
    )

    def make_scoped(title: str, method_name: str):
        def run(ctx: ReportContext) -> Any:
            svc = services.get("reports_projects")
            if svc is None:
                raise ReportSkipped("Project reports service is unavailable")
            project_id = str(ctx.option("project_id", "") or "")
            if not project_id:
                raise ReportSkipped(
                    f"{title} needs a project selected in the filters"
                )
            method = getattr(svc, method_name, None)
            if method is None:
                raise ReportSkipped(f"Project reports service cannot run {title}")
            return method(project_id)

        return run

    for title, method_name in _PROJECT_SCOPED_METHODS.items():
        registry.register(
            ReportDefinition(
                domain=DOMAIN_PROJECTS,
                report_id=slugify_report_id(title),
                title=title,
                supports_date_range=False,
            ),
            make_scoped(title, method_name),
        )


__all__ = [
    "ReportRegistry",
    "ReportSkipped",
    "build_report_registry",
    "date",
]
