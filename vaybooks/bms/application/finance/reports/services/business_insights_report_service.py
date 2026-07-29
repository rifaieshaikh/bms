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

    def get_period_summary(
        self, start: date, end: date, *, location_id: str = ""
    ) -> dict[str, Any]:
        from vaybooks.bms.application.finance.reports.services.period_summary import build_period_summary

        return build_period_summary(
            self._repo, start, end, location_id=location_id
        )

    def period_financial_summary(self, filters: PeriodSummaryFilter) -> list:
        summary = self.get_period_summary(
            filters.date_range.start,
            filters.date_range.end,
            location_id=getattr(filters, "location_id", "") or "",
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
        from vaybooks.bms.application.finance.reports.services.aging import (
            allocate_balance_to_aging_buckets,
            normalize_aging_bucket_days,
        )
        from vaybooks.bms.domain.finance.accounting.sales_parsing import (
            sales_row_from_voucher,
        )
        from vaybooks.bms.domain.shared.enums import VoucherType
        from vaybooks.bms.infrastructure.db.bson_utils import as_date

        cutoffs = normalize_aging_bucket_days(filters.bucket_days)
        as_of = filters.as_of_date or date.today()
        location_id = (getattr(filters, "location_id", "") or "").strip()
        customer_map = {
            c.id: c.customer_name for c in self._customers.list_all_customers()
        }

        discount_id = None
        get_discount = getattr(self._accounting, "get_discount_account", None)
        if callable(get_discount):
            discount = get_discount()
            discount_id = discount.id if discount else None

        open_by_account: dict[str, list[dict]] = {}
        list_types = getattr(self._accounting, "list_vouchers_by_types", None)
        vouchers = []
        if callable(list_types):
            vouchers = list_types(
                [VoucherType.SALES_INVOICE, VoucherType.CUSTOMIZATION_INVOICE]
            ) or []
        else:
            list_one = getattr(self._accounting, "list_vouchers_by_type", None)
            if callable(list_one):
                vouchers = list(list_one(VoucherType.SALES_INVOICE) or [])
                vouchers.extend(list_one(VoucherType.CUSTOMIZATION_INVOICE) or [])

        if location_id:
            vouchers = [
                v
                for v in vouchers
                if (getattr(v, "location_id", "") or "").strip() == location_id
            ]

        balance_by_account: dict[str, float] | None = None
        if location_id:
            balance_by_account = {}
            list_all = getattr(self._accounting, "list_vouchers", None)
            loc_vouchers = (
                list_all(location_filter={"location_id": location_id})
                if callable(list_all)
                else []
            )
            for voucher in loc_vouchers or []:
                for line in getattr(voucher, "lines", None) or []:
                    account_id = getattr(line, "account_id", None)
                    if not account_id:
                        continue
                    debit = float(getattr(line, "debit_amount", 0) or 0)
                    credit = float(getattr(line, "credit_amount", 0) or 0)
                    balance_by_account[account_id] = round(
                        balance_by_account.get(account_id, 0.0) + debit - credit, 2
                    )

        for voucher in vouchers:
            vtype = getattr(voucher, "voucher_type", None)
            if vtype == VoucherType.SALES_INVOICE:
                try:
                    row = sales_row_from_voucher(voucher, discount_id)
                except Exception:
                    continue
                account_id = row.get("customer_account_id")
                outstanding = float(row.get("outstanding") or 0)
                inv_date = as_date(row.get("sale_date"))
            elif vtype == VoucherType.CUSTOMIZATION_INVOICE:
                account_id, outstanding, inv_date = self._customization_open_face(
                    voucher
                )
            else:
                continue
            if not account_id or outstanding <= 0 or inv_date is None:
                continue
            open_by_account.setdefault(account_id, []).append(
                {"invoice_date": inv_date, "outstanding": outstanding}
            )

        rows = []
        for acc in self._accounting.list_accounts(active_only=False):
            if not acc.linked_customer_id:
                continue
            if balance_by_account is not None:
                balance = float(balance_by_account.get(acc.id, 0) or 0)
            else:
                balance = float(acc.current_balance or 0)
            if balance <= 0:
                continue
            if filters.min_balance is not None and balance < filters.min_balance:
                continue
            customer_name = customer_map.get(
                acc.linked_customer_id, acc.account_name
            )
            if filters.search and filters.search not in customer_name.lower():
                continue
            buckets, oldest_days = allocate_balance_to_aging_buckets(
                balance,
                open_by_account.get(acc.id, []),
                as_of=as_of,
                cutoffs=cutoffs,
            )
            row = {
                "account_id": acc.id,
                "customer_id": acc.linked_customer_id,
                "customer_name": customer_name,
                "account_name": acc.account_name,
                "balance_due": round(balance, 2),
                "oldest_days": oldest_days,
                "as_of": as_of,
            }
            row.update(buckets)
            rows.append(row)
        return rows

    @staticmethod
    def _customization_open_face(voucher) -> tuple[str | None, float, date | None]:
        """Net customer AR on a customization invoice voucher."""
        from vaybooks.bms.infrastructure.db.bson_utils import as_date

        by_account: dict[str, float] = {}
        for line in getattr(voucher, "lines", None) or []:
            account_id = getattr(line, "account_id", None) or (
                line.get("account_id") if isinstance(line, dict) else None
            )
            if not account_id:
                continue
            debit = float(
                getattr(line, "debit_amount", 0)
                if not isinstance(line, dict)
                else (line.get("debit_amount") or 0)
            )
            credit = float(
                getattr(line, "credit_amount", 0)
                if not isinstance(line, dict)
                else (line.get("credit_amount") or 0)
            )
            by_account[account_id] = round(
                by_account.get(account_id, 0.0) + debit - credit, 2
            )
        # Customer line is the positive net receivable on the voucher.
        account_id = None
        outstanding = 0.0
        for acc_id, net in by_account.items():
            if net > outstanding:
                account_id = acc_id
                outstanding = net
        inv_date = as_date(getattr(voucher, "voucher_date", None))
        return account_id, outstanding, inv_date

    def vendor_payables_report(self, filters: OutstandingFilter) -> list:
        vendor_map = {v.id: v.vendor_name for v in self._vendors.list_all_vendors()}
        location_id = (getattr(filters, "location_id", "") or "").strip()
        balance_by_account: dict[str, float] | None = None
        if location_id:
            balance_by_account = {}
            list_all = getattr(self._accounting, "list_vouchers", None)
            loc_vouchers = (
                list_all(location_filter={"location_id": location_id})
                if callable(list_all)
                else []
            )
            for voucher in loc_vouchers or []:
                for line in getattr(voucher, "lines", None) or []:
                    account_id = getattr(line, "account_id", None)
                    if not account_id:
                        continue
                    debit = float(getattr(line, "debit_amount", 0) or 0)
                    credit = float(getattr(line, "credit_amount", 0) or 0)
                    balance_by_account[account_id] = round(
                        balance_by_account.get(account_id, 0.0) + debit - credit, 2
                    )
        rows = []
        for acc in self._accounting.list_accounts(active_only=False):
            if not acc.linked_vendor_id:
                continue
            if balance_by_account is not None:
                balance = float(balance_by_account.get(acc.id, 0) or 0)
            else:
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
                    "account_id": acc.id,
                    "vendor_id": acc.linked_vendor_id,
                    "vendor_name": vendor_name,
                    "account_name": acc.account_name,
                    "payable": round(payable, 2),
                }
            )
        return rows

    def cash_movement_report(self, filters: CashMovementFilter) -> list:
        totals = self._repo.get_voucher_totals_by_type(
            filters.date_range.start,
            filters.date_range.end,
            location_id=getattr(filters, "location_id", "") or "",
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
