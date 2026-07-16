"""Exact-match + AND semantics for the list filtering framework."""

from dataclasses import dataclass
from datetime import date, datetime

from vaybooks.bms.domain.shared.enums import OrderStatus
from vaybooks.bms.ui import filtering as F
from vaybooks.bms.ui import list_schemas as ls


@dataclass
class _Order:
    order_number: str
    customer_name: str
    order_status: OrderStatus
    order_date: date
    expected_delivery_date: date
    advance_amount: float
    created_at: datetime
    customization_items: list


def _orders():
    return [
        _Order("ZO1", "Ananya Rao", OrderStatus.IN_PROGRESS, date(2026, 7, 1),
               date(2026, 7, 10), 100.0, datetime(2026, 7, 1), []),
        _Order("ZO2", "Bob", OrderStatus.COMPLETED, date(2026, 7, 5),
               date(2026, 7, 15), 0.0, datetime(2026, 7, 5), []),
    ]


def _numbers(recs):
    return sorted(r.order_number for r in recs)


def test_exact_match_passes_partial_does_not():
    recs = _orders()
    f = F.default_filters(ls.ORDERS)
    f["customer_name"] = "Ananya Rao"
    assert _numbers(F.apply_filters(recs, ls.ORDERS, f)) == ["ZO1"]

    f_partial = F.default_filters(ls.ORDERS)
    f_partial["customer_name"] = "Ananya"
    assert F.apply_filters(recs, ls.ORDERS, f_partial) == []


def test_exact_match_is_case_insensitive():
    recs = _orders()
    f = F.default_filters(ls.ORDERS)
    f["customer_name"] = "ananya rao"
    assert _numbers(F.apply_filters(recs, ls.ORDERS, f)) == ["ZO1"]

    f_upper = F.default_filters(ls.ORDERS)
    f_upper["customer_name"] = "ANANYA RAO"
    assert _numbers(F.apply_filters(recs, ls.ORDERS, f_upper)) == ["ZO1"]

    # Partial values still do not match, regardless of case.
    f_partial = F.default_filters(ls.ORDERS)
    f_partial["customer_name"] = "ananya"
    assert F.apply_filters(recs, ls.ORDERS, f_partial) == []


def test_sales_order_filters_are_case_insensitive():
    from vaybooks.bms.ui.sales_list_schemas import SALES_ORDERS

    recs = [
        {
            "id": "1",
            "so_number": "SO-0001",
            "customer_name": "Safwan",
            "customer_id": "c1",
            "order_date": date(2026, 7, 1),
            "status": "Confirmed",
        },
        {
            "id": "2",
            "so_number": "SO-0002",
            "customer_name": "Bob",
            "customer_id": "c2",
            "order_date": date(2026, 7, 5),
            "status": "Delivered",
        },
    ]

    f = F.default_filters(SALES_ORDERS)
    f["so_number"] = "so-0001"
    result = F.apply_filters(recs, SALES_ORDERS, f)
    assert [r["so_number"] for r in result] == ["SO-0001"]

    f = F.default_filters(SALES_ORDERS)
    f["customer_name"] = "SAFWAN"
    result = F.apply_filters(recs, SALES_ORDERS, f)
    assert [r["customer_name"] for r in result] == ["Safwan"]

    f = F.default_filters(SALES_ORDERS)
    f["status"] = "confirmed"
    result = F.apply_filters(recs, SALES_ORDERS, f)
    assert [r["so_number"] for r in result] == ["SO-0001"]


def test_delivery_note_filters_are_case_insensitive():
    from vaybooks.bms.ui.sales_list_schemas import DELIVERY_NOTES

    recs = [
        {
            "id": "1",
            "dn_number": "DN-0001",
            "so_number": "SO-0001",
            "customer_name": "Safwan",
            "delivery_date": date(2026, 7, 1),
            "status": "Delivered",
        },
        {
            "id": "2",
            "dn_number": "DN-0002",
            "so_number": "SO-0002",
            "customer_name": "Bob",
            "delivery_date": date(2026, 7, 5),
            "status": "Draft",
        },
    ]

    f = F.default_filters(DELIVERY_NOTES)
    f["dn_number"] = "dn-0001"
    result = F.apply_filters(recs, DELIVERY_NOTES, f)
    assert [r["dn_number"] for r in result] == ["DN-0001"]

    f = F.default_filters(DELIVERY_NOTES)
    f["so_number"] = "so-0001"
    result = F.apply_filters(recs, DELIVERY_NOTES, f)
    assert [r["dn_number"] for r in result] == ["DN-0001"]

    f = F.default_filters(DELIVERY_NOTES)
    f["customer_name"] = "SAFWAN"
    result = F.apply_filters(recs, DELIVERY_NOTES, f)
    assert [r["customer_name"] for r in result] == ["Safwan"]

    f = F.default_filters(DELIVERY_NOTES)
    f["status"] = "delivered"
    result = F.apply_filters(recs, DELIVERY_NOTES, f)
    assert [r["dn_number"] for r in result] == ["DN-0001"]


def test_and_semantics_excludes_partial_field_matches():
    recs = _orders()
    # ZO1 matches name; ZO2 matches status. Neither matches both.
    f = F.default_filters(ls.ORDERS)
    f["customer_name"] = "Ananya Rao"
    f["statuses"] = ["Completed"]
    assert F.apply_filters(recs, ls.ORDERS, f) == []


def test_multiselect_is_or_within_a_single_field():
    recs = _orders()
    f = F.default_filters(ls.ORDERS)
    f["statuses"] = ["In Progress", "Completed"]
    assert _numbers(F.apply_filters(recs, ls.ORDERS, f)) == ["ZO1", "ZO2"]


def test_date_range_is_inclusive():
    recs = _orders()
    f = F.default_filters(ls.ORDERS)
    f["order_date"] = (date(2026, 7, 4), date(2026, 7, 10))
    assert _numbers(F.apply_filters(recs, ls.ORDERS, f)) == ["ZO2"]


def test_checkbox_only_constrains_when_true():
    recs = _orders()
    f = F.default_filters(ls.ORDERS)
    f["has_advance"] = True
    assert _numbers(F.apply_filters(recs, ls.ORDERS, f)) == ["ZO1"]


def test_default_sort_is_newest_first():
    recs = _orders()
    ordered = F.sort_records(recs, ls.ORDERS, F.default_sort(ls.ORDERS))
    assert [r.order_number for r in ordered] == ["ZO2", "ZO1"]


def test_empty_filters_return_all():
    recs = _orders()
    assert len(F.apply_filters(recs, ls.ORDERS, F.default_filters(ls.ORDERS))) == 2
