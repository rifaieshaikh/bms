"""Tests for sales line serialization."""

from vaybooks.bms.domain.sales.line_items import (
    parse_sales_line_items_note,
    serialize_sales_line_items,
)


def test_serialize_round_trip_preserves_tax_fields():
    items = [
        {
            "product_id": "p1",
            "description": "Kurta",
            "qty": 2,
            "rate": 500,
            "discount": 0,
            "hsn_sac": "5208",
            "taxable_amount": 1000.0,
            "cgst_amount": 90.0,
            "sgst_amount": 90.0,
            "igst_amount": 0.0,
            "utgst_amount": 0.0,
            "line_total": 1180.0,
            "gst_rate": 18.0,
        }
    ]
    tax_summary = {
        "taxable": 1000.0,
        "cgst": 90.0,
        "sgst": 90.0,
        "igst": 0.0,
        "utgst": 0.0,
        "total_tax": 180.0,
        "grand_total": 1180.0,
    }
    note = serialize_sales_line_items(items, 0.0, tax_summary=tax_summary)
    description = f"Store invoice SI-1\n{note}"
    parsed_items, invoice_discount, parsed_summary = parse_sales_line_items_note(
        description
    )
    assert invoice_discount == 0.0
    assert parsed_summary == tax_summary
    assert parsed_items[0]["hsn_sac"] == "5208"
    assert parsed_items[0]["cgst_amount"] == 90.0
    assert parsed_items[0]["line_total"] == 1180.0


def test_parse_backward_compatible_without_tax_fields():
    description = (
        'Store invoice SI-2\n{"items": [{"description": "Item", "qty": 1, '
        '"rate": 100, "discount": 0}], "invoice_discount": 0}'
    )
    items, invoice_discount, tax_summary = parse_sales_line_items_note(description)
    assert len(items) == 1
    assert invoice_discount == 0.0
    assert tax_summary is None
