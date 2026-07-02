import pytest

from vaybooks.bms.domain.shared.date_utils import calculate_duration_minutes
from vaybooks.bms.domain.shared.exceptions import ValidationError


def test_duration_calculation():
    assert calculate_duration_minutes("10:00", "13:00") == 180


def test_end_must_be_greater_than_start():
    with pytest.raises(ValidationError):
        calculate_duration_minutes("14:00", "10:00")


def test_missing_times_raise():
    with pytest.raises(ValidationError):
        calculate_duration_minutes("", "13:00")
