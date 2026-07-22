from typing import List, Optional

from vaybooks.bms.domain.boutique.measurements.entities import (
    MeasurementRecord,
    MeasurementSpecField,
    MeasurementValue,
)
from vaybooks.bms.domain.shared.enums import PersonType
from vaybooks.bms.domain.shared.exceptions import ValidationError


class MeasurementDomainService:
    def validate_spec_field(self, field: MeasurementSpecField) -> None:
        if not field.key or not field.key.strip():
            raise ValidationError("Measurement field key is required")
        if not field.label or not field.label.strip():
            raise ValidationError("Measurement field label is required")
        if not field.person_types:
            raise ValidationError("At least one person type is required")

    def validate_record(
        self,
        record: MeasurementRecord,
        specs: List[MeasurementSpecField],
    ) -> None:
        if not record.customer_id:
            raise ValidationError("Customer is required for a measurement")
        if not isinstance(record.person_type, PersonType):
            raise ValidationError("Person type is required")
        if record.person_type in (
            PersonType.BOY_CHILD,
            PersonType.GIRL_CHILD,
            PersonType.INFANT,
        ) and not (record.wearer_name or "").strip():
            raise ValidationError("Wearer name is required for child/infant measurements")

        required = [
            s
            for s in specs
            if s.applies_to(record.person_type) and s.required and s.is_active
        ]
        value_map = {
            v.field_key: (v.value or "").strip()
            for v in record.values
        }
        missing = [
            s.label for s in required if not value_map.get(s.key)
        ]
        if missing:
            raise ValidationError(
                "Missing required measurements: " + ", ".join(missing)
            )

    def build_values(self, raw: List[dict]) -> List[MeasurementValue]:
        values: List[MeasurementValue] = []
        for row in raw or []:
            key = (row.get("field_key") or row.get("key") or "").strip()
            value = str(row.get("value") or "").strip()
            if not key or not value:
                continue
            values.append(
                MeasurementValue(
                    field_key=key,
                    value=value,
                    unit=(row.get("unit") or "inch").strip() or "inch",
                    notes=(row.get("notes") or "").strip(),
                )
            )
        return values
