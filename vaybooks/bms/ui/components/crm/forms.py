"""CRM create/edit form fields. Each renderer returns a service payload dict."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any, Optional

import streamlit as st

from vaybooks.bms.domain.crm.enums import ActivityStatus, LeadPriority, LeadStatus
from vaybooks.bms.ui.components.crm.common import (
    activity_outcomes,
    activity_types,
    index_of,
    lead_sources,
)
from vaybooks.bms.ui.crm_adapters import CrmAdapter, as_datetime, field, text

PRIORITIES = [p.value for p in LeadPriority]
LEAD_STATUSES = [s.value for s in LeadStatus]
UNASSIGNED = "— Unassigned —"


def _owner_picker(
    adapter: CrmAdapter, key: str, current_id: str = "", label: str = "Owner"
) -> tuple[str, str]:
    """Return the chosen ``(user_id, user_name)``; blank when unassigned."""
    owners = adapter.owners()
    ids = [""] + [oid for oid, _ in owners]
    labels = {"": UNASSIGNED, **{oid: name for oid, name in owners}}
    if current_id and current_id not in ids:
        ids.append(current_id)
        labels[current_id] = adapter.owner_name(current_id)
    choice = st.selectbox(
        label,
        ids,
        index=ids.index(current_id) if current_id in ids else 0,
        format_func=lambda v: labels.get(v, v),
        key=key,
    )
    return choice, ("" if not choice else labels.get(choice, ""))


def _date_time_pair(
    label: str, key_prefix: str, current: Any = None, *, optional: bool = True
) -> Optional[datetime]:
    """Optional date + time inputs collapsed into one ``datetime``."""
    current_dt = current if isinstance(current, datetime) else None
    cols = st.columns([2, 1, 1])
    with cols[0]:
        chosen_date = st.date_input(
            label,
            value=current_dt.date() if current_dt else None,
            key=f"{key_prefix}_date",
            format="DD/MM/YYYY",
        )
    with cols[1]:
        chosen_time = st.time_input(
            "Time",
            value=current_dt.time() if current_dt else time(9, 0),
            key=f"{key_prefix}_time",
            step=900,
        )
    with cols[2]:
        clear = st.checkbox("None", value=False, key=f"{key_prefix}_none") if optional else False
    if clear or not chosen_date:
        return None
    return as_datetime(chosen_date, chosen_time)


def render_lead_form(
    key_prefix: str, adapter: CrmAdapter, lead: Any = None, *, with_status: bool = False
) -> dict:
    """Lead fields; the returned payload matches ``create_lead`` keywords."""
    sources = lead_sources(adapter)
    name_col, contact_col = st.columns(2)
    name = name_col.text_input(
        "Lead name *", value=text(field(lead, "name")), key=f"{key_prefix}_name"
    )
    contact_person = contact_col.text_input(
        "Contact person",
        value=text(field(lead, "contact_person")),
        key=f"{key_prefix}_contact",
    )

    phone_col, alt_col, email_col = st.columns(3)
    phone = phone_col.text_input(
        "Phone",
        value=text(field(lead, "phone")),
        key=f"{key_prefix}_phone",
        placeholder="10-digit mobile",
    )
    alternate_phone = alt_col.text_input(
        "Alternate phone",
        value=text(field(lead, "alternate_phone")),
        key=f"{key_prefix}_alt",
    )
    email = email_col.text_input(
        "Email", value=text(field(lead, "email")), key=f"{key_prefix}_email"
    )

    source_col, priority_col, value_col = st.columns(3)
    source_options = [""] + sources
    source = source_col.selectbox(
        "Source",
        source_options,
        index=index_of(source_options, field(lead, "source")),
        format_func=lambda v: v or "— Select —",
        key=f"{key_prefix}_source",
    )
    priority = priority_col.selectbox(
        "Priority",
        PRIORITIES,
        index=index_of(PRIORITIES, field(lead, "priority"), PRIORITIES.index("Medium")),
        key=f"{key_prefix}_priority",
    )
    estimated_value = value_col.number_input(
        "Estimated value (₹)",
        min_value=0.0,
        step=1000.0,
        value=float(field(lead, "estimated_value", default=0.0) or 0.0),
        key=f"{key_prefix}_value",
    )

    status = text(field(lead, "status"), default=LeadStatus.NEW.value)
    if with_status:
        status = st.selectbox(
            "Status",
            LEAD_STATUSES,
            index=index_of(LEAD_STATUSES, status),
            key=f"{key_prefix}_status",
        )

    owner_id, owner_name = _owner_picker(
        adapter, f"{key_prefix}_owner", text(field(lead, "assigned_user_id"))
    )

    interested_products = st.text_input(
        "Interested products",
        value=text(field(lead, "interested_products")),
        key=f"{key_prefix}_products",
    )
    next_follow_up_at = _date_time_pair(
        "Next follow-up", f"{key_prefix}_followup", field(lead, "next_follow_up_at")
    )

    with st.expander("Address and tax", expanded=False):
        addr1 = st.text_input(
            "Address line 1",
            value=text(field(lead, "address_line1")),
            key=f"{key_prefix}_addr1",
        )
        addr2 = st.text_input(
            "Address line 2",
            value=text(field(lead, "address_line2")),
            key=f"{key_prefix}_addr2",
        )
        area_col, city_col = st.columns(2)
        area = area_col.text_input(
            "Area", value=text(field(lead, "area")), key=f"{key_prefix}_area"
        )
        city = city_col.text_input(
            "City", value=text(field(lead, "city")), key=f"{key_prefix}_city"
        )
        state_col, pin_col, gstin_col = st.columns(3)
        state_code = state_col.text_input(
            "State code",
            value=text(field(lead, "state_code")),
            key=f"{key_prefix}_state",
        )
        pincode = pin_col.text_input(
            "Pincode", value=text(field(lead, "pincode")), key=f"{key_prefix}_pin"
        )
        gstin = gstin_col.text_input(
            "GSTIN", value=text(field(lead, "gstin")), key=f"{key_prefix}_gstin"
        )

    notes = st.text_area(
        "Notes", value=text(field(lead, "notes")), key=f"{key_prefix}_notes", height=80
    )

    return {
        "name": name,
        "phone": phone,
        "contact_person": contact_person,
        "alternate_phone": alternate_phone,
        "email": email,
        "address_line1": addr1,
        "address_line2": addr2,
        "area": area,
        "city": city,
        "state_code": state_code,
        "pincode": pincode,
        "gstin": gstin,
        "source": source,
        "interested_products": interested_products,
        "estimated_value": estimated_value,
        "assigned_user_id": owner_id,
        "assigned_user_name": owner_name,
        "priority": priority,
        "status": status,
        "next_follow_up_at": next_follow_up_at,
        "notes": notes,
    }


def render_enquiry_form(
    key_prefix: str,
    adapter: CrmAdapter,
    enquiry: Any = None,
    *,
    leads: Optional[list] = None,
    customers: Optional[list] = None,
    lock_party: bool = False,
) -> dict:
    """Enquiry fields; the payload matches ``create_enquiry`` keywords."""
    sources = lead_sources(adapter)
    lead_id = text(field(enquiry, "lead_id"))
    customer_id = text(field(enquiry, "customer_id"))
    party_name = text(field(enquiry, "party_name"))

    if not lock_party:
        lead_options = [("", "— None —")] + [
            (text(field(l, "id")), text(field(l, "name"))) for l in leads or []
        ]
        customer_options = [("", "— None —")] + [
            (text(field(c, "id")), text(field(c, "customer_name"))) for c in customers or []
        ]
        lead_col, cust_col = st.columns(2)
        with lead_col:
            lead_ids = [v for v, _ in lead_options]
            lead_labels = dict(lead_options)
            lead_id = st.selectbox(
                "Lead",
                lead_ids,
                index=lead_ids.index(lead_id) if lead_id in lead_ids else 0,
                format_func=lambda v: lead_labels.get(v, v),
                key=f"{key_prefix}_lead",
            )
        with cust_col:
            customer_ids = [v for v, _ in customer_options]
            customer_labels = dict(customer_options)
            customer_id = st.selectbox(
                "Customer",
                customer_ids,
                index=(
                    customer_ids.index(customer_id) if customer_id in customer_ids else 0
                ),
                format_func=lambda v: customer_labels.get(v, v),
                key=f"{key_prefix}_customer",
            )
        st.caption("An enquiry must be linked to a lead or a customer.")

    party_name = st.text_input(
        "Party name",
        value=party_name,
        key=f"{key_prefix}_party",
        help="Defaults to the linked lead or customer when left blank.",
    )

    product_col, source_col = st.columns(2)
    product_interest = product_col.text_input(
        "Product interest",
        value=text(field(enquiry, "product_interest")),
        key=f"{key_prefix}_product",
    )
    source_options = [""] + sources
    source = source_col.selectbox(
        "Source",
        source_options,
        index=index_of(source_options, field(enquiry, "source")),
        format_func=lambda v: v or "— Select —",
        key=f"{key_prefix}_source",
    )

    qty_col, value_col, priority_col = st.columns(3)
    expected_quantity = qty_col.number_input(
        "Expected quantity",
        min_value=0.0,
        step=1.0,
        value=float(field(enquiry, "expected_quantity", default=0.0) or 0.0),
        key=f"{key_prefix}_qty",
    )
    estimated_value = value_col.number_input(
        "Estimated value (₹)",
        min_value=0.0,
        step=1000.0,
        value=float(field(enquiry, "estimated_value", default=0.0) or 0.0),
        key=f"{key_prefix}_value",
    )
    priority = priority_col.selectbox(
        "Priority",
        PRIORITIES,
        index=index_of(PRIORITIES, field(enquiry, "priority"), PRIORITIES.index("Medium")),
        key=f"{key_prefix}_priority",
    )

    owner_id, owner_name = _owner_picker(
        adapter, f"{key_prefix}_owner", text(field(enquiry, "assigned_user_id"))
    )
    expected_decision_at = _date_time_pair(
        "Expected decision", f"{key_prefix}_decision", field(enquiry, "expected_decision_at")
    )
    next_follow_up_at = _date_time_pair(
        "Next follow-up", f"{key_prefix}_followup", field(enquiry, "next_follow_up_at")
    )

    description = st.text_area(
        "Description",
        value=text(field(enquiry, "description")),
        key=f"{key_prefix}_description",
        height=80,
    )
    notes = st.text_area(
        "Notes", value=text(field(enquiry, "notes")), key=f"{key_prefix}_notes", height=68
    )

    return {
        "lead_id": lead_id,
        "customer_id": customer_id,
        "party_name": party_name,
        "source": source,
        "product_interest": product_interest,
        "description": description,
        "expected_quantity": expected_quantity,
        "estimated_value": estimated_value,
        "priority": priority,
        "assigned_user_id": owner_id,
        "assigned_user_name": owner_name,
        "expected_decision_at": expected_decision_at,
        "next_follow_up_at": next_follow_up_at,
        "notes": notes,
    }


def render_activity_form(
    key_prefix: str,
    adapter: CrmAdapter,
    activity: Any = None,
    *,
    lead_id: str = "",
    enquiry_id: str = "",
    customer_id: str = "",
    party_name: str = "",
    default_activity_type: str = "",
    leads: Optional[list] = None,
    customers: Optional[list] = None,
    lock_party: bool = False,
) -> dict:
    """Activity fields; the payload matches ``create_manual`` keywords."""
    types = activity_types(adapter)
    outcomes = [""] + activity_outcomes(adapter)

    type_col, priority_col = st.columns(2)
    activity_type = type_col.selectbox(
        "Activity type *",
        types,
        index=index_of(
            types,
            field(activity, "activity_type", default=default_activity_type),
        ),
        key=f"{key_prefix}_type",
    )
    priority = priority_col.selectbox(
        "Priority",
        PRIORITIES,
        index=index_of(PRIORITIES, field(activity, "priority"), PRIORITIES.index("Medium")),
        key=f"{key_prefix}_priority",
    )

    lead_id = text(field(activity, "lead_id"), default=lead_id)
    customer_id = text(field(activity, "customer_id"), default=customer_id)
    enquiry_id = text(field(activity, "enquiry_id"), default=enquiry_id)
    party_name = text(field(activity, "party_name"), default=party_name)

    if not lock_party:
        lead_options = [("", "— None —")] + [
            (text(field(l, "id")), text(field(l, "name"))) for l in leads or []
        ]
        customer_options = [("", "— None —")] + [
            (text(field(c, "id")), text(field(c, "customer_name"))) for c in customers or []
        ]
        lead_col, cust_col = st.columns(2)
        with lead_col:
            lead_ids = [v for v, _ in lead_options]
            lead_labels = dict(lead_options)
            lead_id = st.selectbox(
                "Lead",
                lead_ids,
                index=lead_ids.index(lead_id) if lead_id in lead_ids else 0,
                format_func=lambda v: lead_labels.get(v, v),
                key=f"{key_prefix}_lead",
            )
        with cust_col:
            customer_ids = [v for v, _ in customer_options]
            customer_labels = dict(customer_options)
            customer_id = st.selectbox(
                "Customer",
                customer_ids,
                index=(
                    customer_ids.index(customer_id) if customer_id in customer_ids else 0
                ),
                format_func=lambda v: customer_labels.get(v, v),
                key=f"{key_prefix}_customer",
            )
        st.caption("An activity must be linked to a lead, enquiry, or customer.")
    elif party_name:
        st.caption(f"Linked to **{party_name}**")

    owner_id, owner_name = _owner_picker(
        adapter,
        f"{key_prefix}_owner",
        text(field(activity, "assigned_user_id")),
        label="Assigned to",
    )

    scheduled_at = _date_time_pair(
        "Scheduled for",
        f"{key_prefix}_scheduled",
        field(activity, "scheduled_at") or datetime.combine(date.today(), time(9, 0)),
    )
    location = st.text_input(
        "Location", value=text(field(activity, "location")), key=f"{key_prefix}_location"
    )

    outcome = st.selectbox(
        "Outcome",
        outcomes,
        index=index_of(outcomes, field(activity, "outcome")),
        format_func=lambda v: v or "— Not recorded —",
        key=f"{key_prefix}_outcome",
    )

    with st.expander("Payment promise", expanded=False):
        promise_cols = st.columns(2)
        promised_amount = promise_cols[0].number_input(
            "Promised amount (₹)",
            min_value=0.0,
            step=1000.0,
            value=float(field(activity, "promised_amount", default=0.0) or 0.0),
            key=f"{key_prefix}_promised_amount",
        )
        with promise_cols[1]:
            promised_date = _date_time_pair(
                "Promised on", f"{key_prefix}_promised", field(activity, "promised_date")
            )

    notes = st.text_area(
        "Notes", value=text(field(activity, "notes")), key=f"{key_prefix}_notes", height=80
    )
    next_action = st.text_input(
        "Next action",
        value=text(field(activity, "next_action")),
        key=f"{key_prefix}_next_action",
    )
    next_follow_up_at = _date_time_pair(
        "Next follow-up", f"{key_prefix}_next_followup", field(activity, "next_follow_up_at")
    )

    return {
        "activity_type": activity_type,
        "lead_id": lead_id,
        "enquiry_id": enquiry_id,
        "customer_id": customer_id,
        "party_name": party_name,
        "assigned_user_id": owner_id,
        "assigned_user_name": owner_name,
        "scheduled_at": scheduled_at,
        "activity_at": scheduled_at,
        "outcome": outcome,
        "notes": notes,
        "next_action": next_action,
        "next_follow_up_at": next_follow_up_at,
        "location": location,
        "priority": priority,
        "promised_amount": promised_amount,
        "promised_date": promised_date,
        "status": text(field(activity, "status"), default=ActivityStatus.SCHEDULED.value),
    }
