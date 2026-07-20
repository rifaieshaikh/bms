from __future__ import annotations

from datetime import date
from typing import List, Optional

from vaybooks.bms.domain.accounting.repository import CounterRepository
from vaybooks.bms.domain.measurements.entities import (
    MeasurementRecord,
    MeasurementSectionConfig,
    MeasurementSpecField,
)
from vaybooks.bms.domain.measurements.repository import (
    MeasurementRecordRepository,
    MeasurementSectionRepository,
    MeasurementSpecRepository,
)
from vaybooks.bms.domain.measurements.services import MeasurementDomainService
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import (
    FitPreference,
    MeasurementFieldType,
    MeasurementSection,
    PersonType,
)
from vaybooks.bms.domain.shared.exceptions import ValidationError


class MeasurementAppService:
    def __init__(
        self,
        spec_repo: MeasurementSpecRepository,
        record_repo: MeasurementRecordRepository,
        counter_repo: CounterRepository,
        section_repo: Optional[MeasurementSectionRepository] = None,
    ):
        self._spec_repo = spec_repo
        self._record_repo = record_repo
        self._counter_repo = counter_repo
        self._section_repo = section_repo
        self._domain = MeasurementDomainService()

    # --- Specs ---

    def list_specs(self, active_only: bool = False) -> List[MeasurementSpecField]:
        return self._spec_repo.list_all(active_only=active_only)

    def list_specs_for_person(
        self, person_type: PersonType | str, active_only: bool = True
    ) -> List[MeasurementSpecField]:
        pt = (
            person_type
            if isinstance(person_type, PersonType)
            else PersonType(person_type)
        )
        return self._spec_repo.list_for_person_type(pt, active_only=active_only)

    def get_spec(self, field_id: str) -> Optional[MeasurementSpecField]:
        return self._spec_repo.find_by_id(field_id)

    def create_spec(
        self,
        key: str,
        label: str,
        person_types: List[str],
        section: str = MeasurementSection.TORSO.value,
        value_type: str = MeasurementFieldType.NUMBER.value,
        unit: str = "inch",
        required: bool = False,
        sort_order: int = 0,
        is_core: bool = False,
        is_active: bool = True,
        help_text: str = "",
        options: Optional[List[str]] = None,
    ) -> MeasurementSpecField:
        field = MeasurementSpecField(
            key=key.strip().lower().replace(" ", "_"),
            label=label.strip(),
            person_types=[PersonType(p) for p in person_types],
            section=section,
            value_type=MeasurementFieldType(value_type),
            unit=unit or "inch",
            required=required,
            sort_order=sort_order,
            is_core=is_core,
            is_active=is_active,
            help_text=help_text or "",
            options=list(options or []),
        )
        self._domain.validate_spec_field(field)
        return self._spec_repo.save(field)

    def update_spec(
        self,
        field_id: str,
        **kwargs,
    ) -> MeasurementSpecField:
        field = self._spec_repo.find_by_id(field_id)
        if not field:
            raise ValidationError("Measurement spec field not found")
        if "person_types" in kwargs and kwargs["person_types"] is not None:
            kwargs["person_types"] = [
                PersonType(p) for p in kwargs["person_types"]
            ]
        if "value_type" in kwargs and kwargs["value_type"] is not None:
            kwargs["value_type"] = MeasurementFieldType(kwargs["value_type"])
        field.update(**kwargs)
        self._domain.validate_spec_field(field)
        return self._spec_repo.save(field)

    def delete_spec(self, field_id: str) -> None:
        self._spec_repo.delete(field_id)

    # --- Configurable sections ---

    def list_sections(
        self, active_only: bool = False
    ) -> List[MeasurementSectionConfig]:
        if not self._section_repo:
            return [
                MeasurementSectionConfig(
                    key=section.value,
                    label=section.value,
                    sort_order=index * 100,
                )
                for index, section in enumerate(MeasurementSection)
            ]
        return self._section_repo.list_all(active_only=active_only)

    def create_section(
        self,
        key: str,
        label: str,
        sort_order: int = 0,
        is_active: bool = True,
    ) -> MeasurementSectionConfig:
        if not self._section_repo:
            raise ValidationError("Measurement section repository is unavailable")
        normalized = key.strip().lower().replace(" ", "_")
        if not normalized or not label.strip():
            raise ValidationError("Section key and label are required")
        if self._section_repo.find_by_key(normalized):
            raise ValidationError(f"Section key {normalized} already exists")
        return self._section_repo.save(
            MeasurementSectionConfig(
                key=normalized,
                label=label.strip(),
                sort_order=int(sort_order),
                is_active=is_active,
            )
        )

    def update_section(
        self, section_id: str, **kwargs
    ) -> MeasurementSectionConfig:
        if not self._section_repo:
            raise ValidationError("Measurement section repository is unavailable")
        section = self._section_repo.find_by_id(section_id)
        if not section:
            raise ValidationError("Measurement section not found")
        # Keys remain stable because fields reference them.
        kwargs.pop("key", None)
        section.update(**kwargs)
        return self._section_repo.save(section)

    def delete_section(self, section_id: str) -> None:
        if not self._section_repo:
            raise ValidationError("Measurement section repository is unavailable")
        section = self._section_repo.find_by_id(section_id)
        if not section:
            raise ValidationError("Measurement section not found")
        in_use = [s for s in self._spec_repo.list_all() if s.section == section.key]
        if in_use:
            raise ValidationError(
                "Section is used by measurement fields; deactivate it instead"
            )
        self._section_repo.delete(section_id)

    # --- Records ---

    def list_all(self) -> List[MeasurementRecord]:
        """List customer-owned measurement records, newest first."""
        return self._record_repo.list_all()

    def list_by_customer(self, customer_id: str) -> List[MeasurementRecord]:
        return self._record_repo.list_by_customer(customer_id)

    def list_by_order(self, order_id: str) -> List[MeasurementRecord]:
        return self._record_repo.list_by_order(order_id)

    def get_record(self, record_id: str) -> Optional[MeasurementRecord]:
        return self._record_repo.find_by_id(record_id)

    def get_by_number(self, measurement_number: str) -> Optional[MeasurementRecord]:
        return self._record_repo.find_by_number(measurement_number)

    def create_record(
        self,
        customer_id: str,
        person_type: str,
        values: Optional[List[dict]] = None,
        order_id: Optional[str] = None,
        wearer_name: str = "",
        wearer_age: str = "",
        wearer_height: str = "",
        wearer_weight: str = "",
        unit: str = "inch",
        fit_preference: str = FitPreference.REGULAR.value,
        notes: str = "",
        print_notes: str = "",
        measured_at: Optional[date] = None,
        measured_by: str = "",
    ) -> MeasurementRecord:
        pt = PersonType(person_type)
        record = MeasurementRecord(
            measurement_number=self._counter_repo.next("measurement_number"),
            customer_id=customer_id,
            person_type=pt,
            order_id=order_id,
            wearer_name=(wearer_name or "").strip(),
            wearer_age=(wearer_age or "").strip(),
            wearer_height=(wearer_height or "").strip(),
            wearer_weight=(wearer_weight or "").strip(),
            unit=unit or "inch",
            fit_preference=FitPreference(fit_preference),
            values=self._domain.build_values(values or []),
            notes=(notes or "").strip(),
            print_notes=(print_notes or "").strip(),
            measured_at=measured_at or date.today(),
            measured_by=(measured_by or "").strip(),
        )
        specs = self.list_specs_for_person(pt, active_only=True)
        self._domain.validate_record(record, specs)
        return self._record_repo.save(record)

    def update_record(
        self,
        record_id: str,
        *,
        values: Optional[List[dict]] = None,
        wearer_name: Optional[str] = None,
        wearer_age: Optional[str] = None,
        wearer_height: Optional[str] = None,
        wearer_weight: Optional[str] = None,
        unit: Optional[str] = None,
        fit_preference: Optional[str] = None,
        notes: Optional[str] = None,
        print_notes: Optional[str] = None,
        measured_at: Optional[date] = None,
        measured_by: Optional[str] = None,
        order_id: Optional[str] = None,
        person_type: Optional[str] = None,
    ) -> MeasurementRecord:
        record = self._record_repo.find_by_id(record_id)
        if not record:
            raise ValidationError("Measurement record not found")
        if person_type is not None:
            record.person_type = PersonType(person_type)
        if values is not None:
            record.values = self._domain.build_values(values)
        if wearer_name is not None:
            record.wearer_name = wearer_name.strip()
        if wearer_age is not None:
            record.wearer_age = wearer_age.strip()
        if wearer_height is not None:
            record.wearer_height = wearer_height.strip()
        if wearer_weight is not None:
            record.wearer_weight = wearer_weight.strip()
        if unit is not None:
            record.unit = unit
        if fit_preference is not None:
            record.fit_preference = FitPreference(fit_preference)
        if notes is not None:
            record.notes = notes.strip()
        if print_notes is not None:
            record.print_notes = print_notes.strip()
        if measured_at is not None:
            record.measured_at = measured_at
        if measured_by is not None:
            record.measured_by = measured_by.strip()
        if order_id is not None:
            record.order_id = order_id
        record.updated_at = utc_now()
        specs = self.list_specs_for_person(record.person_type, active_only=True)
        self._domain.validate_record(record, specs)
        return self._record_repo.save(record)

    def delete_record(self, record_id: str) -> None:
        record = self._record_repo.find_by_id(record_id)
        if not record:
            raise ValidationError("Measurement record not found")
        self._record_repo.delete(record_id)
