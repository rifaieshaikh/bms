"""Data Migration hub + stepped wizard (session/step machine) UI tests."""

from __future__ import annotations

import pandas as pd

from vaybooks.bms.application.migration.results import ImportPreview, ImportResult
from vaybooks.bms.application.migration.schemas import (
    ImportEntityType,
    fields_for,
)


class _StubMigration:
    """Minimal MigrationAppService stand-in (no DB, no parsing)."""

    def __init__(self):
        self.imports: list = []

    def get_template(self, entity_type) -> str:
        return "col_a,col_b\n"

    def source_columns(self, df) -> list:
        return list(df.columns)

    def suggest_mapping(self, entity_type, source_cols) -> dict:
        return {f.key: "" for f in fields_for(entity_type)}

    def missing_required(self, entity_type, mapping) -> list:
        return [
            f.key for f in fields_for(entity_type) if f.required and not mapping.get(f.key)
        ]

    def list_mapping_profiles(self, entity_type) -> list:
        return []

    def preview_import(self, entity_type, df, mapping) -> ImportPreview:
        return ImportPreview(
            entity_type=entity_type.value,
            total_rows=len(df),
            valid_rows=len(df),
            sample_rows=[{"customer_name": "QA Party"}],
            can_import=True,
        )

    def run_import(
        self, entity_type, df, mapping, duplicate_policy=None, **kwargs
    ) -> ImportResult:
        self.imports.append(duplicate_policy)
        return ImportResult(entity_type=entity_type.value, created=len(df))


def _page(migration):
    from vaybooks.bms.ui.pages.migration.wizard import render

    render({"migration": migration})


def _app(migration):
    from streamlit.testing.v1 import AppTest

    return AppTest.from_function(_page, kwargs={"migration": migration})


def _seed_loaded_file(at, entity: ImportEntityType, mapping: dict) -> None:
    prefix = f"migration_{entity.value}_"
    at.session_state["migration_entity"] = entity.value
    at.session_state[prefix + "file_key"] = "qa.csv:10"
    at.session_state[prefix + "df"] = pd.DataFrame({"Party": ["QA Party"], "Mobile": ["9999999999"]})
    at.session_state[prefix + "source_cols"] = ["Party", "Mobile"]
    at.session_state[prefix + "mapping"] = mapping


def test_hub_lists_every_entity_and_starts_wizard():
    at = _app(_StubMigration())
    at.run(timeout=20)
    assert not at.exception

    start_buttons = [b for b in at.button if b.label == "Start import"]
    assert len(start_buttons) == 5

    start_buttons[2].click().run(timeout=20)
    assert not at.exception
    assert at.session_state["migration_entity"] == ImportEntityType.CUSTOMERS.value
    assert "Migrate Customers" in [el.value for el in at.title]


def test_upload_step_blocks_next_until_a_file_is_loaded():
    at = _app(_StubMigration())
    at.session_state["migration_entity"] = ImportEntityType.CATEGORIES.value
    at.run(timeout=20)
    assert not at.exception

    next_btn = next(b for b in at.button if b.label == "Next")
    assert next_btn.disabled
    assert any("Upload a file to continue." in el.value for el in at.info)

    # Cancelling from step 1 clears the uploader widget key without erroring.
    next(b for b in at.button if b.label == "Cancel").click().run(timeout=20)
    assert not at.exception
    assert "migration_entity" not in at.session_state


def test_dry_run_then_confirm_import_runs_with_selected_policy():
    migration = _StubMigration()
    entity = ImportEntityType.CUSTOMERS
    at = _app(migration)
    _seed_loaded_file(at, entity, {"customer_name": "Party", "phone_number": "Mobile"})
    at.session_state[f"migration_{entity.value}_step"] = 2
    at.run(timeout=20)
    assert not at.exception

    # Next is gated until a dry-run reports importable rows.
    assert next(b for b in at.button if b.label == "Next").disabled

    at.radio[0].set_value("Update").run(timeout=20)
    next(b for b in at.button if b.label == "Run dry-run").click().run(timeout=20)
    assert not at.exception
    assert not next(b for b in at.button if b.label == "Next").disabled

    next(b for b in at.button if b.label == "Next").click().run(timeout=20)
    assert at.session_state[f"migration_{entity.value}_step"] == 3

    next(b for b in at.button if b.label == "Confirm import").click().run(timeout=20)
    assert not at.exception
    assert [p.value for p in migration.imports] == ["update"]
    assert any("Created 1" in el.value for el in at.success)


def test_cancel_clears_state_and_returns_to_hub():
    entity = ImportEntityType.VENDORS
    at = _app(_StubMigration())
    _seed_loaded_file(at, entity, {"vendor_name": "Party", "phone_number": "Mobile"})
    at.session_state[f"migration_{entity.value}_step"] = 1
    at.run(timeout=20)
    assert not at.exception

    next(b for b in at.button if b.label == "Cancel").click().run(timeout=20)
    assert not at.exception
    assert "migration_entity" not in at.session_state
    assert f"migration_{entity.value}_df" not in at.session_state
    assert "Data Migration" in [el.value for el in at.title]
