from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from vaybooks.bms.application.migration.schemas import (
    NOT_MAPPED,
    FieldType,
    ImportEntityType,
    TargetField,
    fields_for,
    required_keys,
)
from vaybooks.bms.domain.shared.enums import PartyRegistrationType
from vaybooks.bms.domain.shared.india import INDIAN_STATES


def _normalize(value: str) -> str:
    text = (value or "").strip().lower()
    text = re.sub(r"[_\-./]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def suggest_mapping(
    entity_type: ImportEntityType, source_columns: List[str]
) -> Dict[str, str]:
    """Auto-suggest target→source mapping using canonical names and aliases."""
    sources_by_norm: Dict[str, str] = {}
    for col in source_columns:
        norm = _normalize(col)
        if norm and norm not in sources_by_norm:
            sources_by_norm[norm] = col

    used: set[str] = set()
    mapping: Dict[str, str] = {}
    for field in fields_for(entity_type):
        candidates = [_normalize(field.key), _normalize(field.label), *[_normalize(a) for a in field.aliases]]
        chosen = NOT_MAPPED
        for candidate in candidates:
            if candidate and candidate in sources_by_norm:
                source = sources_by_norm[candidate]
                if source not in used:
                    chosen = source
                    used.add(source)
                    break
        mapping[field.key] = chosen
    return mapping


def apply_saved_profile(
    mapping: Dict[str, str],
    source_columns: List[str],
    profile_mapping: Dict[str, str],
) -> Tuple[Dict[str, str], List[str]]:
    """Apply a saved profile onto current sources; return mapping + missing source warnings."""
    source_set = set(source_columns)
    result = dict(mapping)
    warnings: List[str] = []
    for target, source in (profile_mapping or {}).items():
        if not source:
            result[target] = NOT_MAPPED
            continue
        if source in source_set:
            result[target] = source
        else:
            warnings.append(
                f"Profile column '{source}' for '{target}' is missing from this file"
            )
            if result.get(target) == source:
                result[target] = NOT_MAPPED
    return result, warnings


def missing_required(entity_type: ImportEntityType, mapping: Dict[str, str]) -> List[str]:
    missing = []
    for key in required_keys(entity_type):
        if not (mapping.get(key) or "").strip():
            missing.append(key)
    return missing


def _parse_bool(value: Any) -> Optional[bool]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if not text:
        return None
    if text in {"1", "true", "yes", "y", "active"}:
        return True
    if text in {"0", "false", "no", "n", "inactive"}:
        return False
    return None


def _parse_float(value: Any) -> Optional[float]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    return float(text)


_STATE_BY_NAME = {s["name"].strip().lower(): s["code"] for s in INDIAN_STATES}
_STATE_CODES = {s["code"] for s in INDIAN_STATES}


def _parse_state_code(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    if not text:
        return ""
    if text in _STATE_CODES:
        return text
    if text.isdigit():
        padded = text.zfill(2)
        if padded in _STATE_CODES:
            return padded
    return _STATE_BY_NAME.get(text.lower(), text)


def _parse_registration_type(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return PartyRegistrationType.UNREGISTERED.value
    text = str(value).strip()
    if not text:
        return PartyRegistrationType.UNREGISTERED.value
    for item in PartyRegistrationType:
        if text.lower() == item.value.lower() or text.lower() == item.name.lower():
            return item.value
    return text


def coerce_value(field: TargetField, raw: Any) -> Any:
    if field.field_type == FieldType.FLOAT:
        return _parse_float(raw)
    if field.field_type == FieldType.BOOL:
        parsed = _parse_bool(raw)
        return True if parsed is None else parsed
    if field.field_type == FieldType.STATE_CODE:
        return _parse_state_code(raw)
    if field.field_type == FieldType.REGISTRATION_TYPE:
        return _parse_registration_type(raw)
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return ""
    return str(raw).strip()


def apply_mapping_to_rows(
    entity_type: ImportEntityType,
    df: pd.DataFrame,
    mapping: Dict[str, str],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for idx, series in df.iterrows():
        mapped: Dict[str, Any] = {"_row": int(idx) + 2}  # header is row 1
        for field in fields_for(entity_type):
            source = (mapping.get(field.key) or "").strip()
            if not source or source not in df.columns:
                mapped[field.key] = None if field.field_type == FieldType.FLOAT else (
                    True if field.key == "is_active" else ""
                )
                if field.field_type == FieldType.BOOL and field.key != "is_active":
                    mapped[field.key] = None
                continue
            mapped[field.key] = coerce_value(field, series.get(source))
        rows.append(mapped)
    return rows
