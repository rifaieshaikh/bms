from datetime import date

from vaybooks.bms.application.report_filters import DateRange, ItemProfitabilityFilter
from vaybooks.bms.ui.components.common.report_filters import build_item_profitability_filter
from vaybooks.bms.ui import filtering as F
from vaybooks.bms.ui.report_schemas import (
    INVENTORY_REPORT_TYPES,
    ITEM_PROFITABILITY,
    ORDER_MPH,
    REPORT_CATEGORIES,
    REPORT_TYPES,
    SCHEMA_BY_REPORT_TYPE,
)


def test_build_item_profitability_filter_from_bar_state():
    start, end = date(2026, 3, 1), date(2026, 3, 31)
    filters = {
        "date_range": (start, end),
        "customer_query": "Alice",
        "bill_query": "B-01",
        "min_mph": 100.0,
        "min_margin": 500.0,
    }
    result = build_item_profitability_filter(filters)
    assert isinstance(result, ItemProfitabilityFilter)
    assert result.date_range == DateRange(start, end)
    assert result.customer_query == "alice"
    assert result.bill_query == "b-01"
    assert result.min_mph == 100.0
    assert result.min_margin == 500.0


def test_report_schemas_define_sort_options():
    assert len(ITEM_PROFITABILITY.sort_options) >= 3
    assert len(ORDER_MPH.sort_options) >= 3
    assert ITEM_PROFITABILITY.default_sort == "margin_per_hour"


def test_report_schema_default_filters_include_mtd_period():
    defaults = F.default_filters(ITEM_PROFITABILITY)
    assert defaults["date_range"][0].day == 1


def test_report_categories_cover_all_reports():
    listed = [report for reports in REPORT_CATEGORIES.values() for report in reports]
    assert len(listed) == len(REPORT_TYPES)
    assert set(listed) == set(REPORT_TYPES)
    assert "Inventory" not in REPORT_CATEGORIES
    assert set(REPORT_TYPES).isdisjoint(INVENTORY_REPORT_TYPES)
    assert set(REPORT_TYPES) | set(INVENTORY_REPORT_TYPES) == set(
        SCHEMA_BY_REPORT_TYPE.keys()
    )
