"""Store sales (SALES_INVOICE) reporting."""

from __future__ import annotations

from datetime import date
from typing import Any

from vaybooks.bms.domain.finance.accounting.sales_parsing import (
    parse_store_invoice_number,
    sales_amounts_from_lines,
)
from vaybooks.bms.infrastructure.repositories.finance.mongo_report_repository import (
    MongoReportRepository,
)


def _amounts_from_voucher_doc(doc: dict) -> dict[str, float]:
    return sales_amounts_from_lines(doc.get("lines") or [])


class SalesReportService:
    def __init__(self, report_repo: MongoReportRepository):
        self._repo = report_repo

    def get_sales_summary(self, start: date, end: date, recent_limit: int = 20) -> dict[str, Any]:
        vouchers = self._repo.list_sales_vouchers(start, end, limit=5000)
        count = len(vouchers)
        gross_total = 0.0
        discount_total = 0.0
        collected_total = 0.0
        recent: list[dict] = []

        for doc in vouchers:
            amounts = _amounts_from_voucher_doc(doc)
            gross_total += amounts["gross"]
            discount_total += amounts["discount"]
            collected_total += amounts["collected"]

        for doc in vouchers[:recent_limit]:
            amounts = _amounts_from_voucher_doc(doc)
            recent.append(
                {
                    "id": doc.get("_id"),
                    "voucher_number": doc.get("voucher_number"),
                    "voucher_date": doc.get("voucher_date"),
                    "store_invoice_number": parse_store_invoice_number(
                        doc.get("description") or ""
                    ),
                    "party_name": amounts["party_name"],
                    "gross": amounts["gross"],
                    "collected": amounts["collected"],
                    "outstanding": amounts["outstanding"],
                }
            )

        net_total = round(gross_total - discount_total, 2)
        outstanding_total = round(net_total - collected_total, 2)
        avg_sale = round(gross_total / count, 2) if count else 0.0

        return {
            "count": count,
            "gross": round(gross_total, 2),
            "discount": round(discount_total, 2),
            "net": net_total,
            "collected": round(collected_total, 2),
            "outstanding": outstanding_total,
            "avg_sale": avg_sale,
            "recent": recent,
        }
