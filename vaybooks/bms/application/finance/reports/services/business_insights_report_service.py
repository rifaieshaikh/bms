from __future__ import annotations

from datetime import date
from typing import Any

from vaybooks.bms.application.finance.accounting.service import AccountingAppService
from vaybooks.bms.application.parties.customers.service import CustomerAppService
from vaybooks.bms.application.report_filters import (
    CashMovementFilter,
    CustomerSegmentsFilter,
    DateRange,
    ExpenseBySourceFilter,
    ExpenseFilter,
    OutstandingFilter,
    PeriodSummaryFilter,
    TopCustomersFilter,
)
from vaybooks.bms.application.finance.reports.services._helpers import (
    flatten_period_summary,
    matches_search,
)
from vaybooks.bms.application.finance.reports.services.profitability_report_service import (
    ProfitabilityReportService,
)
from vaybooks.bms.application.parties.vendors.service import VendorAppService
from vaybooks.bms.infrastructure.repositories.finance.mongo_report_repository import (
    MongoReportRepository,
)


class BusinessInsightsReportService:
    def __init__(
        self,
        report_repo: MongoReportRepository,
        accounting_service: AccountingAppService,
        vendor_service: VendorAppService,
        customer_service: CustomerAppService,
    ):
        self._repo = report_repo
        self._accounting = accounting_service
        self._vendors = vendor_service
        self._customers = customer_service
        self._profitability = ProfitabilityReportService(report_repo)

    def get_period_summary(self, start: date, end: date) -> dict[str, Any]:
        from vaybooks.bms.application.finance.reports.services.period_summary import build_period_summary

        return build_period_summary(self._repo, start, end)

    def period_financial_summary(self, filters: PeriodSummaryFilter) -> list:
        summary = self.get_period_summary(
            filters.date_range.start, filters.date_range.end
        )
        return flatten_period_summary(summary)

    def top_customers_by_revenue(self, filters: TopCustomersFilter) -> list:
        return self._rollup_customers(filters, sort_margin=False)

    def top_customers_by_margin(self, filters: TopCustomersFilter) -> list:
        return self._rollup_customers(filters, sort_margin=True)

    def _rollup_customers(
        self, filters: TopCustomersFilter, *, sort_margin: bool
    ) -> list:
        from vaybooks.bms.application.report_filters import ItemProfitabilityFilter

        items = self._profitability.item_profitability_report(
            ItemProfitabilityFilter(date_range=filters.date_range)
        )
        by_customer: dict[str, dict] = {}
        orders_seen: dict[str, set] = {}
        for it in items:
            name = it.get("customer_name") or "Unknown"
            bucket = by_customer.setdefault(
                name,
                {
                    "customer_name": name,
                    "item_count": 0,
                    "total_revenue": 0.0,
                    "total_margin": 0.0,
                    "total_hours": 0.0,
                    "order_count": 0,
                },
            )
            bucket["item_count"] += 1
            bucket["total_revenue"] += float(it.get("revenue_net") or 0)
            bucket["total_margin"] += float(it.get("margin_amount") or 0)
            bucket["total_hours"] += float(it.get("in_house_hours") or 0)
            order_no = it.get("order_number")
            if order_no:
                orders_seen.setdefault(name, set()).add(order_no)

        rows = []
        for name, bucket in by_customer.items():
            bucket["order_count"] = len(orders_seen.get(name, set()))
            hours = bucket["total_hours"]
            avg_mph = (
                round(bucket["total_margin"] / hours, 2) if hours > 0 else None
            )
            if filters.min_revenue is not None and bucket["total_revenue"] < filters.min_revenue:
                continue
            if filters.min_margin is not None and bucket["total_margin"] < filters.min_margin:
                continue
            rows.append(
                {
                    "customer_name": name,
                    "order_count": bucket["order_count"],
                    "item_count": bucket["item_count"],
                    "total_revenue": round(bucket["total_revenue"], 2),
                    "total_margin": round(bucket["total_margin"], 2),
                    "avg_mph": avg_mph,
                }
            )
        return rows

    def customer_outstanding_report(self, filters: OutstandingFilter) -> list:
        customer_map = {
            c.id: c.customer_name for c in self._customers.list_all_customers()
        }
        rows = []
        for acc in self._accounting.list_accounts(active_only=False):
            if not acc.linked_customer_id:
                continue
            balance = acc.current_balance
            if balance <= 0:
                continue
            if filters.min_balance is not None and balance < filters.min_balance:
                continue
            customer_name = customer_map.get(
                acc.linked_customer_id, acc.account_name
            )
            if filters.search and filters.search not in customer_name.lower():
                continue
            rows.append(
                {
                    "customer_name": customer_name,
                    "account_name": acc.account_name,
                    "balance_due": round(balance, 2),
                }
            )
        return rows

    def vendor_payables_report(self, filters: OutstandingFilter) -> list:
        vendor_map = {v.id: v.vendor_name for v in self._vendors.list_all_vendors()}
        rows = []
        for acc in self._accounting.list_accounts(active_only=False):
            if not acc.linked_vendor_id:
                continue
            balance = acc.current_balance
            payable = abs(balance) if balance < 0 else 0
            if payable <= 0:
                continue
            if filters.min_balance is not None and payable < filters.min_balance:
                continue
            vendor_name = vendor_map.get(acc.linked_vendor_id, acc.account_name)
            if filters.search and filters.search not in vendor_name.lower():
                continue
            rows.append(
                {
                    "vendor_name": vendor_name,
                    "account_name": acc.account_name,
                    "payable": round(payable, 2),
                }
            )
        return rows

    def cash_movement_report(self, filters: CashMovementFilter) -> list:
        totals = self._repo.get_voucher_totals_by_type(
            filters.date_range.start, filters.date_range.end
        )
        return [
            {"flow_type": "Receipts", "amount": totals.get("receipt", 0)},
            {"flow_type": "Refunds", "amount": -totals.get("refund", 0)},
            {"flow_type": "Vendor payments", "amount": -totals.get("vendor_payment", 0)},
            {"flow_type": "Salary payments", "amount": -totals.get("salary_payment", 0)},
        ]

    def expense_by_source_report(self, filters: ExpenseBySourceFilter) -> list:
        detail = self.expense_detail_report(
            ExpenseFilter(date_range=filters.date_range)
        )
        by_source: dict[str, dict] = {}
        for row in detail:
            source = row.get("expense_source") or "Unknown"
            bucket = by_source.setdefault(
                source,
                {"expense_source": source, "total_amount": 0.0, "line_count": 0},
            )
            bucket["total_amount"] += float(row.get("total_purchase_price") or 0)
            bucket["line_count"] += 1
        for bucket in by_source.values():
            bucket["total_amount"] = round(bucket["total_amount"], 2)
        return list(by_source.values())

    def customer_segments_report(self, filters: CustomerSegmentsFilter) -> list:
        start, end = filters.date_range.start, filters.date_range.end
        with_orders = self._repo.count_distinct_customers_with_orders(start, end)
        repeat = self._repo.count_repeat_customers_with_orders(start, end)
        new_count = max(0, with_orders - repeat)
        return [
            {
                "segment": "Repeat customers",
                "customer_count": repeat,
                "order_count": with_orders,
            },
            {
                "segment": "New customers (first order in period)",
                "customer_count": new_count,
                "order_count": new_count,
            },
        ]

    def expense_detail_report(self, filters: ExpenseFilter) -> list:
        from vaybooks.bms.application.finance.reports.services._helpers import _as_date

        expenses = self._repo.get_expenses(
            filters.date_range.start,
            filters.date_range.end,
            expense_source=filters.expense_source or None,
        )
        rows = []
        for e in expenses:
            amount = float(e.get("total_purchase_price") or 0)
            if filters.min_amount is not None and amount < filters.min_amount:
                continue
            row = {
                "order_number": e.get("order_number"),
                "bill_number": e.get("bill_number"),
                "expense_name": e.get("expense_name"),
                "expense_source": e.get("expense_source"),
                "total_purchase_price": amount,
                "total_selling_price": e.get("total_selling_price"),
                "expense_date": _as_date(e.get("expense_date")),
            }
            if not matches_search(
                row, filters.search, "order_number", "bill_number", "expense_name"
            ):
                continue
            rows.append(row)
        return rows
