"""Merge tests/qa/test-case-executions.json into qa-output test case configs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _bms_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_test_cases_payload(test_cases_path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(test_cases_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    test_cases = payload.get("testCases")
    if not isinstance(test_cases, list):
        return None
    return payload


def sync_additional_test_cases(bms_root: Path | None = None) -> bool:
    """Inject committed test cases from additional-test-cases.json when missing."""
    root = bms_root or _bms_root()
    additions_path = root / "tests" / "qa" / "additional-test-cases.json"
    test_cases_path = root / "qa-output" / "test-cases" / "test-cases.json"

    if not additions_path.is_file() or not test_cases_path.is_file():
        return False

    try:
        additions: list[dict[str, Any]] = json.loads(
            additions_path.read_text(encoding="utf-8")
        )
    except (json.JSONDecodeError, OSError):
        return False

    payload = _load_test_cases_payload(test_cases_path)
    if payload is None:
        return False

    test_cases = payload["testCases"]
    existing_ids = {tc.get("testCaseId") for tc in test_cases}
    changed = False

    for test_case in additions:
        test_case_id = test_case.get("testCaseId")
        if not test_case_id or test_case_id in existing_ids:
            continue
        test_cases.append(test_case)
        existing_ids.add(test_case_id)
        changed = True

    if changed:
        test_cases_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    return changed


def sync_execution_overrides(bms_root: Path | None = None) -> bool:
    """Apply execution overrides from test-case-executions.json into test-cases.json."""
    root = bms_root or _bms_root()
    overrides_path = root / "tests" / "qa" / "test-case-executions.json"
    test_cases_path = root / "qa-output" / "test-cases" / "test-cases.json"

    if not overrides_path.is_file() or not test_cases_path.is_file():
        return False

    try:
        overrides: dict[str, dict[str, Any]] = json.loads(
            overrides_path.read_text(encoding="utf-8")
        )
    except (json.JSONDecodeError, OSError):
        return False

    payload = _load_test_cases_payload(test_cases_path)
    if payload is None:
        return False

    test_cases = payload["testCases"]
    changed = False
    for test_case in test_cases:
        test_case_id = test_case.get("testCaseId")
        override = overrides.get(test_case_id)
        if not override:
            continue

        execution = dict(test_case.get("execution") or {})
        execution.update(override)
        execution["type"] = override.get("type") or execution.get("type") or "db"
        test_case["execution"] = execution
        changed = True

    if changed:
        test_cases_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    return changed


def sync_qa_test_cases(bms_root: Path | None = None) -> dict[str, bool]:
    """Merge additional test cases and execution overrides into qa-output."""
    return {
        "additionalTestCases": sync_additional_test_cases(bms_root),
        "executionOverrides": sync_execution_overrides(bms_root),
    }


if __name__ == "__main__":
    print(json.dumps(sync_qa_test_cases()))
