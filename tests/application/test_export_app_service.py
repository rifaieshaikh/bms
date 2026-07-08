import json
from datetime import datetime
from unittest.mock import MagicMock

from bson import ObjectId
from bson.decimal128 import Decimal128

from vaybooks.bms.application.export_app_service import ExportAppService


def test_export_full_backup_json_is_valid_json():
    report_repo = MagicMock()
    customer_id = ObjectId()
    order_id = ObjectId()
    report_repo.get_all_customers.return_value = [
        {
            "_id": customer_id,
            "customer_name": "O'Brien, Zahcci",
            "customer_account_id": ObjectId(),
            "created_at": datetime(2024, 6, 15, 10, 30, 0),
        }
    ]
    report_repo.get_all_orders.return_value = [
        {
            "_id": order_id,
            "order_number": "ZC-2024-0061",
            "customer_name": "Sharma, Priya's Boutique",
            "order_date": datetime(2024, 6, 1, 0, 0, 0),
            "advance_amount": Decimal128("1500.50"),
        }
    ]
    report_repo.get_all_time_entries.return_value = []
    report_repo.get_all_expenses.return_value = [
        {
            "_id": ObjectId(),
            "order_number": "ZC-2024-0061",
            "total_purchase_price": Decimal128("800.00"),
            "expense_date": datetime(2024, 6, 2, 12, 0, 0),
        }
    ]
    report_repo.get_all_invoices.return_value = []
    report_repo.get_all_vouchers.return_value = [
        {
            "_id": ObjectId(),
            "voucher_number": "VCH-0001",
            "voucher_date": datetime(2024, 6, 30, 18, 0, 0),
            "description": "Month-end, Zahcci adjustment",
        }
    ]

    export_service = ExportAppService(report_repo)
    backup_json = export_service.export_full_backup_json()

    parsed = json.loads(backup_json)
    assert parsed["customers"][0]["customer_name"] == "O'Brien, Zahcci"
    assert parsed["customization_orders"][0]["customer_name"] == "Sharma, Priya's Boutique"
    assert parsed["expenses"][0]["total_purchase_price"] == "800.00"
    assert parsed["vouchers"][0]["description"] == "Month-end, Zahcci adjustment"
