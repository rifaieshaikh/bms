from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.measurements.entities import (
    MeasurementRecord,
    MeasurementSectionConfig,
    MeasurementSpecField,
    MeasurementValue,
)
from vaybooks.bms.domain.shared.enums import (
    FitPreference,
    MeasurementFieldType,
    MeasurementSection,
    PersonType,
)
from vaybooks.bms.infrastructure.db.bson_utils import from_bson_date, to_bson_value


class MongoMeasurementSpecRepository:
    def __init__(self, db: Database):
        self._collection = db.measurement_specs

    def _to_doc(self, field: MeasurementSpecField) -> dict:
        return {
            "_id": field.id,
            "key": field.key,
            "label": field.label,
            "person_types": [p.value for p in field.person_types],
            "section": field.section,
            "value_type": field.value_type.value,
            "unit": field.unit,
            "required": field.required,
            "sort_order": field.sort_order,
            "is_core": field.is_core,
            "is_active": field.is_active,
            "help_text": field.help_text,
            "options": list(field.options),
            "created_at": field.created_at,
            "updated_at": field.updated_at,
        }

    def _from_doc(self, doc: dict) -> MeasurementSpecField:
        return MeasurementSpecField(
            id=doc["_id"],
            key=doc["key"],
            label=doc["label"],
            person_types=[
                PersonType(p) for p in doc.get("person_types") or []
            ],
            section=doc.get("section", MeasurementSection.TORSO.value),
            value_type=MeasurementFieldType(
                doc.get("value_type", MeasurementFieldType.NUMBER.value)
            ),
            unit=doc.get("unit", "inch"),
            required=bool(doc.get("required")),
            sort_order=int(doc.get("sort_order") or 0),
            is_core=bool(doc.get("is_core", True)),
            is_active=doc.get("is_active", True),
            help_text=doc.get("help_text", ""),
            options=list(doc.get("options") or []),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, field: MeasurementSpecField) -> MeasurementSpecField:
        self._collection.replace_one(
            {"_id": field.id}, self._to_doc(field), upsert=True
        )
        return field

    def find_by_id(self, field_id: str) -> Optional[MeasurementSpecField]:
        doc = self._collection.find_one({"_id": field_id})
        return self._from_doc(doc) if doc else None

    def find_by_key(
        self, key: str, person_type: Optional[PersonType] = None
    ) -> Optional[MeasurementSpecField]:
        query: dict = {"key": key.strip()}
        if person_type is not None:
            query["person_types"] = person_type.value
        doc = self._collection.find_one(query)
        return self._from_doc(doc) if doc else None

    def list_all(self, active_only: bool = False) -> List[MeasurementSpecField]:
        query = {"is_active": True} if active_only else {}
        docs = self._collection.find(query).sort(
            [("sort_order", 1), ("label", 1)]
        )
        return [self._from_doc(d) for d in docs]

    def list_for_person_type(
        self, person_type: PersonType, active_only: bool = True
    ) -> List[MeasurementSpecField]:
        query: dict = {"person_types": person_type.value}
        if active_only:
            query["is_active"] = True
        docs = self._collection.find(query).sort(
            [("sort_order", 1), ("label", 1)]
        )
        return [self._from_doc(d) for d in docs]

    def delete(self, field_id: str) -> None:
        self._collection.delete_one({"_id": field_id})


class MongoMeasurementSectionRepository:
    def __init__(self, db: Database):
        self._collection = db.measurement_sections

    def _to_doc(self, section: MeasurementSectionConfig) -> dict:
        return {
            "_id": section.id,
            "key": section.key,
            "label": section.label,
            "sort_order": section.sort_order,
            "is_active": section.is_active,
            "created_at": section.created_at,
            "updated_at": section.updated_at,
        }

    def _from_doc(self, doc: dict) -> MeasurementSectionConfig:
        return MeasurementSectionConfig(
            id=doc["_id"],
            key=doc["key"],
            label=doc["label"],
            sort_order=int(doc.get("sort_order") or 0),
            is_active=doc.get("is_active", True),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, section: MeasurementSectionConfig) -> MeasurementSectionConfig:
        self._collection.replace_one(
            {"_id": section.id}, self._to_doc(section), upsert=True
        )
        return section

    def find_by_id(self, section_id: str) -> Optional[MeasurementSectionConfig]:
        doc = self._collection.find_one({"_id": section_id})
        return self._from_doc(doc) if doc else None

    def find_by_key(self, key: str) -> Optional[MeasurementSectionConfig]:
        doc = self._collection.find_one({"key": key.strip()})
        return self._from_doc(doc) if doc else None

    def list_all(self, active_only: bool = False) -> List[MeasurementSectionConfig]:
        query = {"is_active": True} if active_only else {}
        docs = self._collection.find(query).sort(
            [("sort_order", 1), ("label", 1)]
        )
        return [self._from_doc(d) for d in docs]

    def delete(self, section_id: str) -> None:
        self._collection.delete_one({"_id": section_id})


class MongoMeasurementRecordRepository:
    def __init__(self, db: Database):
        self._collection = db.measurement_records

    def _value_to_doc(self, value: MeasurementValue) -> dict:
        return {
            "field_key": value.field_key,
            "value": value.value,
            "unit": value.unit,
            "notes": value.notes,
        }

    def _value_from_doc(self, doc: dict) -> MeasurementValue:
        return MeasurementValue(
            field_key=doc.get("field_key", ""),
            value=str(doc.get("value", "")),
            unit=doc.get("unit", "inch"),
            notes=doc.get("notes", ""),
        )

    def _to_doc(self, record: MeasurementRecord) -> dict:
        return {
            "_id": record.id,
            "measurement_number": record.measurement_number,
            "customer_id": record.customer_id,
            "order_id": record.order_id,
            "person_type": record.person_type.value,
            "wearer_name": record.wearer_name,
            "wearer_age": record.wearer_age,
            "wearer_height": record.wearer_height,
            "wearer_weight": record.wearer_weight,
            "unit": record.unit,
            "fit_preference": record.fit_preference.value,
            "values": [self._value_to_doc(v) for v in record.values],
            "notes": record.notes,
            "print_notes": record.print_notes,
            "measured_at": to_bson_value(record.measured_at),
            "measured_by": record.measured_by,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }

    def _from_doc(self, doc: dict) -> MeasurementRecord:
        fit = doc.get("fit_preference", FitPreference.REGULAR.value)
        return MeasurementRecord(
            id=doc["_id"],
            measurement_number=doc["measurement_number"],
            customer_id=doc["customer_id"],
            order_id=doc.get("order_id"),
            person_type=PersonType(doc["person_type"]),
            wearer_name=doc.get("wearer_name", ""),
            wearer_age=doc.get("wearer_age", ""),
            wearer_height=doc.get("wearer_height", ""),
            wearer_weight=doc.get("wearer_weight", ""),
            unit=doc.get("unit", "inch"),
            fit_preference=FitPreference(fit),
            values=[
                self._value_from_doc(v) for v in doc.get("values") or []
            ],
            notes=doc.get("notes", ""),
            print_notes=doc.get("print_notes", ""),
            measured_at=from_bson_date(doc.get("measured_at"))
            or datetime.utcnow().date(),
            measured_by=doc.get("measured_by", ""),
            created_at=doc.get("created_at", datetime.utcnow()),
            updated_at=doc.get("updated_at", datetime.utcnow()),
        )

    def save(self, record: MeasurementRecord) -> MeasurementRecord:
        self._collection.replace_one(
            {"_id": record.id}, self._to_doc(record), upsert=True
        )
        return record

    def find_by_id(self, record_id: str) -> Optional[MeasurementRecord]:
        doc = self._collection.find_one({"_id": record_id})
        return self._from_doc(doc) if doc else None

    def find_by_number(
        self, measurement_number: str
    ) -> Optional[MeasurementRecord]:
        doc = self._collection.find_one(
            {"measurement_number": measurement_number.strip().upper()}
        )
        return self._from_doc(doc) if doc else None

    def list_by_customer(self, customer_id: str) -> List[MeasurementRecord]:
        docs = self._collection.find({"customer_id": customer_id}).sort(
            "created_at", -1
        )
        return [self._from_doc(d) for d in docs]

    def list_by_order(self, order_id: str) -> List[MeasurementRecord]:
        docs = self._collection.find({"order_id": order_id}).sort(
            "created_at", -1
        )
        return [self._from_doc(d) for d in docs]

    def list_all(self) -> List[MeasurementRecord]:
        docs = self._collection.find({}).sort("created_at", -1)
        return [self._from_doc(d) for d in docs]

    def delete(self, record_id: str) -> None:
        self._collection.delete_one({"_id": record_id})
