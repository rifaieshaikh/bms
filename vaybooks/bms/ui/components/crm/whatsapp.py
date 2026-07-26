"""WhatsApp click-to-chat payment reminder dialog.

WhatsApp is opened through a click-to-chat link, so the app can only record
that a reminder was *prepared* — never that it was delivered.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import streamlit as st

from vaybooks.bms.domain.crm.services import (
    build_whatsapp_click_to_chat_url,
    render_payment_reminder_message,
)
from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.ui.crm_adapters import CrmAdapter, field, text
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler

REMINDER_FLAG = "crm_whatsapp_reminder_dialog"

DEFAULT_TEMPLATE = (
    "Hello {customer_name}, this is a payment reminder from {business_name}. "
    "Your total outstanding across all pending invoices is Rs.{outstanding_amount}. "
    "Please contact us to arrange payment. Thank you."
)


@dataclass
class ReminderDraft:
    customer_id: str
    customer_name: str
    phone: str
    outstanding_amount: float
    message: str
    whatsapp_url: str
    invoice_count: int = 0
    invoice_refs: str = ""
    oldest_due_date: str = ""


def build_reminder_draft(
    *,
    customer_id: str,
    customer_name: str,
    phone: str,
    outstanding_amount: float,
    template: str = "",
    business_name: str = "",
    message_override: str = "",
    invoice_refs: str = "",
    invoice_count: int = 0,
    oldest_due_date: str = "",
) -> ReminderDraft:
    """Render the message and click-to-chat URL without touching services."""
    message = (message_override or "").strip() or render_payment_reminder_message(
        template or DEFAULT_TEMPLATE,
        customer_name=customer_name,
        business_name=business_name,
        outstanding_amount=outstanding_amount,
        invoice_refs=invoice_refs,
        invoice_count=invoice_count,
        oldest_due_date=oldest_due_date,
    )
    return ReminderDraft(
        customer_id=customer_id,
        customer_name=customer_name,
        phone=phone,
        outstanding_amount=float(outstanding_amount or 0),
        message=message,
        whatsapp_url=build_whatsapp_click_to_chat_url(phone, message),
        invoice_count=int(invoice_count or 0),
        invoice_refs=invoice_refs,
        oldest_due_date=oldest_due_date,
    )


def arm_reminder_dialog(customer_id: str) -> None:
    st.session_state[REMINDER_FLAG] = customer_id


def _business_name(services: dict, adapter: CrmAdapter) -> str:
    settings = adapter.get_settings()
    configured = text(field(settings, "business_display_name"))
    if configured:
        return configured
    business = services.get("business")
    for name in ("get_business_profile", "get_profile", "get_settings"):
        loader = getattr(business, name, None) if business else None
        if callable(loader):
            try:
                profile = loader()
            except Exception:
                continue
            label = text(field(profile, "business_name", "name", "display_name"))
            if label:
                return label
    return ""


def _outstanding(services: dict, customer_id: str) -> float:
    accounting = services.get("accounting")
    loader = getattr(accounting, "customer_balances_by_customer", None) if accounting else None
    if callable(loader):
        try:
            return max(float((loader() or {}).get(customer_id, 0) or 0), 0.0)
        except Exception:
            return 0.0
    return 0.0


def _draft_from_services(
    services: dict,
    adapter: CrmAdapter,
    customer: Any,
    *,
    phone: str,
    amount: float,
    message_override: str,
) -> ReminderDraft:
    """Prefer the backend preview; fall back to local rendering."""
    customer_id = text(field(customer, "id"))
    if adapter.supports("reminders", "preview"):
        try:
            preview = adapter.reminder_preview(
                customer_id,
                phone=phone,
                outstanding_amount=amount,
                message_override=message_override,
            )
        except ValidationError:
            raise
        except Exception:
            preview = None
        if preview is not None:
            return ReminderDraft(
                customer_id=text(field(preview, "customer_id"), default=customer_id),
                customer_name=text(field(preview, "customer_name")),
                phone=text(field(preview, "phone"), default=phone),
                outstanding_amount=float(
                    field(preview, "outstanding_amount", default=0.0) or 0.0
                ),
                message=text(field(preview, "message")),
                whatsapp_url=text(field(preview, "whatsapp_url")),
                invoice_count=int(field(preview, "invoice_count", default=0) or 0),
                invoice_refs=text(field(preview, "invoice_refs")),
                oldest_due_date=text(field(preview, "oldest_due_date")),
            )
    settings = adapter.get_settings()
    return build_reminder_draft(
        customer_id=customer_id,
        customer_name=text(field(customer, "customer_name")),
        phone=phone,
        outstanding_amount=amount,
        template=text(field(settings, "payment_reminder_template")),
        business_name=_business_name(services, adapter),
        message_override=message_override,
    )


@st.dialog("WhatsApp Payment Reminder", on_dismiss=make_dismiss_handler(REMINDER_FLAG))
def payment_reminder_dialog(services: dict, adapter: CrmAdapter, customer_id: str) -> None:
    customers = services.get("customers")
    customer = customers.get_customer_detail(customer_id) if customers else None
    if not customer:
        st.error("Customer not found.")
        return

    default_phone = text(field(customer, "phone_number"))
    default_amount = _outstanding(services, customer_id)

    cols = st.columns(2)
    phone = cols[0].text_input(
        "Mobile number", value=default_phone, key="crm_wa_phone"
    )
    amount = cols[1].number_input(
        "Outstanding amount (₹)",
        min_value=0.0,
        step=500.0,
        value=float(default_amount),
        key="crm_wa_amount",
    )
    override = st.text_area(
        "Message",
        key="crm_wa_message",
        height=120,
        placeholder="Leave blank to use the configured template.",
    )

    try:
        draft = _draft_from_services(
            services,
            adapter,
            customer,
            phone=phone,
            amount=amount,
            message_override=override,
        )
    except ValidationError as exc:
        st.error(str(exc))
        st.caption("Add a valid mobile number to the customer to send reminders.")
        if st.button("Close", key="crm_wa_close_error", width="stretch"):
            st.session_state.pop(REMINDER_FLAG, None)
            st.rerun()
        return

    if draft.invoice_count:
        summary = f"{draft.invoice_count} open invoice(s)"
        if draft.oldest_due_date:
            summary += f" — oldest dated {draft.oldest_due_date}"
        if draft.invoice_refs:
            summary += f": {draft.invoice_refs}"
        st.caption(summary)

    st.caption("Preview")
    st.info(draft.message)
    st.caption(
        "Opening WhatsApp only prepares the message — delivery is not confirmed."
    )

    prepared_url = st.session_state.get("crm_wa_prepared_url")
    if prepared_url and prepared_url != draft.whatsapp_url:
        st.session_state.pop("crm_wa_prepared_url", None)
        prepared_url = None
    if prepared_url:
        st.link_button(
            "Open prepared message in WhatsApp",
            prepared_url,
            type="primary",
            width="stretch",
            icon=":material/chat:",
        )
    elif st.button(
        "Confirm and prepare WhatsApp link",
        key="crm_wa_prepare",
        type="primary",
        width="stretch",
    ):
        try:
            adapter.record_reminder_opened(draft)
            st.session_state["crm_wa_prepared_url"] = draft.whatsapp_url
            st.rerun()
        except Exception as exc:
            st.error(f"Could not prepare the reminder: {exc}")
    if st.button("Close", key="crm_wa_close", width="stretch"):
        st.session_state.pop(REMINDER_FLAG, None)
        st.session_state.pop("crm_wa_message", None)
        st.session_state.pop("crm_wa_prepared_url", None)
        st.rerun()

    if adapter.supports("reminders", "schedule_reminder_tasks"):
        with st.expander("Schedule follow-up reminder tasks", expanded=False):
            recipient_id = adapter.actor_id
            st.caption(
                "Creates scheduled Payment Reminder activities using the offsets "
                "configured in CRM settings."
            )
            if st.button(
                "Schedule reminders",
                key="crm_wa_schedule",
                disabled=not recipient_id,
                width="stretch",
            ):
                try:
                    created = adapter.schedule_reminder_tasks(
                        {
                            "customer_id": draft.customer_id,
                            "customer_name": draft.customer_name,
                            "outstanding_amount": draft.outstanding_amount,
                            "recipient_id": recipient_id,
                            "phone": draft.phone,
                        }
                    )
                    st.success(f"{len(created)} reminder task(s) scheduled.")
                except Exception as exc:
                    st.error(f"Could not schedule reminders: {exc}")


def open_reminder_dialog_if_armed(services: dict, adapter: CrmAdapter) -> None:
    customer_id = st.session_state.get(REMINDER_FLAG)
    if customer_id:
        payment_reminder_dialog(services, adapter, customer_id)
