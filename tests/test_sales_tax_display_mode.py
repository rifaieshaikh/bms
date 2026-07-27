"""Tests for sales tax column display mode."""

from vaybooks.bms.domain.shared.india import UTGST_STATE_CODES
from vaybooks.bms.ui.components.sales.sales_line_ui import (
    sales_tax_column_labels,
    sales_tax_display_mode,
)


def test_tax_mode_none_when_unregistered():
    assert sales_tax_display_mode(business_registered=False) == "none"
    assert sales_tax_column_labels("none") == []


def test_tax_mode_igst_inter_state():
    assert (
        sales_tax_display_mode(
            business_registered=True,
            business_state_code="27",
            customer_state_code="29",
        )
        == "igst"
    )
    assert sales_tax_column_labels("igst") == ["IGST"]


def test_tax_mode_cgst_sgst_same_state():
    assert (
        sales_tax_display_mode(
            business_registered=True,
            business_state_code="27",
            customer_state_code="27",
        )
        == "cgst_sgst"
    )
    assert sales_tax_column_labels("cgst_sgst") == ["CGST", "SGST"]


def test_tax_mode_cgst_utgst_same_ut():
    ut = next(iter(UTGST_STATE_CODES))
    assert (
        sales_tax_display_mode(
            business_registered=True,
            business_state_code=ut,
            customer_state_code=ut,
        )
        == "cgst_utgst"
    )
    assert sales_tax_column_labels("cgst_utgst") == ["CGST", "UTGST"]


def test_tax_mode_defaults_to_igst_when_state_missing():
    assert (
        sales_tax_display_mode(
            business_registered=True,
            business_state_code="27",
            customer_state_code="",
        )
        == "igst"
    )
