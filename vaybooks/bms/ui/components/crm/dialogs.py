"""CRM action dialogs shared by the list, detail, and customer pages.

Every dialog is armed through a session flag so it survives the rerun that
Streamlit performs when the triggering button is clicked.
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any, Callable, Optional

import streamlit as st

from vaybooks.bms.domain.crm.enums import EnquiryStatus, LeadStatus
from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.crm.common import (
    activity_outcomes,
    index_of,
    lost_reasons,
)
from vaybooks.bms.ui.components.crm.forms import (
    UNASSIGNED,
    render_activity_form,
    render_enquiry_form,
    render_lead_form,
)
from vaybooks.bms.ui.crm_adapters import (
    CrmAdapter,
    CrmUnavailable,
    as_datetime,
    field,
    record_id,
    text,
)
from vaybooks.bms.ui.dialog_utils import (
    clear_all_dialog_flags,
    make_dismiss_handler,
    register_armed_dialog,
)

LEAD_ADD = "crm_lead_add_dialog"
LEAD_EDIT = "crm_lead_edit_dialog"
LEAD_ASSIGN = "crm_lead_assign_dialog"
LEAD_STATUS = "crm_lead_status_dialog"
LEAD_LOST = "crm_lead_lost_dialog"
LEAD_REOPEN = "crm_lead_reopen_dialog"
LEAD_CONVERT = "crm_lead_convert_dialog"
LEAD_BULK = "crm_lead_bulk_dialog"
ENQUIRY_ADD = "crm_enquiry_add_dialog"
ENQUIRY_EDIT = "crm_enquiry_edit_dialog"
ENQUIRY_ASSIGN = "crm_enquiry_assign_dialog"
ENQUIRY_STATUS = "crm_enquiry_status_dialog"
ACTIVITY_ADD = "crm_activity_add_dialog"
ACTIVITY_COMPLETE = "crm_activity_complete_dialog"
ACTIVITY_RESCHEDULE = "crm_activity_reschedule_dialog"
ACTIVITY_CANCEL = "crm_activity_cancel_dialog"

LEAD_STATUSES = [s.value for s in LeadStatus]
ENQUIRY_STATUSES = [s.value for s in EnquiryStatus]
REOPEN_STATUSES = [
    LeadStatus.FOLLOW_UP_REQUIRED.value,
    LeadStatus.NEW.value,
    LeadStatus.CONTACTED.value,
    LeadStatus.QUALIFIED.value,
    LeadStatus.INTERESTED.value,
    LeadStatus.ON_HOLD.value,
]


def arm(flag: str, value: Any = True) -> None:
    """Open one dialog, closing any other that is currently armed."""
    clear_all_dialog_flags()
    st.session_state[flag] = value


def _close(flag: str) -> None:
    st.session_state.pop(flag, None)


def _apply(action: Callable[[], Any], *, flag: str, success: str) -> None:
    """Run a CRM write, surface failures, and close the dialog on success."""
    try:
        action()
    except CrmUnavailable as exc:
        st.error(f"This action is not available yet. {exc}")
        return
    except ValidationError as exc:
        st.error(str(exc))
        return
    except Exception as exc:  # noqa: BLE001 - surface backend errors to the user
        st.error(f"Could not complete the action: {exc}")
        return
    _close(flag)
    st.success(success)
    st.rerun()


def _cancel_button(flag: str, key: str, column=None) -> None:
    target = column if column is not None else st
    if target.button("Cancel", key=key, width="stretch"):
        _close(flag)
        st.rerun()


def _owner_choice(
    adapter: CrmAdapter, key: str, current_id: str = ""
) -> tuple[str, str]:
    owners = adapter.owners()
    if not owners:
        st.warning("No users are available to assign.")
        return "", ""
    ids = [""] + [oid for oid, _ in owners]
    labels = {"": UNASSIGNED, **dict(owners)}
    choice = st.selectbox(
        "Assign to",
        ids,
        index=ids.index(current_id) if current_id in ids else 0,
        format_func=lambda v: labels.get(v, v),
        key=key,
    )
    return choice, labels.get(choice, "") if choice else ""


def _customer_options(services: dict) -> list:
    customers = services.get("customers")
    try:
        return list(customers.list_all_customers()) if customers else []
    except Exception:
        return []


# --- leads -------------------------------------------------------------------
@st.dialog("Add Lead", width="large", on_dismiss=make_dismiss_handler(LEAD_ADD))
def lead_add_dialog(adapter: CrmAdapter) -> None:
    payload = render_lead_form("crm_lead_add", adapter)
    duplicate = None
    if (
        payload.get("name")
        or payload.get("phone")
        or payload.get("email")
        or payload.get("gstin")
    ):
        try:
            duplicate = adapter.detect_lead_duplicates(
                phone=payload.get("phone", ""),
                email=payload.get("email", ""),
                gstin=payload.get("gstin", ""),
                name=payload.get("name", ""),
            )
        except Exception:
            duplicate = None
    existing_lead = field(duplicate, "lead")
    existing_customer_id = text(field(duplicate, "customer_id"))
    if existing_lead is not None:
        st.warning(
            f"A lead with the same contact details already exists: "
            f"**{text(field(existing_lead, 'name'))}**"
        )
        if st.button("Open existing lead", key="crm_lead_add_open_dup"):
            _close(LEAD_ADD)
            navigation.go_to_detail("crm_lead_detail", record_id(existing_lead))
            return
    elif existing_customer_id:
        st.info(
            f"These details match customer "
            f"**{text(field(duplicate, 'customer_name'))}**. "
            "The lead can still be created and linked after conversion."
        )

    cols = st.columns(2)
    if cols[0].button("Create Lead", type="primary", width="stretch"):
        _apply(
            lambda: adapter.create_lead(payload),
            flag=LEAD_ADD,
            success=f"Created lead: {payload.get('name', '')}",
        )
    _cancel_button(LEAD_ADD, "crm_lead_add_cancel", cols[1])


@st.dialog("Edit Lead", width="large", on_dismiss=make_dismiss_handler(LEAD_EDIT))
def lead_edit_dialog(adapter: CrmAdapter, lead_id: str) -> None:
    lead = adapter.get_lead(lead_id)
    if lead is None:
        st.error("Lead not found.")
        return
    payload = render_lead_form("crm_lead_edit", adapter, lead, with_status=True)

    def _save() -> None:
        adapter.update_lead(lead_id, payload)
        # Owner and status are audited transitions, not plain field writes.
        if payload.get("assigned_user_id") != text(field(lead, "assigned_user_id")):
            adapter.assign_lead(
                lead_id,
                payload.get("assigned_user_id", ""),
                payload.get("assigned_user_name", ""),
            )
        if payload.get("status") != text(field(lead, "status")):
            adapter.set_lead_status(lead_id, payload.get("status", ""))

    cols = st.columns(2)
    if cols[0].button("Save Changes", type="primary", width="stretch"):
        _apply(_save, flag=LEAD_EDIT, success="Lead updated")
    _cancel_button(LEAD_EDIT, "crm_lead_edit_cancel", cols[1])


@st.dialog("Assign Lead", on_dismiss=make_dismiss_handler(LEAD_ASSIGN))
def lead_assign_dialog(adapter: CrmAdapter, lead_id: str) -> None:
    lead = adapter.get_lead(lead_id)
    if lead is None:
        st.error("Lead not found.")
        return
    st.caption(text(field(lead, "name")))
    owner_id, owner_name = _owner_choice(
        adapter, "crm_lead_assign_owner", text(field(lead, "assigned_user_id"))
    )
    cols = st.columns(2)
    if cols[0].button("Assign", type="primary", width="stretch"):
        _apply(
            lambda: adapter.assign_lead(lead_id, owner_id, owner_name),
            flag=LEAD_ASSIGN,
            success="Lead assigned",
        )
    _cancel_button(LEAD_ASSIGN, "crm_lead_assign_cancel", cols[1])


@st.dialog("Change Lead Status", on_dismiss=make_dismiss_handler(LEAD_STATUS))
def lead_status_dialog(adapter: CrmAdapter, lead_id: str) -> None:
    lead = adapter.get_lead(lead_id)
    if lead is None:
        st.error("Lead not found.")
        return
    st.caption(text(field(lead, "name")))
    status = st.selectbox(
        "Status",
        LEAD_STATUSES,
        index=index_of(LEAD_STATUSES, field(lead, "status")),
        key="crm_lead_status_value",
    )
    reason = st.text_input("Reason (optional)", key="crm_lead_status_reason")
    if status == LeadStatus.LOST.value:
        st.caption("Use **Mark Lost** to record a lost reason on the lead.")
    if status == LeadStatus.CONVERTED.value:
        st.caption("Use **Convert** so a customer record is created and linked.")
    cols = st.columns(2)
    disabled = status in (LeadStatus.LOST.value, LeadStatus.CONVERTED.value)
    if cols[0].button(
        "Update Status", type="primary", width="stretch", disabled=disabled
    ):
        _apply(
            lambda: adapter.set_lead_status(lead_id, status, reason),
            flag=LEAD_STATUS,
            success=f"Status set to {status}",
        )
    _cancel_button(LEAD_STATUS, "crm_lead_status_cancel", cols[1])


@st.dialog("Mark Lead Lost", on_dismiss=make_dismiss_handler(LEAD_LOST))
def lead_lost_dialog(adapter: CrmAdapter, lead_id: str) -> None:
    lead = adapter.get_lead(lead_id)
    if lead is None:
        st.error("Lead not found.")
        return
    st.warning(f"Mark **{text(field(lead, 'name'))}** as lost?")
    reasons = lost_reasons(adapter)
    reason = st.selectbox("Lost reason", reasons, key="crm_lead_lost_reason")
    note = st.text_input("Additional detail (optional)", key="crm_lead_lost_note")
    full_reason = f"{reason} — {note}".strip(" —") if note else reason
    cols = st.columns(2)
    if cols[0].button("Mark Lost", type="primary", width="stretch"):
        _apply(
            lambda: adapter.mark_lead_lost(lead_id, full_reason),
            flag=LEAD_LOST,
            success="Lead marked lost",
        )
    _cancel_button(LEAD_LOST, "crm_lead_lost_cancel", cols[1])


@st.dialog("Reopen Lead", on_dismiss=make_dismiss_handler(LEAD_REOPEN))
def lead_reopen_dialog(adapter: CrmAdapter, lead_id: str) -> None:
    lead = adapter.get_lead(lead_id)
    if lead is None:
        st.error("Lead not found.")
        return
    st.caption(text(field(lead, "name")))
    status = st.selectbox(
        "Reopen with status", REOPEN_STATUSES, key="crm_lead_reopen_status"
    )
    cols = st.columns(2)
    if cols[0].button("Reopen", type="primary", width="stretch"):
        _apply(
            lambda: adapter.reopen_lead(lead_id, status),
            flag=LEAD_REOPEN,
            success="Lead reopened",
        )
    _cancel_button(LEAD_REOPEN, "crm_lead_reopen_cancel", cols[1])


@st.dialog("Convert Lead to Customer", on_dismiss=make_dismiss_handler(LEAD_CONVERT))
def lead_convert_dialog(adapter: CrmAdapter, lead_id: str) -> None:
    lead = adapter.get_lead(lead_id)
    if lead is None:
        st.error("Lead not found.")
        return
    name = text(field(lead, "name"))
    linked_customer = text(field(lead, "customer_id"))
    if linked_customer:
        st.info(f"**{name}** is already linked to a customer.")
        if st.button("Open customer", key="crm_lead_convert_open", type="primary"):
            _close(LEAD_CONVERT)
            navigation.go_to_detail("customer_detail", linked_customer)
            return
        _cancel_button(LEAD_CONVERT, "crm_lead_convert_close")
        return

    st.write(f"Convert **{name}** into a customer record.")
    if not text(field(lead, "phone")):
        st.warning("A phone number is required before this lead can be converted.")
    match = None
    try:
        match = adapter.detect_lead_duplicates(
            phone=text(field(lead, "phone")),
            email=text(field(lead, "email")),
            gstin=text(field(lead, "gstin")),
            name=text(field(lead, "name")),
            exclude_lead_id=lead_id,
        )
    except Exception:
        match = None
    match_customer = text(field(match, "customer_id"))
    force_new = False
    if match_customer:
        st.info(
            f"An existing customer matches these details: "
            f"**{text(field(match, 'customer_name'))}**."
        )
        force_new = st.checkbox(
            "Create a separate customer instead of linking",
            key="crm_lead_convert_force",
        )

    cols = st.columns(2)
    if cols[0].button("Convert", type="primary", width="stretch"):
        _apply(
            lambda: adapter.convert_lead(lead_id, force_new=force_new),
            flag=LEAD_CONVERT,
            success=f"{name} converted to a customer",
        )
    _cancel_button(LEAD_CONVERT, "crm_lead_convert_cancel", cols[1])


@st.dialog("Bulk Lead Actions", on_dismiss=make_dismiss_handler(LEAD_BULK))
def lead_bulk_dialog(adapter: CrmAdapter, lead_ids: list[str]) -> None:
    st.write(f"**{len(lead_ids)}** lead(s) selected.")
    action = st.radio(
        "Action",
        ["Assign owner", "Change status"],
        horizontal=True,
        key="crm_lead_bulk_action",
    )
    if action == "Assign owner":
        owner_id, owner_name = _owner_choice(adapter, "crm_lead_bulk_owner")
        run = lambda: adapter.bulk_assign_leads(lead_ids, owner_id, owner_name)
    else:
        status = st.selectbox(
            "Status",
            [
                s
                for s in LEAD_STATUSES
                if s not in (LeadStatus.CONVERTED.value, LeadStatus.LOST.value)
            ],
            key="crm_lead_bulk_status",
        )
        run = lambda: adapter.bulk_set_lead_status(lead_ids, status)

    def _apply_bulk() -> None:
        done, failed = run()
        st.session_state["_crm_bulk_result"] = (done, failed)

    cols = st.columns(2)
    if cols[0].button("Apply", type="primary", width="stretch", disabled=not lead_ids):
        _apply(_apply_bulk, flag=LEAD_BULK, success=f"Updated {len(lead_ids)} lead(s)")
    _cancel_button(LEAD_BULK, "crm_lead_bulk_cancel", cols[1])


# --- enquiries ---------------------------------------------------------------
@st.dialog("Add Enquiry", width="large", on_dismiss=make_dismiss_handler(ENQUIRY_ADD))
def enquiry_add_dialog(
    adapter: CrmAdapter,
    services: dict,
    *,
    lead_id: str = "",
    customer_id: str = "",
    party_name: str = "",
) -> None:
    locked = bool(lead_id or customer_id)
    leads, customers = ([], [])
    if not locked:
        leads = adapter.list_leads(limit=1000)
        customers = _customer_options(services)
    payload = render_enquiry_form(
        "crm_enquiry_add",
        adapter,
        leads=leads,
        customers=customers,
        lock_party=locked,
    )
    if locked:
        payload["lead_id"] = lead_id
        payload["customer_id"] = customer_id
        payload["party_name"] = payload.get("party_name") or party_name

    cols = st.columns(2)
    if cols[0].button("Create Enquiry", type="primary", width="stretch"):
        _apply(
            lambda: adapter.create_enquiry(payload),
            flag=ENQUIRY_ADD,
            success="Enquiry created",
        )
    _cancel_button(ENQUIRY_ADD, "crm_enquiry_add_cancel", cols[1])


@st.dialog("Edit Enquiry", width="large", on_dismiss=make_dismiss_handler(ENQUIRY_EDIT))
def enquiry_edit_dialog(adapter: CrmAdapter, enquiry_id: str) -> None:
    enquiry = adapter.get_enquiry(enquiry_id)
    if enquiry is None:
        st.error("Enquiry not found.")
        return
    payload = render_enquiry_form(
        "crm_enquiry_edit", adapter, enquiry, lock_party=True
    )

    def _save() -> None:
        adapter.update_enquiry(enquiry_id, payload)
        if payload.get("assigned_user_id") != text(field(enquiry, "assigned_user_id")):
            adapter.assign_enquiry(
                enquiry_id,
                payload.get("assigned_user_id", ""),
                payload.get("assigned_user_name", ""),
            )

    cols = st.columns(2)
    if cols[0].button("Save Changes", type="primary", width="stretch"):
        _apply(_save, flag=ENQUIRY_EDIT, success="Enquiry updated")
    _cancel_button(ENQUIRY_EDIT, "crm_enquiry_edit_cancel", cols[1])


@st.dialog("Assign Enquiry", on_dismiss=make_dismiss_handler(ENQUIRY_ASSIGN))
def enquiry_assign_dialog(adapter: CrmAdapter, enquiry_id: str) -> None:
    enquiry = adapter.get_enquiry(enquiry_id)
    if enquiry is None:
        st.error("Enquiry not found.")
        return
    st.caption(text(field(enquiry, "party_name")))
    owner_id, owner_name = _owner_choice(
        adapter, "crm_enquiry_assign_owner", text(field(enquiry, "assigned_user_id"))
    )
    cols = st.columns(2)
    if cols[0].button("Assign", type="primary", width="stretch"):
        _apply(
            lambda: adapter.assign_enquiry(enquiry_id, owner_id, owner_name),
            flag=ENQUIRY_ASSIGN,
            success="Enquiry assigned",
        )
    _cancel_button(ENQUIRY_ASSIGN, "crm_enquiry_assign_cancel", cols[1])


@st.dialog("Change Enquiry Status", on_dismiss=make_dismiss_handler(ENQUIRY_STATUS))
def enquiry_status_dialog(adapter: CrmAdapter, enquiry_id: str) -> None:
    enquiry = adapter.get_enquiry(enquiry_id)
    if enquiry is None:
        st.error("Enquiry not found.")
        return
    st.caption(text(field(enquiry, "party_name")))
    status = st.selectbox(
        "Status",
        ENQUIRY_STATUSES,
        index=index_of(ENQUIRY_STATUSES, field(enquiry, "status")),
        key="crm_enquiry_status_value",
    )
    reason = ""
    if status == EnquiryStatus.LOST.value:
        reasons = lost_reasons(adapter)
        reason = st.selectbox("Lost reason", reasons, key="crm_enquiry_lost_reason")
    cols = st.columns(2)
    if cols[0].button("Update Status", type="primary", width="stretch"):
        _apply(
            lambda: adapter.set_enquiry_status(enquiry_id, status, reason),
            flag=ENQUIRY_STATUS,
            success=f"Status set to {status}",
        )
    _cancel_button(ENQUIRY_STATUS, "crm_enquiry_status_cancel", cols[1])


# --- activities --------------------------------------------------------------
@st.dialog("Add Activity", width="large", on_dismiss=make_dismiss_handler(ACTIVITY_ADD))
def activity_add_dialog(
    adapter: CrmAdapter,
    services: dict,
    *,
    lead_id: str = "",
    enquiry_id: str = "",
    customer_id: str = "",
    party_name: str = "",
    activity_type: str = "",
) -> None:
    locked = bool(lead_id or enquiry_id or customer_id)
    leads, customers = ([], [])
    if not locked:
        leads = adapter.list_leads(limit=1000)
        customers = _customer_options(services)
    payload = render_activity_form(
        "crm_activity_add",
        adapter,
        lead_id=lead_id,
        enquiry_id=enquiry_id,
        customer_id=customer_id,
        party_name=party_name,
        default_activity_type=activity_type,
        leads=leads,
        customers=customers,
        lock_party=locked,
    )
    cols = st.columns(2)
    if cols[0].button("Create Activity", type="primary", width="stretch"):
        _apply(
            lambda: adapter.create_activity(payload),
            flag=ACTIVITY_ADD,
            success="Activity created",
        )
    _cancel_button(ACTIVITY_ADD, "crm_activity_add_cancel", cols[1])


@st.dialog("Complete Activity", on_dismiss=make_dismiss_handler(ACTIVITY_COMPLETE))
def activity_complete_dialog(adapter: CrmAdapter, activity_id: str) -> None:
    activity = adapter.get_activity(activity_id)
    if activity is None:
        st.error("Activity not found.")
        return
    st.caption(
        f"{text(field(activity, 'activity_type'))} · "
        f"{text(field(activity, 'party_name'), default='—')}"
    )
    outcomes = activity_outcomes(adapter)
    outcome = st.selectbox("Outcome", outcomes, key="crm_activity_outcome")
    notes = st.text_area("Notes", key="crm_activity_complete_notes", height=80)
    next_action = st.text_input("Next action", key="crm_activity_next_action")
    schedule_follow_up = st.checkbox(
        "Schedule a follow-up", key="crm_activity_followup_toggle"
    )
    follow_up: Optional[datetime] = None
    if schedule_follow_up:
        cols = st.columns(2)
        follow_up_date = cols[0].date_input(
            "Follow-up date",
            value=date.today(),
            key="crm_activity_followup_date",
            format="DD/MM/YYYY",
        )
        follow_up_time = cols[1].time_input(
            "Time", value=time(9, 0), key="crm_activity_followup_time", step=900
        )
        follow_up = as_datetime(follow_up_date, follow_up_time)

    buttons = st.columns(2)
    if buttons[0].button("Mark Completed", type="primary", width="stretch"):
        _apply(
            lambda: adapter.complete_activity(
                activity_id,
                outcome=outcome,
                notes=notes,
                next_action=next_action,
                next_follow_up_at=follow_up,
            ),
            flag=ACTIVITY_COMPLETE,
            success="Activity completed",
        )
    _cancel_button(ACTIVITY_COMPLETE, "crm_activity_complete_cancel", buttons[1])


@st.dialog("Reschedule Activity", on_dismiss=make_dismiss_handler(ACTIVITY_RESCHEDULE))
def activity_reschedule_dialog(adapter: CrmAdapter, activity_id: str) -> None:
    activity = adapter.get_activity(activity_id)
    if activity is None:
        st.error("Activity not found.")
        return
    current = field(activity, "scheduled_at")
    st.caption(text(field(activity, "activity_type")))
    cols = st.columns(2)
    new_date = cols[0].date_input(
        "New date",
        value=current.date() if isinstance(current, datetime) else date.today(),
        key="crm_activity_resched_date",
        format="DD/MM/YYYY",
    )
    new_time = cols[1].time_input(
        "New time",
        value=current.time() if isinstance(current, datetime) else time(9, 0),
        key="crm_activity_resched_time",
        step=900,
    )
    reason = st.text_input("Reason (optional)", key="crm_activity_resched_reason")
    buttons = st.columns(2)
    if buttons[0].button("Reschedule", type="primary", width="stretch"):
        _apply(
            lambda: adapter.reschedule_activity(
                activity_id, as_datetime(new_date, new_time), reason
            ),
            flag=ACTIVITY_RESCHEDULE,
            success="Activity rescheduled",
        )
    _cancel_button(ACTIVITY_RESCHEDULE, "crm_activity_resched_cancel", buttons[1])


@st.dialog("Cancel Activity", on_dismiss=make_dismiss_handler(ACTIVITY_CANCEL))
def activity_cancel_dialog(adapter: CrmAdapter, activity_id: str) -> None:
    activity = adapter.get_activity(activity_id)
    if activity is None:
        st.error("Activity not found.")
        return
    st.warning(f"Cancel **{text(field(activity, 'activity_type'))}**?")
    reason = st.text_input("Cancellation reason *", key="crm_activity_cancel_reason")
    buttons = st.columns(2)
    if buttons[0].button(
        "Cancel Activity", type="primary", width="stretch", disabled=not reason.strip()
    ):
        _apply(
            lambda: adapter.cancel_activity(activity_id, reason),
            flag=ACTIVITY_CANCEL,
            success="Activity cancelled",
        )
    _cancel_button(ACTIVITY_CANCEL, "crm_activity_cancel_close", buttons[1])


# --- dispatchers -------------------------------------------------------------
def open_lead_dialogs_if_armed(adapter: CrmAdapter, services: dict) -> None:
    dispatch = {
        LEAD_ADD: lambda _: lead_add_dialog(adapter),
        LEAD_EDIT: lambda v: lead_edit_dialog(adapter, v),
        LEAD_ASSIGN: lambda v: lead_assign_dialog(adapter, v),
        LEAD_STATUS: lambda v: lead_status_dialog(adapter, v),
        LEAD_LOST: lambda v: lead_lost_dialog(adapter, v),
        LEAD_REOPEN: lambda v: lead_reopen_dialog(adapter, v),
        LEAD_CONVERT: lambda v: lead_convert_dialog(adapter, v),
        LEAD_BULK: lambda v: lead_bulk_dialog(adapter, list(v or [])),
    }
    _dispatch(dispatch)


def open_enquiry_dialogs_if_armed(adapter: CrmAdapter, services: dict) -> None:
    dispatch = {
        ENQUIRY_ADD: lambda v: enquiry_add_dialog(
            adapter, services, **(v if isinstance(v, dict) else {})
        ),
        ENQUIRY_EDIT: lambda v: enquiry_edit_dialog(adapter, v),
        ENQUIRY_ASSIGN: lambda v: enquiry_assign_dialog(adapter, v),
        ENQUIRY_STATUS: lambda v: enquiry_status_dialog(adapter, v),
    }
    _dispatch(dispatch)


def open_activity_dialogs_if_armed(adapter: CrmAdapter, services: dict) -> None:
    dispatch = {
        ACTIVITY_ADD: lambda v: activity_add_dialog(
            adapter, services, **(v if isinstance(v, dict) else {})
        ),
        ACTIVITY_COMPLETE: lambda v: activity_complete_dialog(adapter, v),
        ACTIVITY_RESCHEDULE: lambda v: activity_reschedule_dialog(adapter, v),
        ACTIVITY_CANCEL: lambda v: activity_cancel_dialog(adapter, v),
    }
    _dispatch(dispatch)


_UNSET = object()


def _dispatch(dispatch: dict) -> None:
    """Open the first armed dialog. ``{}`` counts as armed; ``None`` does not."""
    for flag, opener in dispatch.items():
        value = st.session_state.get(flag, _UNSET)
        if value is _UNSET or value is None or value is False:
            continue
        register_armed_dialog(flag)
        opener(value)
        return


def open_all_dialogs_if_armed(adapter: CrmAdapter, services: dict) -> None:
    open_lead_dialogs_if_armed(adapter, services)
    open_enquiry_dialogs_if_armed(adapter, services)
    open_activity_dialogs_if_armed(adapter, services)
