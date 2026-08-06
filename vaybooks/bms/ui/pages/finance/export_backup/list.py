import json

import streamlit as st

from vaybooks.bms.infrastructure.backup.service import (
    BackupService,
    normalize_backup_mode,
)
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
            width="stretch",
        )


def render(services: dict):
    from vaybooks.bms.ui.keyboard.actions import consume_action
    from vaybooks.bms.ui.keyboard.context import set_current_page
    from vaybooks.bms.ui.keyboard.wired import mark_wired

    set_current_page("export_backup")
    mark_wired(
        "export.csv.customers",
        "export.csv.orders",
        "export.csv.products",
        "export.csv.vendors",
        "export.backup.json",
        "export.backup.zip",
        "export.backup.save_disk",
        "export.backup.restore",
    )
    for aid, label in (
        ("export.csv.customers", "Customers CSV"),
        ("export.csv.orders", "Orders CSV"),
        ("export.csv.products", "Products CSV"),
        ("export.csv.vendors", "Vendors CSV"),
    ):
        if consume_action(aid):
            st.info(f"Shortcut ready: use the **{label}** download button below.")

    st.title("Export / Backup")
    export_service = services["export"]
    settings = get_settings()
    backup_service = BackupService(get_database())
    backup_mode = normalize_backup_mode(getattr(settings, "backup_mode", "complete"))

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
        st.subheader("Database backup")
        st.caption(
            "Complete = all collections. Balances = parties + accounts (+ AR/AP summary). "
            f"Configured mode: **{backup_mode}**. Retention: "
            f"**{getattr(settings, 'backup_retention', 'keep_one')}**."
        )

        col_a, col_b = st.columns(2)
        with col_a:
            complete_zip = backup_service.create_backup_zip("complete")
            st.download_button(
                "Download Complete Backup (ZIP)",
                complete_zip,
                file_name="vaybooks_backup_complete.zip",
                mime="application/zip",
                key="export_complete_backup_zip",
                width="stretch",
            )
        with col_b:
            balances_zip = backup_service.create_backup_zip("balances")
            st.download_button(
                "Download Balances Backup (ZIP)",
                balances_zip,
                file_name="vaybooks_backup_balances.zip",
                mime="application/zip",
                key="export_balances_backup_zip",
                width="stretch",
            )

        st.subheader("Legacy JSON snapshot")
        st.caption("Partial boutique-era JSON export (download only).")
        backup_json = _cached_backup_json_v2(export_service)
        try:
            json.loads(backup_json)
            st.success("Backup JSON parses successfully")
        except json.JSONDecodeError:
            st.error("Backup JSON could not be parsed")
        st.download_button(
            "Download Legacy Backup (JSON)",
            backup_json,
            file_name="zahcci_backup.json",
            mime="application/json",
            key="export_full_backup_json",
            width="stretch",
        )

        if is_desktop():
            st.caption(
                f"Scheduled backup: **{settings.backup_schedule}** · "
                f"Drive: **{'on' if settings.backup_google_drive_enabled else 'off'}**"
            )
            if st.button("Save Backup to Disk (configured mode)", width="stretch"):
                path = backup_service.save_backup_to_disk(mode=backup_mode)
                if path:
                    st.success(f"Backup saved to {path}")
                    if settings.backup_google_drive_enabled:
                        try:
                            from vaybooks.bms.infrastructure.backup.google_drive import (
                                upload_backup_and_prune,
                            )

                            file_id = upload_backup_and_prune(
                                path,
                                retention=settings.backup_retention,
                            )
                            st.success(f"Uploaded to Google Drive ({file_id})")
                        except Exception as exc:
                            st.warning(f"Local save OK; Drive upload failed: {exc}")
                else:
                    st.error("Could not save backup")

            local_backups = backup_service.list_local_backups()
            if local_backups:
                st.write("Recent local backups:")
                for path in local_backups[:5]:
                    st.text(str(path.name))
        else:
            st.caption(
                "Web deployment: download ZIP above. Scheduled local/Drive backups "
                "run only on the desktop app."
            )

    if is_desktop():
        st.divider()
        with panel("restore"):
            st.subheader("Restore from backup")
            st.warning(
                "Complete restore replaces existing data in collections present in the ZIP. "
                "Balances-only ZIPs cannot fully restore."
            )
            uploaded = st.file_uploader("Upload backup ZIP", type=["zip"])
            dry_run = st.checkbox("Dry run (validate only)", value=True)
            if uploaded and st.button("Restore", type="primary"):
                try:
                    stats = backup_service.restore_from_zip(
                        uploaded.read(), dry_run=dry_run
                    )
                    if dry_run:
                        st.info(f"Dry run OK — would restore: {stats}")
                    else:
                        st.success(f"Restore complete: {stats}")
                        st.cache_data.clear()
                except Exception as exc:
                    st.error(str(exc))
