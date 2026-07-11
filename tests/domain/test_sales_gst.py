"""Tests for sales GST calculation."""

import pytest

from vaybooks.bms.domain.shared.india import compute_sales_gst


def test_intra_state_registered_cgst_sgst():
    gst = compute_sales_gst(
        1000.0,
        18.0,
        business_registered=True,
        business_state_code="27",
        customer_state_code="27",
    )
    assert gst.taxable_amount == 1000.0
    assert gst.cgst_amount == 90.0
    assert gst.sgst_amount == 90.0
    assert gst.line_total == 1180.0


def test_inter_state_registered_igst():
    gst = compute_sales_gst(
        500.0,
        12.0,
        business_registered=True,
        business_state_code="27",
        customer_state_code="09",
    )
    assert gst.igst_amount == 60.0
    assert gst.cgst_amount == 0.0
    assert gst.line_total == 560.0


def test_unregistered_business_no_gst():
    gst = compute_sales_gst(
        200.0,
        18.0,
        business_registered=False,
        business_state_code="27",
        customer_state_code="27",
    )
    assert gst.total_tax == 0.0
    assert gst.line_total == 200.0


def test_ut_intra_state_utgst():
    gst = compute_sales_gst(
        100.0,
        5.0,
        business_registered=True,
        business_state_code="04",
        customer_state_code="04",
    )
    assert gst.cgst_amount == 2.5
    assert gst.utgst_amount == 2.5
    assert gst.sgst_amount == 0.0
