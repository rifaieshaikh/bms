import streamlit as st


def render(services: dict):
    st.title("Export / Backup")
    export_service = services["export"]

    st.write(
        "Export data for backup and reporting. "
        "MongoDB Atlas remains the source of truth."
    )

    exports = [
        ("Customers", export_service.export_customers_csv),
        ("Customization Orders", export_service.export_orders_csv),
        ("Time Entries", export_service.export_time_entries_csv),
        ("Expenses", export_service.export_expenses_csv),
        ("Invoices", export_service.export_invoices_csv),
        ("Vouchers", export_service.export_vouchers_csv),
    ]

    for label, func in exports:
        csv_data = func()
        st.download_button(
            f"Download {label} CSV",
            csv_data,
            file_name=f"zahcci_{label.lower().replace(' ', '_')}.csv",
            mime="text/csv",
        )

    st.divider()
    backup_json = export_service.export_full_backup_json()
    st.download_button(
        "Download Full Backup (JSON)",
        backup_json,
        file_name="zahcci_backup.json",
        mime="application/json",
    )
