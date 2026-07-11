from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from vaybooks.bms.application.migration.results import ImportPreview, RowIssue
from vaybooks.bms.application.migration.schemas import ImportEntityType, required_keys


def _nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def validate_mapped_rows(
    entity_type: ImportEntityType,
    rows: List[Dict[str, Any]],
) -> ImportPreview:
    issues: List[RowIssue] = []
    valid = 0
    req = required_keys(entity_type)
    for row in rows:
        row_num = int(row.get("_row") or 0)
        row_errors = []
        for key in req:
            if not _nonempty(row.get(key)):
                row_errors.append(f"Required field '{key}' is empty")
        if entity_type == ImportEntityType.PRODUCTS:
            opening = row.get("opening_qty")
            if opening is not None and opening < 0:
                row_errors.append("opening_qty cannot be negative")
        if row_errors:
            for message in row_errors:
                issues.append(RowIssue(row=row_num, message=message))
        else:
            valid += 1

    sample = [{k: v for k, v in r.items() if k != "_row"} for r in rows[:10]]
    return ImportPreview(
        entity_type=entity_type.value,
        total_rows=len(rows),
        valid_rows=valid,
        issues=issues,
        sample_rows=sample,
        can_import=valid > 0 and not any(i.severity == "error" for i in issues),
    )


def resolve_category_id(
    category_value: str,
    categories_by_path: Dict[str, str],
    categories_by_name: Dict[str, List[str]],
) -> Tuple[Optional[str], Optional[str]]:
    """Return (category_id, error_message)."""
    text = (category_value or "").strip()
    if not text:
        return None, None
    path_key = text.lower()
    if path_key in categories_by_path:
        return categories_by_path[path_key], None
    # Support "Parent > Child" path
    if ">" in text:
        normalized = " > ".join(part.strip() for part in text.split(">") if part.strip())
        if normalized.lower() in categories_by_path:
            return categories_by_path[normalized.lower()], None
    matches = categories_by_name.get(text.lower(), [])
    if len(matches) == 1:
        return matches[0], None
    if len(matches) > 1:
        return None, f"Ambiguous category name '{text}'"
    return None, f"Category '{text}' not found"
