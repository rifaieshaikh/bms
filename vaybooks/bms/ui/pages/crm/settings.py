"""CRM settings: catalogs, automation, WhatsApp template, notifications."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from vaybooks.bms.domain.crm.enums import (
    DEFAULT_ACTIVITY_OUTCOMES,
    DEFAULT_ACTIVITY_TYPES,
    DEFAULT_LEAD_SOURCES,
    DEFAULT_LOST_REASONS,
    DEFAULT_OUTCOME_REQUIRED_TYPES,
    EnquiryStatus,
    LeadStatus,
)
from vaybooks.bms.domain.crm.services import render_payment_reminder_message
from vaybooks.bms.ui.auth.session import current_user_id
from vaybooks.bms.ui.components.crm.common import CRM_UNAVAILABLE_TEXT, page_adapter
from vaybooks.bms.ui.crm_adapters import CrmUnavailable, field, text

PAGE_KEY = "crm_settings"

SECTIONS = (
    "Lists & statuses",
    "Activities",
    "Automation",
    "WhatsApp",
    "My notifications",
)

LIST_CATALOGS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("lead_sources", "Lead sources", DEFAULT_LEAD_SOURCES),
    ("lead_statuses", "Lead statuses", tuple(s.value for s in LeadStatus)),
    ("enquiry_statuses", "Enquiry statuses", tuple(s.value for s in EnquiryStatus)),
    ("lost_reasons", "Lost reasons", DEFAULT_LOST_REASONS),
)

ACTIVITY_CATALOGS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("activity_types", "Activity types", DEFAULT_ACTIVITY_TYPES),
    ("activity_outcomes", "Activity outcomes", DEFAULT_ACTIVITY_OUTCOMES),
)

ORDER_TRIGGERS = ("Draft", "Confirmed", "Delivered", "Invoiced")
PAYMENT_TRIGGERS = {
    "receipt_create": "When a receipt is recorded",
    "invoice_paid": "When an invoice is fully paid",
}

NOTIFICATION_FIELDS: tuple[tuple[str, str], ...] = (
    ("activity_due_today", "Activities due today"),
    ("upcoming_visits", "Upcoming visits"),
    ("overdue_follow_ups", "Overdue follow-ups"),
    ("lead_assigned", "A lead is assigned to me"),
    ("enquiry_reassigned", "An enquiry is reassigned"),
    ("payment_promises", "Payment promises"),
    ("high_priority_idle", "High-priority leads with no activity"),
    ("payment_reminder_due", "Payment reminders due"),
)

TEMPLATE_PLACEHOLDERS: tuple[tuple[str, str], ...] = (
    ("{customer_name}", "Customer's name"),
    ("{business_name}", "Business display name below"),
    ("{outstanding_amount}", "Total due across all open invoices"),
    ("{invoice_count}", "Number of open invoices"),
    ("{invoice_refs}", "Open invoices with amounts, e.g. INV-12 (Rs.1,200.00)"),
    ("{oldest_due_date}", "Date of the oldest open invoice"),
)

SAMPLE_TEMPLATE_VALUES = {
    "customer_name": "Asha Traders",
    "business_name": "VayBooks Store",
    "outstanding_amount": 3450.0,
    "invoice_refs": "INV-12 (Rs.1,200.00), INV-15 (Rs.2,250.00)",
    "invoice_count": 2,
    "oldest_due_date": "02-Jul-2026",
}


def _catalog_rows(
    settings: Any,
    attribute: str,
    fallback: tuple[str, ...],
    *,
    outcome_flag: bool = False,
) -> list[dict]:
    items = field(settings, attribute) or []
    rows: list[dict] = []
    for item in items:
        if not (isinstance(item, dict) and item.get("label")):
            continue
        row = {
            "Label": text(item.get("label")),
            "Active": bool(item.get("active", True)),
        }
        if outcome_flag:
            row["Outcome required"] = bool(item.get("outcome_required", False))
        rows.append(row)
    if rows:
        return rows
    required = {t.lower() for t in DEFAULT_OUTCOME_REQUIRED_TYPES}
    fallback_rows = []
    for label in fallback:
        row = {"Label": label, "Active": True}
        if outcome_flag:
            row["Outcome required"] = label.lower() in required
        fallback_rows.append(row)
    return fallback_rows


def _rows_to_catalog(frame: pd.DataFrame, original: Any) -> list[dict]:
    """Merge edited labels/flags back onto the stored catalog dicts."""
    stored = {
        text(item.get("label")): dict(item)
        for item in (original or [])
        if isinstance(item, dict)
    }
    has_outcome = "Outcome required" in frame.columns
    catalog: list[dict] = []
    for _, row in frame.iterrows():
        label = str(row.get("Label") or "").strip()
        if not label:
            continue
        item = stored.get(label, {"label": label})
        item["label"] = label
        item["active"] = bool(row.get("Active", True))
        if has_outcome:
            item["outcome_required"] = bool(row.get("Outcome required", False))
        catalog.append(item)
    return catalog


def _save(adapter, payload: dict, success: str) -> None:
    try:
        adapter.update_settings(payload)
    except CrmUnavailable as exc:
        st.error(f"This action is not available yet. {exc}")
        return
    except Exception as exc:  # noqa: BLE001 - surface backend errors to the user
        st.error(f"Could not save settings: {exc}")
        return
    st.success(success)
    st.rerun()


def _catalog_editor(
    adapter,
    settings: Any,
    catalogs: tuple[tuple[str, str, tuple[str, ...]], ...],
    *,
    picker_key: str,
) -> None:
    labels = [label for _, label, _ in catalogs]
    choice = st.selectbox("List", labels, key=picker_key)
    attribute, label, fallback = next(c for c in catalogs if c[1] == choice)
    outcome_flag = attribute == "activity_types"

    column_config: dict[str, Any] = {
        "Label": st.column_config.TextColumn("Label", required=True),
        "Active": st.column_config.CheckboxColumn(
            "Active", help="Inactive entries are hidden from dropdowns."
        ),
    }
    if outcome_flag:
        column_config["Outcome required"] = st.column_config.CheckboxColumn(
            "Outcome required",
            help="An outcome must be recorded before this activity can be completed.",
        )

    frame = st.data_editor(
        pd.DataFrame(
            _catalog_rows(settings, attribute, fallback, outcome_flag=outcome_flag)
        ),
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        key=f"crm_settings_catalog_{attribute}",
        column_config=column_config,
    )
    st.caption(
        "Deactivate an entry to hide it from dropdowns without losing history. "
        "Add a row to introduce a new option."
    )
    if st.button(
        f"Save {label.lower()}",
        type="primary",
        key=f"crm_settings_save_{attribute}",
    ):
        _save(
            adapter,
            {attribute: _rows_to_catalog(frame, field(settings, attribute))},
            f"{label} saved",
        )


def _lists_section(adapter, settings: Any) -> None:
    st.subheader("Lists & statuses")
    _catalog_editor(
        adapter, settings, LIST_CATALOGS, picker_key="crm_settings_list_picker"
    )


def _activities_section(adapter, settings: Any) -> None:
    st.subheader("Activities")
    _catalog_editor(
        adapter, settings, ACTIVITY_CATALOGS, picker_key="crm_settings_activity_picker"
    )


def _automation_section(adapter, settings: Any) -> None:
    st.subheader("Automation")
    with st.form("crm_settings_defaults"):
        st.markdown("**Follow-up defaults**")
        cols = st.columns(2)
        inactivity = cols[0].number_input(
            "Inactivity window (days)",
            min_value=1,
            max_value=365,
            value=int(field(settings, "default_inactivity_days", default=30) or 30),
            help="A customer with no manual activity for this long counts as dormant.",
        )
        follow_up = cols[1].number_input(
            "Default follow-up gap (days)",
            min_value=1,
            max_value=90,
            value=int(field(settings, "default_follow_up_days", default=3) or 3),
            help="Pre-fills the next follow-up date when an activity is completed.",
        )

        st.markdown("**Automatic activity triggers**")
        current_order = text(field(settings, "order_trigger_status"), default="Confirmed")
        order_options = list(ORDER_TRIGGERS)
        if current_order not in order_options:
            order_options.insert(0, current_order)
        order_trigger = st.selectbox(
            "Log an 'Order Placed' activity when a sales order is",
            order_options,
            index=order_options.index(current_order),
        )
        payment_keys = list(PAYMENT_TRIGGERS)
        current_payment = text(
            field(settings, "payment_trigger"), default="receipt_create"
        )
        payment_trigger = st.selectbox(
            "Log a 'Payment Received' activity",
            payment_keys,
            index=(
                payment_keys.index(current_payment)
                if current_payment in payment_keys
                else 0
            ),
            format_func=lambda key: PAYMENT_TRIGGERS.get(key, key),
        )

        if st.form_submit_button("Save automation settings", type="primary"):
            _save(
                adapter,
                {
                    "default_inactivity_days": int(inactivity),
                    "default_follow_up_days": int(follow_up),
                    "order_trigger_status": order_trigger,
                    "payment_trigger": payment_trigger,
                },
                "Automation settings saved",
            )


def _whatsapp_section(adapter, settings: Any) -> None:
    st.subheader("WhatsApp payment reminders")
    st.caption(
        "Reminders cover the customer's total due across all open invoices. "
        "Messages open in WhatsApp for review — nothing is sent automatically."
    )
    with st.form("crm_settings_whatsapp"):
        business_name = st.text_input(
            "Business display name",
            value=text(field(settings, "business_display_name")),
            help="Used in the {business_name} placeholder.",
        )
        template = st.text_area(
            "Payment reminder template",
            value=text(field(settings, "payment_reminder_template")),
            height=160,
        )
        offsets = st.text_input(
            "Reminder schedule (days after due date)",
            value=", ".join(
                str(day)
                for day in (field(settings, "payment_reminder_due_offsets_days") or [])
            ),
            help="Comma-separated day offsets, e.g. 0, 3, 7.",
        )
        if st.form_submit_button("Save WhatsApp settings", type="primary"):
            try:
                parsed = [
                    int(part.strip())
                    for part in offsets.split(",")
                    if part.strip()
                ]
            except ValueError:
                st.error("Reminder schedule must be a comma-separated list of days.")
                return
            _save(
                adapter,
                {
                    "business_display_name": business_name,
                    "payment_reminder_template": template,
                    "payment_reminder_due_offsets_days": parsed,
                },
                "WhatsApp settings saved",
            )

    with st.expander("Placeholders and sample", expanded=False):
        st.markdown(
            "\n".join(
                f"- `{placeholder}` — {description}"
                for placeholder, description in TEMPLATE_PLACEHOLDERS
            )
        )
        st.caption("Sample message with two open invoices:")
        st.info(
            render_payment_reminder_message(
                text(field(settings, "payment_reminder_template")),
                **SAMPLE_TEMPLATE_VALUES,
            )
        )


def _notifications_section(adapter) -> None:
    st.subheader("My notifications")
    user_id = current_user_id()
    if not user_id:
        st.info("Sign in to manage your notification preferences.")
        return
    preferences = adapter.get_notification_preferences(user_id)
    if preferences is None:
        st.info("Notification preferences are not available yet.")
        return

    st.caption("These preferences apply to your account only.")
    with st.form("crm_settings_notifications"):
        values = {
            key: st.checkbox(
                label,
                value=bool(field(preferences, key, default=True)),
                key=f"crm_notify_{key}",
            )
            for key, label in NOTIFICATION_FIELDS
        }
        if st.form_submit_button("Save preferences", type="primary"):
            try:
                adapter.update_notification_preferences(user_id, values)
            except Exception as exc:  # noqa: BLE001 - surface backend errors
                st.error(f"Could not save preferences: {exc}")
                return
            st.success("Notification preferences saved")
            st.rerun()


def _section_picker() -> str:
    control = getattr(st, "segmented_control", None)
    if callable(control):
        choice = control(
            "Section",
            SECTIONS,
            default=SECTIONS[0],
            key="crm_settings_section",
            label_visibility="collapsed",
        )
        return choice or SECTIONS[0]
    return st.radio(
        "Section",
        SECTIONS,
        horizontal=True,
        key="crm_settings_section",
        label_visibility="collapsed",
    )


def render(services: dict) -> None:
    from vaybooks.bms.ui.keyboard.context import set_current_page

    set_current_page(PAGE_KEY)
    st.title("CRM Settings")
    st.caption("CRM roles are assigned under Access → Users.")

    adapter = page_adapter(services)
    if not adapter.available:
        st.info(CRM_UNAVAILABLE_TEXT)
        return

    settings = adapter.get_settings()
    if settings is None:
        st.info("CRM settings are not available yet.")
        return

    updated_by = text(field(settings, "updated_by_name"))
    if updated_by:
        st.caption(f"Last updated by {updated_by}")

    section = _section_picker()
    if section == "Lists & statuses":
        _lists_section(adapter, settings)
    elif section == "Activities":
        _activities_section(adapter, settings)
    elif section == "Automation":
        _automation_section(adapter, settings)
    elif section == "WhatsApp":
        _whatsapp_section(adapter, settings)
    else:
        _notifications_section(adapter)
