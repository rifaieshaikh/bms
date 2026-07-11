from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RowIssue:
    row: int
    message: str
    severity: str = "error"  # error | warning


@dataclass
class ImportPreview:
    entity_type: str
    total_rows: int
    valid_rows: int
    issues: List[RowIssue] = field(default_factory=list)
    sample_rows: List[Dict[str, Any]] = field(default_factory=list)
    can_import: bool = False


@dataclass
class ImportResult:
    entity_type: str
    created: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    issues: List[RowIssue] = field(default_factory=list)

    @property
    def total_processed(self) -> int:
        return self.created + self.updated + self.skipped + self.failed


def issues_to_csv(issues: List[RowIssue]) -> str:
    lines = ["row,severity,message"]
    for issue in issues:
        msg = (issue.message or "").replace('"', '""')
        lines.append(f'{issue.row},{issue.severity},"{msg}"')
    return "\n".join(lines) + "\n"
