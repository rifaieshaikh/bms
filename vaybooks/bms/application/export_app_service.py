import json
from datetime import date, datetime
from io import StringIO
from typing import Any

from bson import ObjectId
from bson.decimal128 import Decimal128

from vaybooks.bms.infrastructure.repositories.mongo_report_repository import MongoReportRepository


def _serialize_bson(value: Any) -> Any:
    """Recursively convert BSON/Python types to JSON-serializable primitives."""
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal128):
        return str(value)
    if isinstance(value, dict):
        return {key: _serialize_bson(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize_bson(item) for item in value]
    return value


def default_serializer(value: Any) -> Any:
    """Serialize BSON/Python types for CSV/JSON export without leaking raw reprs."""
    if isinstance(value, (ObjectId, datetime, date, Decimal128, dict, list)):
        return _serialize_bson(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _serialize_cell(value: Any) -> str:
    if value is None:
        return ""
    serialized = default_serializer(value)
    if isinstance(serialized, (dict, list)):
        return json.dumps(serialized)
    return str(serialized)


class ExportAppService:
    def __init__(self, report_repo: MongoReportRepository):
        self._repo = report_repo

    def _docs_to_csv(self, docs: list, fields: list) -> str:
        import csv

        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for doc in docs:
            row = {field: _serialize_cell(doc.get(field, "")) for field in fields}
            if "_id" in doc:
                if "id" in fields:
                    row["id"] = _serialize_cell(doc["_id"])
                if "customer_id" in fields:
                    row["customer_id"] = _serialize_cell(doc["_id"])
            writer.writerow(row)
        return output.getvalue()

    def export_customers_csv(self) -> str:
        docs = self._repo.get_all_customers()
        return self._docs_to_csv(
            docs,
            [
                "customer_id",
                "customer_name",
                "phone_number",
                "alternate_phone_number",
                "address",
                "notes",
                "customer_account_id",
            ],
        )

    def export_orders_csv(self) -> str:
        docs = self._repo.get_all_orders()
        rows = []
        for doc in docs:
            rows.append(
                {
                    "id": doc.get("_id"),
                    "order_number": doc.get("order_number"),
                    "customer_name": doc.get("customer_name"),
                    "phone_number": doc.get("phone_number"),
                    "order_status": doc.get("order_status"),
                    "order_date": doc.get("order_date"),
                    "expected_delivery_date": doc.get("expected_delivery_date"),
                    "advance_amount": doc.get("advance_amount"),
                }
            )
        return self._docs_to_csv(
            rows,
            [
                "id",
                "order_number",
                "customer_name",
                "phone_number",
                "order_status",
                "order_date",
                "expected_delivery_date",
                "advance_amount",
            ],
        )

    def export_time_entries_csv(self) -> str:
        return self._docs_to_csv(
            self._repo.get_all_time_entries(),
            [
                "order_number",
                "bill_number",
                "activity_name",
                "work_date",
                "start_time",
                "end_time",
                "duration_minutes",
                "worker_name",
            ],
        )

    def export_expenses_csv(self) -> str:
        return self._docs_to_csv(
            self._repo.get_all_expenses(),
            [
                "order_number",
                "expense_name",
                "expense_source",
                "total_purchase_price",
                "total_selling_price",
                "expense_date",
            ],
        )

    def export_invoices_csv(self) -> str:
        return self._docs_to_csv(
            self._repo.get_all_invoices(),
            [
                "order_number",
                "invoice_number",
                "invoice_amount",
                "margin_amount",
                "margin_per_hour",
                "invoice_date",
            ],
        )

    def export_vouchers_csv(self) -> str:
        return self._docs_to_csv(
            self._repo.get_all_vouchers(),
            [
                "voucher_number",
                "voucher_type",
                "voucher_date",
                "description",
            ],
        )

    def export_full_backup_json(self) -> str:
        backup = {
            "customers": self._repo.get_all_customers(),
            "customization_orders": self._repo.get_all_orders(),
            "time_entries": self._repo.get_all_time_entries(),
            "expenses": self._repo.get_all_expenses(),
            "invoices": self._repo.get_all_invoices(),
            "vouchers": self._repo.get_all_vouchers(),
        }

        return json.dumps(_serialize_bson(backup), indent=2)
