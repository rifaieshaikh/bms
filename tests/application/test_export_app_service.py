import json
from datetime import datetime
from unittest.mock import MagicMock

from bson import ObjectId
from bson.decimal128 import Decimal128

from vaybooks.bms.application.export_app_service import ExportAppService, _serialize_cell
from vaybooks.bms.domain.shared.enums import OrderStatus


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


def test_serialize_cell_primitives():
    assert _serialize_cell("text") == "text"
    assert _serialize_cell(42) == "42"
    assert _serialize_cell(3.5) == "3.5"
    assert _serialize_cell(True) == "True"
    assert _serialize_cell(None) == ""
    assert _serialize_cell(OrderStatus.IN_PROGRESS) == "In Progress"


def test_default_serializer_never_raises_on_scalars():
    from vaybooks.bms.application.export_app_service import default_serializer

    assert default_serializer("hello") == "hello"
    assert default_serializer(99) == 99


def test_export_customers_csv_handles_strings_and_objectid():
    customer_id = ObjectId()
    report_repo = MagicMock()
    report_repo.get_all_customers.return_value = [
        {
            "_id": customer_id,
            "customer_name": "Alice Boutique",
            "phone_number": "9876543210",
            "alternate_phone_number": "",
            "address": "12 Main St",
            "notes": "",
            "customer_account_id": ObjectId(),
        }
    ]
    export_service = ExportAppService(report_repo)
    csv_data = export_service.export_customers_csv()

    assert "Alice Boutique" in csv_data
    assert "9876543210" in csv_data
    assert str(customer_id) in csv_data


def test_export_orders_csv_handles_datetime_and_decimal():
    order_id = ObjectId()
    report_repo = MagicMock()
    report_repo.get_all_orders.return_value = [
        {
            "_id": order_id,
            "order_number": "ZC-2024-0061",
            "customer_name": "Sharma, Priya's Boutique",
            "phone_number": "9000000001",
            "order_status": "In Progress",
            "order_date": datetime(2024, 6, 1, 0, 0, 0),
            "expected_delivery_date": datetime(2024, 6, 15, 0, 0, 0),
            "advance_amount": Decimal128("1500.50"),
        }
    ]
    export_service = ExportAppService(report_repo)
    csv_data = export_service.export_orders_csv()

    assert "ZC-2024-0061" in csv_data
    assert "2024-06-01" in csv_data
    assert "1500.50" in csv_data
    assert str(order_id) in csv_data
