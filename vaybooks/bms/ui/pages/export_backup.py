import json

import streamlit as st

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

    st.write(
        "Export data for backup and reporting. "
        "MongoDB Atlas remains the source of truth."
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
        st.caption("JSON snapshot of all exportable collections.")
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
