"""System settings page (desktop only)."""

import streamlit as st

from vaybooks.bms.version import __version__
from vaybooks.bms.infrastructure.config.settings import (
    AppSettings,
    get_settings,
    save_settings,
    validate_mongo_connection,
)


def render(services: dict):
    st.title("System Settings")
    st.caption(f"VayBooks-BMS v{__version__}")

    settings = get_settings()

    with st.form("system_settings_form"):
        mongo_uri = st.text_input("MongoDB URI", value=settings.mongo_uri, type="password")
        db_name = st.text_input("Database Name", value=settings.db_name)
        app_port = st.number_input("App Port", min_value=1024, max_value=65535, value=settings.app_port)
        mongo_mode = st.selectbox(
            "MongoDB Mode",
            options=["local", "remote"],
            index=0 if settings.mongo_mode == "local" else 1,
        )
        update_url = st.text_input("Update Check URL", value=settings.update_check_url)
        backup_schedule = st.selectbox(
            "Backup Schedule",
            options=["off", "daily", "weekly"],
            index=["off", "daily", "weekly"].index(settings.backup_schedule),
        )
        retention = st.number_input(
            "Backup Retention (days)",
            min_value=1,
            max_value=365,
            value=settings.backup_retention_days,
        )
        auto_update = st.checkbox("Enable automatic updates (future)", value=settings.auto_update_enabled)

        test_col, save_col = st.columns(2)
        with test_col:
            test_clicked = st.form_submit_button("Test Connection", use_container_width=True)
        with save_col:
            save_clicked = st.form_submit_button("Save Settings", type="primary", use_container_width=True)

    if test_clicked:
        ok, message = validate_mongo_connection(mongo_uri, db_name)
        if ok:
            st.success(message)
        else:
            st.error(message)

    if save_clicked:
        ok, message = validate_mongo_connection(mongo_uri, db_name)
        if not ok:
            st.error(message)
        else:
            new_settings = AppSettings(
                app_version=__version__,
                app_port=int(app_port),
                mongo_uri=mongo_uri,
                db_name=db_name,
                mongo_mode=mongo_mode,
                update_check_url=update_url,
                backup_schedule=backup_schedule,
                backup_retention_days=int(retention),
                auto_update_enabled=auto_update,
            )
            save_settings(new_settings)
            st.success("Settings saved. Restart the service for port changes to take effect.")
            st.info("MongoDB connection changes take effect on next page reload.")
