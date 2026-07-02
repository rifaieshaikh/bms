import json
from io import StringIO

from vaybooks.bms.infrastructure.repositories.mongo_report_repository import MongoReportRepository


class ExportAppService:
    def __init__(self, report_repo: MongoReportRepository):
        self._repo = report_repo

    def _docs_to_csv(self, docs: list, fields: list) -> str:
        import csv

        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for doc in docs:
            row = {f: doc.get(f, "") for f in fields}
            if "_id" in doc and "id" in fields:
                row["id"] = doc["_id"]
            writer.writerow(row)
        return output.getvalue()

    def export_customers_csv(self) -> str:
        docs = self._repo.get_all_customers()
        return self._docs_to_csv(
            docs,
            [
                "id",
                "customer_name",
                "phone_number",
                "alternate_phone_number",
                "address",
                "notes",
            ],
        )

    def export_orders_csv(self) -> str:
        docs = self._repo.get_all_orders()
        rows = []
        for doc in docs:
            rows.append(
                {
                    "id": doc["_id"],
                    "order_number": doc.get("order_number"),
                    "customer_name": doc.get("customer_name"),
                    "phone_number": doc.get("phone_number"),
                    "order_status": doc.get("order_status"),
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

        def default_serializer(obj):
            if hasattr(obj, "isoformat"):
                return obj.isoformat()
            return str(obj)

        return json.dumps(backup, default=default_serializer, indent=2)
