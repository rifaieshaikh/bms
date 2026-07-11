from __future__ import annotations

from typing import Dict

import pandas as pd
import streamlit as st

from vaybooks.bms.application.migration.schemas import (
    NOT_MAPPED,
    DuplicatePolicy,
    ImportEntityType,
    ENTITY_TITLES,
    fields_for,
)
from vaybooks.bms.application.migration.results import issues_to_csv
from vaybooks.bms.ui.styles import panel


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


def render_migration_wizard(services: dict, entity_type: ImportEntityType) -> None:
    migration = services["migration"]
    title = ENTITY_TITLES[entity_type]
    st.title(f"Migrate {title}")
    st.caption(
        "Recommended order: Categories → Products → Customers → Vendors. "
        "Upload any CSV/Excel layout, map columns, save the mapping, then import."
    )

    with panel(f"template_{entity_type.value}"):
        st.subheader("Optional template")
        st.caption("Download a VayBooks-shaped sample if you prefer to reformat the file.")
        st.download_button(
            "Download CSV template",
            migration.get_template(entity_type),
            file_name=f"vaybooks_{entity_type.value}_template.csv",
            mime="text/csv",
            key=_sk(entity_type, "dl_template"),
            use_container_width=True,
        )

    st.divider()
    st.subheader("1. Upload file")
    uploaded = st.file_uploader(
        "CSV or Excel",
        type=["csv", "xlsx", "xls"],
        key=_sk(entity_type, "uploader"),
    )
    if uploaded is not None:
        file_bytes = uploaded.getvalue()
        file_key = f"{uploaded.name}:{len(file_bytes)}"
        prev_key = st.session_state.get(_sk(entity_type, "file_key"))
        if file_key != prev_key:
            _reset_downstream(entity_type, "upload")
            try:
                df = migration.parse_upload(file_bytes, uploaded.name)
            except Exception as exc:
                st.error(f"Could not read file: {exc}")
                return
            cols = migration.source_columns(df)
            st.session_state[_sk(entity_type, "file_key")] = file_key
            st.session_state[_sk(entity_type, "df")] = df
            st.session_state[_sk(entity_type, "source_cols")] = cols
            st.session_state[_sk(entity_type, "mapping")] = migration.suggest_mapping(
                entity_type, cols
            )
            st.session_state[_sk(entity_type, "profile_warnings")] = []

    df: pd.DataFrame | None = st.session_state.get(_sk(entity_type, "df"))
    source_cols = st.session_state.get(_sk(entity_type, "source_cols")) or []
    if df is None:
        st.info("Upload a file to continue.")
        return

    st.success(f"Loaded {len(df)} rows · {len(source_cols)} columns")
    with st.expander("Preview source rows", expanded=False):
        st.dataframe(df.head(20), use_container_width=True)

    st.divider()
    st.subheader("2. Map columns")
    profiles = migration.list_mapping_profiles(entity_type)
    profile_names = ["— None —"] + [p.name for p in profiles]
    load_col, save_col = st.columns(2)
    with load_col:
        selected_profile = st.selectbox(
            "Load saved mapping",
            profile_names,
            key=_sk(entity_type, "load_profile"),
        )
        if selected_profile != "— None —":
            if st.button("Apply profile", key=_sk(entity_type, "apply_profile")):
                profile = next(p for p in profiles if p.name == selected_profile)
                mapping, warnings = migration.apply_profile_to_mapping(
                    entity_type,
                    source_cols,
                    profile.mapping,
                    st.session_state.get(_sk(entity_type, "mapping")),
                )
                st.session_state[_sk(entity_type, "mapping")] = mapping
                st.session_state[_sk(entity_type, "profile_warnings")] = warnings
                for field in fields_for(entity_type):
                    source = mapping.get(field.key) or NOT_MAPPED
                    widget_key = _sk(entity_type, f"map_{field.key}")
                    st.session_state[widget_key] = (
                        "— Not mapped —" if not source else source
                    )
                _reset_downstream(entity_type, "mapping")
                st.rerun()
    with save_col:
        profile_name = st.text_input(
            "Save mapping as",
            key=_sk(entity_type, "save_name"),
            placeholder="e.g. Old ERP customers",
        )
        if st.button("Save mapping", key=_sk(entity_type, "save_profile")):
            mapping = st.session_state.get(_sk(entity_type, "mapping")) or {}
            try:
                migration.save_mapping_profile(entity_type, profile_name, mapping)
                st.success(f"Saved mapping '{profile_name.strip()}'")
            except Exception as exc:
                st.error(str(exc))

    for warning in st.session_state.get(_sk(entity_type, "profile_warnings")) or []:
        st.warning(warning)

    mapping: Dict[str, str] = dict(st.session_state.get(_sk(entity_type, "mapping")) or {})
    options = ["— Not mapped —"] + source_cols
    updated_mapping: Dict[str, str] = {}
    for field in fields_for(entity_type):
        current = mapping.get(field.key) or NOT_MAPPED
        label = f"{field.label}{' *' if field.required else ''}"
        index = 0
        if current in source_cols:
            index = source_cols.index(current) + 1
        choice = st.selectbox(
            label,
            options,
            index=index,
            key=_sk(entity_type, f"map_{field.key}"),
            help=f"Target field: {field.key}",
        )
        updated_mapping[field.key] = "" if choice == "— Not mapped —" else choice
    st.session_state[_sk(entity_type, "mapping")] = updated_mapping

    missing = migration.missing_required(entity_type, updated_mapping)
    if missing:
        st.error(
            "Map all required fields before continuing: "
            + ", ".join(missing)
        )
        return

    st.divider()
    st.subheader("3. Duplicate policy & dry-run")
    policy_label = st.radio(
        "When a row already exists",
        ["Skip", "Update", "Fail"],
        index=0,
        horizontal=True,
        key=_sk(entity_type, "policy"),
        help="Skip keeps existing data. Update overwrites master fields. Fail stops on first duplicate.",
    )
    policy = {
        "Skip": DuplicatePolicy.SKIP,
        "Update": DuplicatePolicy.UPDATE,
        "Fail": DuplicatePolicy.FAIL,
    }[policy_label]

    if st.button("Run dry-run", key=_sk(entity_type, "dry_run"), type="primary"):
        preview = migration.preview_import(entity_type, df, updated_mapping)
        st.session_state[_sk(entity_type, "preview")] = preview
        st.session_state.pop(_sk(entity_type, "result"), None)

    preview = st.session_state.get(_sk(entity_type, "preview"))
    if preview is None:
        return

    st.write(
        f"Rows: **{preview.total_rows}** · Valid: **{preview.valid_rows}** · "
        f"Issues: **{len(preview.issues)}**"
    )
    if preview.sample_rows:
        st.dataframe(pd.DataFrame(preview.sample_rows), use_container_width=True)
    if preview.issues:
        st.dataframe(
            pd.DataFrame(
                [{"row": i.row, "severity": i.severity, "message": i.message} for i in preview.issues]
            ),
            use_container_width=True,
        )

    if not preview.can_import:
        st.warning("Nothing valid to import.")
        return

    st.divider()
    st.subheader("4. Import")
    if st.button("Confirm import", key=_sk(entity_type, "confirm"), type="primary"):
        with st.spinner("Importing…"):
            result = migration.run_import(
                entity_type, df, updated_mapping, duplicate_policy=policy
            )
        st.session_state[_sk(entity_type, "result")] = result

    result = st.session_state.get(_sk(entity_type, "result"))
    if result is None:
        return

    st.success(
        f"Created {result.created} · Updated {result.updated} · "
        f"Skipped {result.skipped} · Failed {result.failed}"
    )
    if result.issues:
        st.dataframe(
            pd.DataFrame(
                [{"row": i.row, "severity": i.severity, "message": i.message} for i in result.issues]
            ),
            use_container_width=True,
        )
        st.download_button(
            "Download error report",
            issues_to_csv(result.issues),
            file_name=f"migration_{entity_type.value}_errors.csv",
            mime="text/csv",
            key=_sk(entity_type, "dl_errors"),
        )
