"""First-class measurement specs and customer measurement records."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import (
    FitPreference,
    MeasurementFieldType,
    MeasurementSection,
    PersonType,
)


@dataclass
class MeasurementSectionConfig:
    key: str
    label: str
    sort_order: int = 0
    is_active: bool = True
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def update(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key) and value is not None:
                setattr(self, key, value)
        self.updated_at = utc_now()


@dataclass
class MeasurementSpecField:
    key: str
    label: str
    person_types: List[PersonType] = field(default_factory=list)
    section: str = MeasurementSection.TORSO.value
    value_type: MeasurementFieldType = MeasurementFieldType.NUMBER
    unit: str = "inch"
    required: bool = False
    sort_order: int = 0
    is_core: bool = True
    is_active: bool = True
    help_text: str = ""
    options: List[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def update(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key) and value is not None:
                setattr(self, key, value)
        self.updated_at = utc_now()

    def applies_to(self, person_type: PersonType) -> bool:
        if not self.is_active:
            return False
        if not self.person_types:
            return True
        return person_type in self.person_types


@dataclass
class MeasurementValue:
    field_key: str
    value: str
    unit: str = "inch"
    notes: str = ""


@dataclass
class MeasurementRecord:
    measurement_number: str
    customer_id: str
    person_type: PersonType
    id: str = field(default_factory=lambda: uuid4().hex)
    order_id: Optional[str] = None
    wearer_name: str = ""
    wearer_age: str = ""
    wearer_height: str = ""
    wearer_weight: str = ""
    unit: str = "inch"
    fit_preference: FitPreference = FitPreference.REGULAR
    values: List[MeasurementValue] = field(default_factory=list)
    notes: str = ""
    print_notes: str = ""
    measured_at: date = field(default_factory=date.today)
    measured_by: str = ""
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def value_map(self) -> dict:
        return {v.field_key: v for v in self.values}

    def set_value(
        self,
        field_key: str,
        value: str,
        unit: str = "inch",
        notes: str = "",
    ) -> None:
        existing = self.value_map().get(field_key)
        if existing:
            existing.value = value
            existing.unit = unit
            existing.notes = notes
        else:
            self.values.append(
                MeasurementValue(
                    field_key=field_key,
                    value=value,
                    unit=unit,
                    notes=notes,
                )
            )
        self.updated_at = utc_now()
