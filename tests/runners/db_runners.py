"""MongoDB validation runners for QA DB integration tests.

Runners are keyed by runnerId (e.g. api-create-order) and may also be
selected by test case id when invoked from the CLI.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Callable, Dict, Optional, Tuple

from pymongo.database import Database

from vaybooks.bms.application.export_app_service import ExportAppService
from vaybooks.bms.domain.shared.enums import OrderStatus
from vaybooks.bms.infrastructure.db.connection import get_database_from_uri
from vaybooks.bms.infrastructure.db.qa_fixtures import (
    BILL_NUMBERS,
    EXPORT_CUSTOMER_NAME,
    EXPORT_EXPECTED_DELIVERY_DATE,
    EXPORT_ORDER_DATE,
    EXPORT_ORDER_NUMBER,
    O1004_ORDER_NUMBER,
    ORDER_NUMBER,
    ZB010_BILL_NUMBER,
    ZB010_FROZEN_MPH,
    ZB010_ITEM_ID,
    ZB010_ORDER_NUMBER,
    ZB010_ORIGINAL_HOURS,
    ensure_export_customer_anjali,
    ensure_export_order_zc20240061,
    ensure_o1001_invoice,
    ensure_o1004_failed_invoice_attempt,
    ensure_zb010_frozen_mph,
)
from vaybooks.bms.infrastructure.repositories.mongo_report_repository import MongoReportRepository

RunnerResult = Tuple[bool, str]
RunnerFn = Callable[[Database, Optional[str]], RunnerResult]


def _find_order(db: Database, order_ref: str = ORDER_NUMBER) -> Optional[dict]:
    order = db.customization_orders.find_one({"order_number": order_ref})
    if order:
        return order
    return db.customization_orders.find_one({"_id": order_ref})


def _item_ids_for_bills(order: dict, bill_numbers: Tuple[str, ...]) -> list[str]:
    items = order.get("customization_items") or order.get("bill_numbers") or []
    ids: list[str] = []
    for bill_number in bill_numbers:
        normalized = bill_number.strip().upper()
        for item in items:
            if (item.get("bill_number") or "").upper() == normalized:
                ids.append(item.get("item_id") or item.get("bill_id"))
                break
    return ids


def _expected_sale_total(order: dict, bill_item_ids: list[str]) -> float:
    items = order.get("customization_items") or []
    total = 0.0
    for item_id in bill_item_ids:
        for item in items:
            if (item.get("item_id") or item.get("bill_id")) == item_id:
                price = item.get("sale_price")
                if price is None:
                    price = item.get("sell_amount", 0.0)
                total += float(price or 0.0)
                break
    return round(total, 2)


def _zb010_item(order: dict) -> Optional[dict]:
    for item in order.get("customization_items") or []:
        if (item.get("bill_number") or "").upper() == ZB010_BILL_NUMBER:
            return item
        if item.get("item_id") == ZB010_ITEM_ID:
            return item
    return None


def validate_invoice_o1001(db: Database, _test_case_id: Optional[str] = None) -> RunnerResult:
    """TC-INV-002: invoice persisted with total_amount and order_status updated."""
    ensure_o1001_invoice(db)

    order = _find_order(db)
    if not order:
        return False, f"Order {ORDER_NUMBER} not found in customization_orders"

    order_id = order["_id"]
    bill_item_ids = _item_ids_for_bills(order, BILL_NUMBERS)
    if len(bill_item_ids) != len(BILL_NUMBERS):
        return (
            False,
            f"Expected bills {list(BILL_NUMBERS)} on order {ORDER_NUMBER}, "
            f"resolved item ids: {bill_item_ids}",
        )

    invoice = db.invoices.find_one({"order_id": order_id})
    if not invoice:
        return False, f"No invoice document found for order {ORDER_NUMBER}"

    invoice_bill_ids = set(invoice.get("bill_ids") or [])
    if set(bill_item_ids) != invoice_bill_ids:
        return (
            False,
            f"Invoice bill_ids mismatch: expected {bill_item_ids}, got {sorted(invoice_bill_ids)}",
        )

    expected_total = _expected_sale_total(order, bill_item_ids)
    total_amount = invoice.get("total_amount")
    if total_amount is None:
        total_amount = invoice.get("invoice_amount")
    if round(float(total_amount or 0), 2) != expected_total:
        return (
            False,
            f"total_amount {total_amount} != sum of item sale prices {expected_total}",
        )

    order_status = order.get("order_status")
    expected_status = OrderStatus.INVOICE_GENERATED.value
    if order_status != expected_status:
        return (
            False,
            f"order_status is {order_status!r}, expected {expected_status!r}",
        )

    invoice_number = invoice.get("invoice_number")
    return (
        True,
        f"Invoice {invoice_number} for {ORDER_NUMBER}: total_amount={total_amount}, "
        f"order_status={order_status}, bill_ids match",
    )


def validate_invoice_o1004_order_status_unchanged(
    db: Database, _test_case_id: Optional[str] = None
) -> RunnerResult:
    """TC-INV-007: failed empty-bill_ids invoice leaves O-1004 status unchanged."""
    ensure_o1004_failed_invoice_attempt(db)

    order = _find_order(db, O1004_ORDER_NUMBER)
    if not order:
        return False, f"Order {O1004_ORDER_NUMBER} not found in customization_orders"

    order_status = order.get("order_status")
    expected_status = OrderStatus.READY_FOR_DELIVERY.value
    if order_status != expected_status:
        return (
            False,
            f"order_status is {order_status!r}, expected {expected_status!r}",
        )

    invoice = db.invoices.find_one({"order_id": order["_id"]})
    if invoice:
        return (
            False,
            f"Unexpected invoice document for order {O1004_ORDER_NUMBER} after failed call",
        )

    return (
        True,
        f"Order {O1004_ORDER_NUMBER} order_status={order_status!r} unchanged, no invoice persisted",
    )


def validate_invoice_zb010_mph_frozen(
    db: Database, _test_case_id: Optional[str] = None
) -> RunnerResult:
    """TC-INV-008: ZB010 per-item MPH stays frozen after post-delivery time correction."""
    ensure_zb010_frozen_mph(db)

    order = _find_order(db, ZB010_ORDER_NUMBER)
    if not order:
        return False, f"Order {ZB010_ORDER_NUMBER} not found in customization_orders"

    item = _zb010_item(order)
    if not item:
        return False, f"Bill {ZB010_BILL_NUMBER} not found on order {ZB010_ORDER_NUMBER}"

    mph_snapshot_at = item.get("mph_snapshot_at")
    if not mph_snapshot_at:
        return False, f"{ZB010_BILL_NUMBER} has no mph_snapshot_at — MPH was not frozen"

    margin_per_hour = item.get("margin_per_hour")
    if round(float(margin_per_hour or 0), 2) != ZB010_FROZEN_MPH:
        return (
            False,
            f"{ZB010_BILL_NUMBER} margin_per_hour={margin_per_hour}, "
            f"expected frozen value {ZB010_FROZEN_MPH}",
        )

    invoice = db.invoices.find_one({"order_id": order["_id"]})
    if not invoice:
        return False, f"No invoice found for order {ZB010_ORDER_NUMBER}"

    invoice_mph = invoice.get("margin_per_hour")
    if invoice_mph is None:
        return False, "Invoice margin_per_hour is missing"

    entries = list(db.time_entries.find({"order_id": order["_id"], "bill_id": ZB010_ITEM_ID}))
    corrected_minutes = sum(int(e.get("duration_minutes") or 0) for e in entries)
    if corrected_minutes <= int(ZB010_ORIGINAL_HOURS * 60):
        return (
            False,
            f"Expected post-delivery time correction (> {ZB010_ORIGINAL_HOURS}h), "
            f"got {corrected_minutes / 60:.2f}h",
        )

    return (
        True,
        f"{ZB010_BILL_NUMBER} mph_snapshot_at frozen; margin_per_hour={margin_per_hour} "
        f"unchanged after time correction ({corrected_minutes / 60:.1f}h logged); "
        f"invoice margin_per_hour={invoice_mph}",
    )


_OBJECT_ID_REPR = re.compile(r"ObjectId\s*\(", re.IGNORECASE)
_DATETIME_REPR = re.compile(r"datetime\.datetime\s*\(", re.IGNORECASE)
_BSON_LEAK = re.compile(r"\bbson\b", re.IGNORECASE)
_HEX24 = re.compile(r"^[0-9a-fA-F]{24}$")
_ISO8601_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")


def _csv_row_for_customer(csv_text: str, customer_name: str) -> Optional[str]:
    for line in csv_text.splitlines()[1:]:
        if customer_name in line:
            return line
    return None


def _csv_row_for_order(csv_text: str, order_number: str) -> Optional[str]:
    for line in csv_text.splitlines()[1:]:
        if order_number in line:
            return line
    return None


def validate_export_customers_csv(
    db: Database, _test_case_id: Optional[str] = None
) -> RunnerResult:
    """TC-EXPORT-006: customer ObjectIds export as plain 24-char hex strings in CSV."""
    ensure_export_customer_anjali(db)

    export_service = ExportAppService(MongoReportRepository(db))
    csv_text = export_service.export_customers_csv()

    if _OBJECT_ID_REPR.search(csv_text):
        return False, "CSV contains raw ObjectId(...) wrapper text"

    if _BSON_LEAK.search(csv_text):
        return False, "CSV contains raw BSON type name"

    row = _csv_row_for_customer(csv_text, EXPORT_CUSTOMER_NAME)
    if not row:
        return False, f"No CSV row found for customer {EXPORT_CUSTOMER_NAME!r}"

    customer_doc = db.customers.find_one({"customer_name": EXPORT_CUSTOMER_NAME})
    if not customer_doc:
        return False, f"Customer {EXPORT_CUSTOMER_NAME!r} not found in customers collection"

    expected_customer_id = str(customer_doc["_id"])
    expected_account_id = str(customer_doc.get("customer_account_id", ""))

    if expected_customer_id not in row:
        return (
            False,
            f"customer_id {expected_customer_id!r} missing or not serialized as plain hex in CSV row",
        )

    if expected_account_id and expected_account_id not in row:
        return (
            False,
            f"customer_account_id {expected_account_id!r} missing or not serialized as plain hex in CSV row",
        )

    for value in (expected_customer_id, expected_account_id):
        if value and not _HEX24.match(value):
            return False, f"Expected 24-char hex string, got {value!r}"

    return (
        True,
        f"Customers CSV for {EXPORT_CUSTOMER_NAME}: customer_id and customer_account_id "
        f"serialized as plain hex ({expected_customer_id}, {expected_account_id})",
    )


def validate_export_orders_csv_iso_dates(
    db: Database, _test_case_id: Optional[str] = None
) -> RunnerResult:
    """TC-EXPORT-007: order_date and expected_delivery_date export as ISO 8601 strings."""
    ensure_export_order_zc20240061(db)

    export_service = ExportAppService(MongoReportRepository(db))
    csv_text = export_service.export_orders_csv()

    if _DATETIME_REPR.search(csv_text):
        return False, "CSV contains raw datetime.datetime(...) repr"

    if _BSON_LEAK.search(csv_text):
        return False, "CSV contains raw BSON type name"

    row = _csv_row_for_order(csv_text, EXPORT_ORDER_NUMBER)
    if not row:
        return False, f"No CSV row found for order {EXPORT_ORDER_NUMBER!r}"

    expected_order_date = EXPORT_ORDER_DATE.isoformat()
    expected_etd = EXPORT_EXPECTED_DELIVERY_DATE.isoformat()

    if expected_order_date not in row:
        return (
            False,
            f"order_date {expected_order_date!r} missing or not serialized as ISO 8601 in CSV row",
        )

    if expected_etd not in row:
        return (
            False,
            f"expected_delivery_date {expected_etd!r} missing or not serialized as ISO 8601 in CSV row",
        )

    for label, value in (
        ("order_date", expected_order_date),
        ("expected_delivery_date", expected_etd),
    ):
        if not _ISO8601_DATETIME.match(value):
            return False, f"{label} value {value!r} is not valid ISO 8601 datetime"

    return (
        True,
        f"Orders CSV for {EXPORT_ORDER_NUMBER}: order_date={expected_order_date}, "
        f"expected_delivery_date={expected_etd} serialized as ISO 8601",
    )


RUNNERS: Dict[str, RunnerFn] = {
    "api-create-order": validate_invoice_o1001,
    "api-create-customer": validate_export_customers_csv,
    "api-export-orders": validate_export_orders_csv_iso_dates,
}

TEST_CASE_RUNNERS: Dict[str, RunnerFn] = {
    "TC-INV-002": validate_invoice_o1001,
    "TC-INV-007": validate_invoice_o1004_order_status_unchanged,
    "TC-INV-008": validate_invoice_zb010_mph_frozen,
    "TC-EXPORT-006": validate_export_customers_csv,
    "TC-EXPORT-007": validate_export_orders_csv_iso_dates,
}


def run_runner(
    runner_id: str,
    test_case_id: Optional[str] = None,
    db: Optional[Database] = None,
) -> RunnerResult:
    runner = TEST_CASE_RUNNERS.get(test_case_id) if test_case_id else None
    if runner is None:
        runner = RUNNERS.get(runner_id)
    if runner is None:
        return False, f"No DB runner defined for runnerId={runner_id!r}"

    if db is None:
        uri = os.environ.get("MONGODB_URI", "")
        db_name = os.environ.get("MONGODB_DATABASE", "zahcci_customization_test")
        if not uri:
            return False, "MONGODB_URI environment variable is required"
        db = get_database_from_uri(uri, db_name)

    return runner(db, test_case_id)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a BMS DB validation runner")
    parser.add_argument("--runner", dest="runner_id", default="api-create-order")
    parser.add_argument("--test-id", dest="test_case_id", default=None)
    args = parser.parse_args()

    passed, message = run_runner(args.runner_id, args.test_case_id)
    print(json.dumps({"passed": passed, "message": message}))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
