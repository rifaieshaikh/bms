"""Data Migration — entity hub plus a stepped, full-page import wizard."""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

import pandas as pd
import streamlit as st

from vaybooks.bms.application.migration.results import issues_to_csv
from vaybooks.bms.application.migration.schemas import (
    ENTITY_TITLES,
    NOT_MAPPED,
    DuplicatePolicy,
    ImportEntityType,
    fields_for,
)
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.keyboard.actions import consume_action
from vaybooks.bms.ui.keyboard.wired import mark_wired
from vaybooks.bms.ui.styles import metric_grid, panel

PAGE_KEY = "data_migration"
ENTITY_KEY = "migration_entity"

NOT_MAPPED_LABEL = "— Not mapped —"
NO_PROFILE_LABEL = "— None —"

STEP_TITLES = [
    "Upload file",
    "Map columns",
    "Duplicate policy & dry-run",
    "Import",
]
STEP_COUNT = len(STEP_TITLES)

_POLICIES: Dict[str, DuplicatePolicy] = {
    "Skip": DuplicatePolicy.SKIP,
    "Update": DuplicatePolicy.UPDATE,
    "Fail": DuplicatePolicy.FAIL,
}

_ENTITY_ORDER: List[ImportEntityType] = [
    ImportEntityType.CATEGORIES,
    ImportEntityType.PRODUCTS,
    ImportEntityType.CUSTOMERS,
    ImportEntityType.VENDORS,
]

_ENTITY_ICONS: Dict[ImportEntityType, str] = {
    ImportEntityType.CATEGORIES: ":material/account_tree:",
    ImportEntityType.PRODUCTS: ":material/inventory_2:",
    ImportEntityType.CUSTOMERS: ":material/groups:",
    ImportEntityType.VENDORS: ":material/local_shipping:",
}

_ENTITY_HINTS: Dict[ImportEntityType, str] = {
    ImportEntityType.CATEGORIES: (
        "Import the category tree first — products reference categories by name or path."
    ),
    ImportEntityType.PRODUCTS: (
        "SKU, name, rates, and opening stock. Needs categories to exist first."
    ),
    ImportEntityType.CUSTOMERS: (
        "Names, contacts, GST details, segments, and opening balances."
    ),
    ImportEntityType.VENDORS: (
        "Names, contacts, GST details, bank details, and opening balances."
    ),
}


# --- session helpers ---------------------------------------------------------
def _sk(entity: ImportEntityType, name: str) -> str:
    return f"migration_{entity.value}_{name}"


def _reset_downstream(entity: ImportEntityType, from_step: str) -> None:
    keys = {
        "upload": ["df", "source_cols", "mapping", "profile_warnings", "preview", "result"],
        "mapping": ["preview", "result"],
        "preview": ["result"],
    }
    for key in keys.get(from_step, []):
        st.session_state.pop(_sk(entity, key), None)
    if from_step == "upload":
        # Stale column choices would no longer exist among the new file's options.
        for field in fields_for(entity):
            st.session_state.pop(_sk(entity, f"map_{field.key}"), None)


def _parse_entity(raw: Optional[str]) -> Optional[ImportEntityType]:
    if not raw:
        return None
    try:
        return ImportEntityType(str(raw))
    except ValueError:
        return None


def _selected_entity() -> Optional[ImportEntityType]:
    """Active entity from a deep link (``?entity=products``) else session state."""
    deep_link = _parse_entity(navigation.consume_list_param(PAGE_KEY, "entity"))
    if deep_link is not None:
        st.session_state[ENTITY_KEY] = deep_link.value
        return deep_link
    return _parse_entity(st.session_state.get(ENTITY_KEY))


def _step(entity: ImportEntityType) -> int:
    try:
        value = int(st.session_state.get(_sk(entity, "step")) or 0)
    except (TypeError, ValueError):
        value = 0
    return max(0, min(value, STEP_COUNT - 1))


def _set_step(entity: ImportEntityType, step: int) -> None:
    st.session_state[_sk(entity, "step")] = max(0, min(step, STEP_COUNT - 1))


def _clear_entity_state(entity: ImportEntityType) -> None:
    names = [
        "step",
        "file_key",
        "df",
        "source_cols",
        "mapping",
        "profile_warnings",
        "preview",
        "result",
        "policy",
        "policy_choice",
        "uploader",
        "load_profile",
        "save_name",
    ]
    names += [f"map_{field.key}" for field in fields_for(entity)]
    for name in names:
        st.session_state.pop(_sk(entity, name), None)


def _go_to_hub(entity: ImportEntityType) -> None:
    _clear_entity_state(entity)
    st.session_state.pop(ENTITY_KEY, None)
    st.rerun()


def _policy(entity: ImportEntityType) -> DuplicatePolicy:
    label = st.session_state.get(_sk(entity, "policy")) or "Skip"
    return _POLICIES.get(label, DuplicatePolicy.SKIP)


def _issues_frame(issues) -> pd.DataFrame:
    return pd.DataFrame(
        [{"row": i.row, "severity": i.severity, "message": i.message} for i in issues]
    )


# --- shared wizard chrome ----------------------------------------------------
def _nav_row(
    entity: ImportEntityType,
    step: int,
    *,
    can_next: bool = True,
    next_label: str = "Next",
    next_icon: Optional[str] = None,
    on_next: Optional[Callable[[], None]] = None,
) -> None:
    """Cancel / Back / Next row shared by every step."""
    cols = st.columns(3)
    if cols[0].button(
        "Cancel", key=_sk(entity, f"nav_cancel_{step}"), width="stretch"
    ):
        _go_to_hub(entity)
    if step > 0 and cols[1].button(
        "Back", key=_sk(entity, f"nav_back_{step}"), width="stretch"
    ):
        _set_step(entity, step - 1)
        st.rerun()
    if cols[2].button(
        next_label,
        key=_sk(entity, f"nav_next_{step}"),
        type="primary",
        disabled=not can_next,
        icon=next_icon,
        width="stretch",
    ):
        if on_next is not None:
            on_next()
        else:
            _set_step(entity, step + 1)
            st.rerun()


# --- step 1: upload ----------------------------------------------------------
def _step_upload(migration, entity: ImportEntityType) -> None:
    with panel(f"template_{entity.value}"):
        st.subheader("Optional template")
        st.caption(
            "Download a VayBooks-shaped sample if you prefer to reformat the file."
        )
        st.download_button(
            "Download CSV template",
            migration.get_template(entity),
            file_name=f"vaybooks_{entity.value}_template.csv",
            mime="text/csv",
            key=_sk(entity, "dl_template"),
            width="stretch",
        )
    mark_wired("migration.download_template", "migration.upload")

    uploaded = st.file_uploader(
        "CSV or Excel",
        type=["csv", "xlsx", "xls"],
        key=_sk(entity, "uploader"),
    )
    if uploaded is not None:
        file_bytes = uploaded.getvalue()
        file_key = f"{uploaded.name}:{len(file_bytes)}"
        if file_key != st.session_state.get(_sk(entity, "file_key")):
            _reset_downstream(entity, "upload")
            try:
                df = migration.parse_upload(file_bytes, uploaded.name)
            except Exception as exc:
                st.error(f"Could not read file: {exc}")
                _nav_row(entity, 0, can_next=False)
                return
            cols = migration.source_columns(df)
            st.session_state[_sk(entity, "file_key")] = file_key
            st.session_state[_sk(entity, "df")] = df
            st.session_state[_sk(entity, "source_cols")] = cols
            st.session_state[_sk(entity, "mapping")] = migration.suggest_mapping(
                entity, cols
            )
            st.session_state[_sk(entity, "profile_warnings")] = []

    df: pd.DataFrame | None = st.session_state.get(_sk(entity, "df"))
    source_cols = st.session_state.get(_sk(entity, "source_cols")) or []
    if df is None:
        st.info("Upload a file to continue.")
    else:
        st.success(f"Loaded {len(df)} rows · {len(source_cols)} columns")
        with st.expander("Preview source rows", expanded=False):
            st.dataframe(df.head(20), width="stretch")

    _nav_row(entity, 0, can_next=df is not None)


# --- step 2: mapping ---------------------------------------------------------
def _render_profile_controls(migration, entity: ImportEntityType) -> None:
    source_cols = st.session_state.get(_sk(entity, "source_cols")) or []
    profiles = migration.list_mapping_profiles(entity)
    profile_names = [NO_PROFILE_LABEL] + [p.name for p in profiles]
    load_col, save_col = st.columns(2)
    with load_col:
        selected_profile = st.selectbox(
            "Load saved mapping",
            profile_names,
            key=_sk(entity, "load_profile"),
        )
        if selected_profile != NO_PROFILE_LABEL:
            mark_wired("migration.apply_profile")
            from_shortcut = consume_action("migration.apply_profile")
            if st.button("Apply profile", key=_sk(entity, "apply_profile")) or from_shortcut:
                profile = next(p for p in profiles if p.name == selected_profile)
                mapping, warnings = migration.apply_profile_to_mapping(
                    entity,
                    source_cols,
                    profile.mapping,
                    st.session_state.get(_sk(entity, "mapping")),
                )
                st.session_state[_sk(entity, "mapping")] = mapping
                st.session_state[_sk(entity, "profile_warnings")] = warnings
                for field in fields_for(entity):
                    source = mapping.get(field.key) or NOT_MAPPED
                    st.session_state[_sk(entity, f"map_{field.key}")] = (
                        NOT_MAPPED_LABEL if not source else source
                    )
                _reset_downstream(entity, "mapping")
                st.rerun()
    with save_col:
        profile_name = st.text_input(
            "Save mapping as",
            key=_sk(entity, "save_name"),
            placeholder="e.g. Old ERP customers",
        )
        if st.button("Save mapping", key=_sk(entity, "save_profile")):
            mapping = st.session_state.get(_sk(entity, "mapping")) or {}
            try:
                migration.save_mapping_profile(entity, profile_name, mapping)
                st.success(f"Saved mapping '{profile_name.strip()}'")
            except Exception as exc:
                st.error(str(exc))


def _step_mapping(migration, entity: ImportEntityType) -> None:
    source_cols = st.session_state.get(_sk(entity, "source_cols")) or []
    st.caption(
        "Point each VayBooks field at a column from your file. "
        "Required fields are marked with an asterisk."
    )

    _render_profile_controls(migration, entity)

    for warning in st.session_state.get(_sk(entity, "profile_warnings")) or []:
        st.warning(warning)

    previous: Dict[str, str] = dict(
        st.session_state.get(_sk(entity, "mapping")) or {}
    )
    options = [NOT_MAPPED_LABEL] + source_cols
    updated_mapping: Dict[str, str] = {}
    for field in fields_for(entity):
        current = previous.get(field.key) or NOT_MAPPED
        index = source_cols.index(current) + 1 if current in source_cols else 0
        choice = st.selectbox(
            f"{field.label}{' *' if field.required else ''}",
            options,
            index=index,
            key=_sk(entity, f"map_{field.key}"),
            help=f"Target field: {field.key}",
        )
        updated_mapping[field.key] = "" if choice == NOT_MAPPED_LABEL else choice
    st.session_state[_sk(entity, "mapping")] = updated_mapping
    if updated_mapping != previous:
        _reset_downstream(entity, "mapping")

    missing = migration.missing_required(entity, updated_mapping)
    if missing:
        st.error("Map all required fields before continuing: " + ", ".join(missing))

    _nav_row(entity, 1, can_next=not missing)


# --- step 3: policy & dry-run ------------------------------------------------
def _step_dry_run(migration, entity: ImportEntityType) -> None:
    df: pd.DataFrame | None = st.session_state.get(_sk(entity, "df"))
    mapping = st.session_state.get(_sk(entity, "mapping")) or {}
    if df is None:
        st.warning("Upload a file first.")
        _nav_row(entity, 2, can_next=False)
        return

    labels = list(_POLICIES.keys())
    stored = st.session_state.get(_sk(entity, "policy")) or labels[0]
    policy_label = st.radio(
        "When a row already exists",
        labels,
        index=labels.index(stored) if stored in labels else 0,
        horizontal=True,
        key=_sk(entity, "policy_choice"),
        help=(
            "Skip keeps existing data. Update overwrites master fields. "
            "Fail stops on first duplicate."
        ),
    )
    st.session_state[_sk(entity, "policy")] = policy_label

    mark_wired("migration.dry_run")
    from_shortcut = consume_action("migration.dry_run")
    if (
        st.button(
            "Run dry-run",
            key=_sk(entity, "dry_run"),
            type="primary",
            icon=":material/rule:",
        )
        or from_shortcut
    ):
        with st.spinner("Validating rows…"):
            preview = migration.preview_import(entity, df, mapping)
        st.session_state[_sk(entity, "preview")] = preview
        st.session_state.pop(_sk(entity, "result"), None)

    preview = st.session_state.get(_sk(entity, "preview"))
    if preview is None:
        st.info("Run a dry-run to validate the file before importing.")
        _nav_row(entity, 2, can_next=False)
        return

    metric_grid(
        [
            ("Rows", preview.total_rows),
            ("Valid", preview.valid_rows, "good" if preview.valid_rows else "danger"),
            (
                "Issues",
                len(preview.issues),
                "warn" if preview.issues else "neutral",
            ),
        ],
        suffix=f"migration_preview_{entity.value}",
    )
    if preview.sample_rows:
        st.markdown("**Sample of mapped rows**")
        st.dataframe(pd.DataFrame(preview.sample_rows), width="stretch")
    if preview.issues:
        st.markdown("**Issues**")
        st.dataframe(_issues_frame(preview.issues), width="stretch")
    if not preview.can_import:
        st.warning("Nothing valid to import. Fix the file or the mapping and retry.")

    _nav_row(entity, 2, can_next=bool(preview.can_import))


# --- step 4: import ---------------------------------------------------------
def _run_import(migration, entity: ImportEntityType) -> None:
    df = st.session_state.get(_sk(entity, "df"))
    mapping = st.session_state.get(_sk(entity, "mapping")) or {}
    with st.spinner("Importing…"):
        result = migration.run_import(
            entity, df, mapping, duplicate_policy=_policy(entity)
        )
    st.session_state[_sk(entity, "result")] = result
    st.rerun()


def _render_result(entity: ImportEntityType, result) -> None:
    st.success(
        f"Created {result.created} · Updated {result.updated} · "
        f"Skipped {result.skipped} · Failed {result.failed}"
    )
    if result.issues:
        st.markdown("**Rows that need attention**")
        st.dataframe(_issues_frame(result.issues), width="stretch")
        mark_wired("migration.download_errors")
        st.download_button(
            "Download error report",
            issues_to_csv(result.issues),
            file_name=f"migration_{entity.value}_errors.csv",
            mime="text/csv",
            key=_sk(entity, "dl_errors"),
        )

    cols = st.columns(2)
    if cols[0].button(
        "Import another file", key=_sk(entity, "import_again"), width="stretch"
    ):
        _clear_entity_state(entity)
        _set_step(entity, 0)
        st.rerun()
    if cols[1].button(
        "Back to Data Migration",
        key=_sk(entity, "back_to_hub"),
        type="primary",
        width="stretch",
    ):
        _go_to_hub(entity)


def _step_import(migration, entity: ImportEntityType) -> None:
    result = st.session_state.get(_sk(entity, "result"))
    if result is not None:
        _render_result(entity, result)
        return

    preview = st.session_state.get(_sk(entity, "preview"))
    if preview is None or not preview.can_import:
        st.warning("Run a dry-run with at least one valid row first.")
        _nav_row(entity, 3, can_next=False)
        return

    st.info(
        f"About to import **{preview.valid_rows}** of {preview.total_rows} rows into "
        f"**{ENTITY_TITLES[entity]}** with duplicate policy "
        f"**{st.session_state.get(_sk(entity, 'policy')) or 'Skip'}**."
    )
    if preview.issues:
        st.caption(
            f"{len(preview.issues)} row(s) flagged in the dry-run will be reported "
            "as failures."
        )

    mark_wired("migration.confirm_import")
    if consume_action("migration.confirm_import"):
        _run_import(migration, entity)
    _nav_row(
        entity,
        3,
        next_label="Confirm import",
        next_icon=":material/upload:",
        on_next=lambda: _run_import(migration, entity),
    )


# --- hub --------------------------------------------------------------------
def _entity_card(migration, entity: ImportEntityType, order: int) -> None:
    title = ENTITY_TITLES[entity]
    with st.container(border=True):
        st.markdown(f"**{order}. {title}**")
        st.caption(_ENTITY_HINTS[entity])

        in_progress = st.session_state.get(_sk(entity, "df")) is not None
        result = st.session_state.get(_sk(entity, "result"))
        if result is not None:
            st.caption(
                f"Last run: created {result.created} · updated {result.updated} · "
                f"skipped {result.skipped} · failed {result.failed}"
            )
        elif in_progress:
            st.caption(f"In progress — step {_step(entity) + 1} of {STEP_COUNT}")

        if result is not None:
            label = "View last result"
        elif in_progress:
            label = "Resume import"
        else:
            label = "Start import"
        if st.button(
            label,
            key=_sk(entity, "start"),
            type="primary",
            icon=_ENTITY_ICONS[entity],
            width="stretch",
        ):
            st.session_state[ENTITY_KEY] = entity.value
            if not in_progress:
                _set_step(entity, 0)
            st.rerun()

        st.download_button(
            "Download CSV template",
            migration.get_template(entity),
            file_name=f"vaybooks_{entity.value}_template.csv",
            mime="text/csv",
            key=_sk(entity, "dl_template_hub"),
            width="stretch",
        )


def _render_hub(services: dict) -> None:
    migration = services["migration"]
    st.title("Data Migration")
    st.caption(
        "Bring existing data in from any CSV or Excel layout. Recommended order: "
        "Categories → Products → Customers → Vendors."
    )
    st.markdown("#### Choose what to import")
    for row_start in range(0, len(_ENTITY_ORDER), 2):
        row = _ENTITY_ORDER[row_start : row_start + 2]
        cols = st.columns(2)
        for offset, entity in enumerate(row):
            with cols[offset]:
                _entity_card(migration, entity, row_start + offset + 1)

    with panel("migration_how_it_works"):
        st.subheader("How it works")
        st.markdown(
            "1. **Upload** a CSV or Excel export from your old system.\n"
            "2. **Map columns** to VayBooks fields — save the mapping to reuse it.\n"
            "3. **Dry-run** to validate every row before anything is written.\n"
            "4. **Import** the valid rows and download a report of any failures."
        )


# --- entry point ------------------------------------------------------------
def render_migration_wizard(services: dict, entity: ImportEntityType) -> None:
    """Full-page stepped wizard for one entity."""
    migration = services["migration"]
    step = _step(entity)
    st.title(f"Migrate {ENTITY_TITLES[entity]}")
    st.progress(
        (step + 1) / STEP_COUNT,
        text=f"Step {step + 1} of {STEP_COUNT} — {STEP_TITLES[step]}",
    )

    steps = [_step_upload, _step_mapping, _step_dry_run, _step_import]
    steps[step](migration, entity)


def render(services: dict) -> None:
    entity = _selected_entity()
    if entity is None:
        _render_hub(services)
        return
    render_migration_wizard(services, entity)
