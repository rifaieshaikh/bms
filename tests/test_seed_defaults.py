from vaybooks.bms.domain.shared.enums import ActivityCategory
from vaybooks.bms.infrastructure.db.seed import (
    DEFAULT_ACCOUNTS,
    DEFAULT_ACTIVITIES,
    DEFAULT_VENDOR_SERVICES,
)


def test_default_activities_cover_in_house_and_outsourced():
    names = {a["activity_name"] for a in DEFAULT_ACTIVITIES}
    assert names == {
        "Cutting",
        "Stitching",
        "Handwork",
        "Cutting and Stitching",
        "Material Purchase",
        "Dyeing",
        "Embroidery",
    }

    in_house = [
        a
        for a in DEFAULT_ACTIVITIES
        if a["activity_category"] == ActivityCategory.IN_HOUSE_SERVICE.value
    ]
    assert len(in_house) == 4
    assert all(a["requires_time_tracking"] for a in in_house)
    assert {a["activity_name"]: a["default_hourly_expense"] for a in in_house} == {
        "Cutting": 250,
        "Stitching": 250,
        "Handwork": 300,
        "Cutting and Stitching": 250,
    }

    outsourced = [
        a
        for a in DEFAULT_ACTIVITIES
        if a["activity_category"]
        in (
            ActivityCategory.OUTSOURCED_SERVICE.value,
            ActivityCategory.OUTSOURCED_MATERIAL.value,
        )
    ]
    assert {a["activity_name"] for a in outsourced} == {
        "Material Purchase",
        "Dyeing",
        "Embroidery",
    }
    assert all(not a["requires_time_tracking"] for a in outsourced)


def test_default_vendor_services_link_to_expense_accounts():
    account_names = {name for name, _, _ in DEFAULT_ACCOUNTS}
    service_names = {name for name, _ in DEFAULT_VENDOR_SERVICES}
    assert service_names == {
        "Material Purchase",
        "Dyeing",
        "Embroidery",
        "Cutting",
        "Stitching",
        "Cutting & Stitching",
        "Handwork",
    }
    for service_name, expense_account_name in DEFAULT_VENDOR_SERVICES:
        assert expense_account_name in account_names, (
            f"{service_name} -> {expense_account_name} missing from DEFAULT_ACCOUNTS"
        )


def test_default_accounts_include_activity_expense_buckets():
    expense_names = {
        name for name, account_type, _ in DEFAULT_ACCOUNTS if account_type.value == "Expense"
    }
    assert {
        "Cutting Expense",
        "Stitching Expense",
        "Handwork Expense",
        "Cutting and Stitching Expense",
        "Material Purchase Expense",
        "Dyeing Expense",
        "Embroidery Expense",
        "Salary Expense",
        "Discount Allowed",
    }.issubset(expense_names)
