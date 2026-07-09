import json

import streamlit as st

from vaybooks.bms.infrastructure.backup.service import BackupService
from vaybooks.bms.infrastructure.config.runtime import is_desktop
from vaybooks.bms.infrastructure.config.settings import get_settings
from vaybooks.bms.infrastructure.db.connection import get_database
from vaybooks.bms.ui.styles import panel, render_card_grid


@st.cache_data(ttl=300, show_spinner=False)
def _cached_csv_export_v2(export_key: str, _export_service) -> str:
    exporters = {
        "customers": _export_service.export_customers_csv,
        "customization_orders": _export_service.export_orders_csv,
        "time_entries": _export_service.export_time_entries_csv,
        "expenses": _export_service.export_expenses_csv,
        "invoices": _export_service.export_invoices_csv,
        "vouchers": _export_service.export_vouchers_csv,
    }
    return exporters[export_key]()


@st.cache_data(ttl=300, show_spinner=False)
def _cached_backup_json_v2(_export_service) -> str:
    return _export_service.export_full_backup_json()


def _render_export_card(
    item: tuple[str, str],
    index: int,
    export_service,
) -> None:
    label, export_key = item
    with st.container(border=True):
        st.subheader(label)
        st.caption("CSV export")
        csv_data = _cached_csv_export_v2(export_key, export_service)
        st.download_button(
            f"Download {label}",
            csv_data,
            file_name=f"zahcci_{export_key}.csv",
            mime="text/csv",
            key=f"export_csv_{index}",
            use_container_width=True,
        )


def render(services: dict):
    st.title("Export / Backup")
    export_service = services["export"]
    settings = get_settings()

    st.write(
        "Export data for backup and reporting. "
        "MongoDB remains the source of truth."
    )

    exports = [
        ("Customers", "customers"),
        ("Customization Orders", "customization_orders"),
        ("Time Entries", "time_entries"),
        ("Expenses", "expenses"),
        ("Invoices", "invoices"),
        ("Vouchers", "vouchers"),
    ]

    render_card_grid(
        exports,
        lambda item, index: _render_export_card(item, index, export_service),
        suffix="exports",
        card_min_width=280,
    )

    st.divider()
    with panel("backup"):
        st.subheader("Full backup")
        st.caption("JSON snapshot of exportable collections.")
        backup_json = _cached_backup_json_v2(export_service)
        try:
            json.loads(backup_json)
            st.success("Backup JSON parses successfully")
        except json.JSONDecodeError:
            st.error("Backup JSON could not be parsed")
        st.download_button(
            "Download Full Backup (JSON)",
            backup_json,
            file_name="zahcci_backup.json",
            mime="application/json",
            key="export_full_backup_json",
            use_container_width=True,
        )

        if is_desktop():
            backup_service = BackupService(get_database())
            zip_bytes = backup_service.create_backup_zip()
            st.download_button(
                "Download Full Backup (ZIP — all collections)",
                zip_bytes,
                file_name="vaybooks_backup.zip",
                mime="application/zip",
                key="export_full_backup_zip",
                use_container_width=True,
            )

            if st.button("Save Backup to Disk", use_container_width=True):
                path = backup_service.save_backup_to_disk()
                if path:
                    st.success(f"Backup saved to {path}")
                else:
                    st.error("Could not save backup")

            st.caption(f"Scheduled backup: **{settings.backup_schedule}**")
            local_backups = backup_service.list_local_backups()
            if local_backups:
                st.write("Recent local backups:")
                for path in local_backups[:5]:
                    st.text(str(path.name))

    if is_desktop():
        st.divider()
        with panel("restore"):
            st.subheader("Restore from backup")
            st.warning("Restore replaces existing data in all backed-up collections.")
            uploaded = st.file_uploader("Upload backup ZIP", type=["zip"])
            dry_run = st.checkbox("Dry run (validate only)", value=True)
            if uploaded and st.button("Restore", type="primary"):
                backup_service = BackupService(get_database())
                try:
                    stats = backup_service.restore_from_zip(uploaded.read(), dry_run=dry_run)
                    if dry_run:
                        st.info(f"Dry run OK — would restore: {stats}")
                    else:
                        st.success(f"Restore complete: {stats}")
                        st.cache_data.clear()
                except Exception as exc:
                    st.error(str(exc))
