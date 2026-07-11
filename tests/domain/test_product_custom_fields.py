"""Tests for product custom field definitions."""

import pytest

from vaybooks.bms.domain.inventory.field_definitions import (
    ProductFieldDefinition,
    ProductFieldType,
    validate_custom_field_values,
)
from vaybooks.bms.domain.shared.exceptions import ValidationError


def test_required_custom_field_validation():
    definition = ProductFieldDefinition(
        key="width",
        label="Width",
        field_type=ProductFieldType.TEXT,
        required=True,
    )
    with pytest.raises(ValidationError):
        validate_custom_field_values([definition], {}, ["c1"])


def test_category_scope():
    definition = ProductFieldDefinition(
        key="gsm",
        label="GSM",
        field_type=ProductFieldType.NUMBER,
        applies_to_category_ids=["fabric"],
    )
    assert definition.applies_to_product(["fabric"])
    assert not definition.applies_to_product(["other"])
