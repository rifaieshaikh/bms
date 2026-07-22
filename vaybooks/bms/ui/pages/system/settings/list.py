"""System settings page (desktop only)."""

import streamlit as st

from vaybooks.bms.version import __version__
from vaybooks.bms.infrastructure.config.settings import (
    AppSettings,
    get_settings,
    save_settings,
    validate_mongo_connection,
)


def _render_product_custom_fields(services: dict) -> None:
    from vaybooks.bms.domain.inventory.field_definitions import ProductFieldType

    inventory = services["inventory"]
    st.subheader("Product custom fields")
    definitions = inventory.list_field_definitions(active_only=False)
    categories = inventory.list_categories(active_only=False)
    cat_opts = {inventory.get_category_path(c.id) or c.name: c.id for c in categories}

    with st.expander("Add custom field", expanded=False):
        key = st.text_input("Key", key="cf_new_key")
        label = st.text_input("Label", key="cf_new_label")
        field_type = st.selectbox(
            "Type",
            [t.value for t in ProductFieldType],
            key="cf_new_type",
        )
        options_raw = st.text_input(
            "Options (comma-separated, for select)",
            key="cf_new_options",
        )
        required = st.checkbox("Required", key="cf_new_required")
        scope = st.multiselect(
            "Applies to categories (empty = all)",
            list(cat_opts.keys()),
            key="cf_new_scope",
        )
        if st.button("Add field", key="cf_add_btn"):
            try:
                inventory.create_field_definition(
                    key,
                    label,
                    ProductFieldType(field_type),
                    options=[o.strip() for o in options_raw.split(",") if o.strip()],
                    required=required,
                    applies_to_category_ids=[cat_opts[s] for s in scope],
                )
                st.success("Custom field added.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    if not definitions:
        st.caption("No custom fields defined yet.")
        return

    for definition in definitions:
        with st.container(border=True):
            st.markdown(f"**{definition.label}** (`{definition.key}`)")
            new_label = st.text_input(
                "Label",
                value=definition.label,
                key=f"cf_lbl_{definition.id}",
            )
            new_type = st.selectbox(
                "Type",
                [t.value for t in ProductFieldType],
                index=[t.value for t in ProductFieldType].index(definition.field_type.value),
                key=f"cf_type_{definition.id}",
            )
            new_options = st.text_input(
                "Options",
                value=", ".join(definition.options),
                key=f"cf_opts_{definition.id}",
            )
            new_required = st.checkbox(
                "Required",
                value=definition.required,
                key=f"cf_req_{definition.id}",
            )
            new_active = st.checkbox(
                "Active",
                value=definition.is_active,
                key=f"cf_act_{definition.id}",
            )
            cols = st.columns(2)
            if cols[0].button("Save", key=f"cf_save_{definition.id}"):
                try:
                    inventory.update_field_definition(
                        definition.id,
                        label=new_label,
                        field_type=ProductFieldType(new_type),
                        options=[o.strip() for o in new_options.split(",") if o.strip()],
                        required=new_required,
                        is_active=new_active,
                        applies_to_category_ids=definition.applies_to_category_ids,
                    )
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
            if cols[1].button("Delete", key=f"cf_del_{definition.id}"):
                try:
                    inventory.delete_field_definition(definition.id)
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))


def render(services: dict):
    st.title("System Settings")
    st.caption(f"VayBooks-BMS v{__version__}")

    settings = get_settings()

    _render_product_custom_fields(services)

    st.divider()

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
