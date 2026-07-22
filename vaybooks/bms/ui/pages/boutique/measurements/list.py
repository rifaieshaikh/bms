"""Customer-owned measurement records list and editor."""

from __future__ import annotations

from datetime import date, datetime

import streamlit as st

from vaybooks.bms.infrastructure.pdf.measurement_pdf import (
    generate_measurement_sheet_pdf,
)
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.common.list_view import render_list
from vaybooks.bms.ui.components.boutique.measurement_form import measurement_form
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler
from vaybooks.bms.ui.list_schemas import MEASUREMENTS
from vaybooks.bms.ui.session_keys import filters_key
from vaybooks.bms.ui.styles import render_card_grid

NEW_DIALOG = "measurement_new_dialog"


def _fmt_date(value) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime("%d %b %Y")
    return str(value) if value else "—"


def _load_measurements(services, filters, sort):
    records = services["measurements"].list_all()
    customers = {
        str(customer.id): customer
        for customer in services["customers"].list_all_customers()
    }
    for record in records:
        customer = customers.get(str(record.customer_id))
        record.customer_name = (
            customer.customer_name if customer else "Unknown customer"
        )
        record.customer_phone = customer.phone_number if customer else ""
    return records


def _measurement_card(services: dict, record, index: int) -> None:
    with st.container(border=True):
        st.markdown(f"**{record.measurement_number}**")
        st.caption(
            f"{record.customer_name}"
            + (f" · {record.customer_phone}" if record.customer_phone else "")
        )
        wearer = record.wearer_name or "Customer"
        st.write(f"**Wearer:** {wearer} · {record.person_type.value}")
        st.caption(
            f"Measured {_fmt_date(record.measured_at)} · "
            f"{len(record.values)} fields · {record.fit_preference.value} fit"
        )
        if st.button(
            "View / Edit",
            key=f"measurement_edit_{index}_{record.id}",
            type="primary",
            use_container_width=True,
        ):
            navigation.go_to_detail("measurement_detail", record.id)


def _render_cards(page_records, services):
    render_card_grid(
        page_records,
        lambda record, index: _measurement_card(services, record, index),
        suffix="measurements",
    )


def _apply_customer_deep_link() -> None:
    customer_id = navigation.consume_list_param("measurements_list", "customer")
    if not customer_id:
        return
    from vaybooks.bms.ui import filtering as F

    key = filters_key(MEASUREMENTS.entity_key)
    committed = st.session_state.setdefault(key, F.default_filters(MEASUREMENTS))
    committed["customer_id"] = customer_id
    st.session_state.pop(f"{MEASUREMENTS.entity_key}_flt_customer_id", None)


@st.dialog(
    "New Measurement",
    width="large",
    on_dismiss=make_dismiss_handler(NEW_DIALOG),
)
def _new_measurement_dialog(services: dict) -> None:
    customers = sorted(
        services["customers"].list_all_customers(),
        key=lambda customer: customer.customer_name.casefold(),
    )
    if not customers:
        st.warning("Add a customer before recording measurements.")
        return

    labels = {
        str(customer.id): (
            f"{customer.customer_name}"
            + (f" · {customer.phone_number}" if customer.phone_number else "")
        )
        for customer in customers
    }
    customer_id = st.selectbox(
        "Customer",
        options=list(labels),
        format_func=labels.get,
        key="measurement_new_customer",
    )
    st.caption(
        "This measurement is saved to the customer and can be reused on future orders."
    )
    saved = measurement_form(
        services,
        customer_id=customer_id,
        key_prefix=f"measurement_new_{customer_id}",
    )
    if saved:
        st.session_state.pop(NEW_DIALOG, None)
        st.success(f"Saved {saved.measurement_number}")
        st.rerun()


def render(services: dict) -> None:
    _apply_customer_deep_link()
    bar = render_list(
        MEASUREMENTS,
        services=services,
        load_fn=_load_measurements,
        card_renderer=_render_cards,
        primary_label="New Measurement",
        primary_key="measurements_add_btn",
        count_label="measurements",
        empty_text="No customer measurements found.",
        page_key_nav="measurements_list",
    )
    if bar["primary_clicked"]:
        st.session_state[NEW_DIALOG] = True
    if bar.get("view_nth") or bar.get("edit_nth"):
        navigation.go_to_detail(
            "measurement_detail", bar.get("edit_nth") or bar["view_nth"]
        )
    if st.session_state.get(NEW_DIALOG):
        _new_measurement_dialog(services)


def render_measurement_detail(services: dict) -> None:
    from vaybooks.bms.ui.keyboard.actions import consume_action
    from vaybooks.bms.ui.keyboard.context import set_current_page
    from vaybooks.bms.ui.keyboard.wired import mark_wired

    set_current_page("measurement_detail")
    mark_wired("nav.back")
    if st.button("← Back to measurements") or consume_action("nav.back"):
        navigation.go_back_to_list("measurements", "measurements_list")
        return

    record_id = navigation.current_detail_id("measurement_detail")
    record = services["measurements"].get_record(record_id) if record_id else None
    if not record:
        st.error("Measurement not found.")
        return

    customer = services["customers"].get_customer_detail(record.customer_id)
    st.title(record.measurement_number)
    if customer:
        header = st.columns([3, 1])
        header[0].write(
            f"**Customer:** {customer.customer_name}"
            + (f" · {customer.phone_number}" if customer.phone_number else "")
        )
        if header[1].button("Open customer", use_container_width=True):
            navigation.go_to_detail("customer_detail", customer.id)
            return

    st.caption(
        "Customer measurement · available for selection on this customer's future orders"
    )
    try:
        business = services["business"].get_profile()
        pdf_bytes = generate_measurement_sheet_pdf(record, customer, business)
        st.download_button(
            "Download measurement PDF",
            data=pdf_bytes,
            file_name=f"{record.measurement_number}.pdf",
            mime="application/pdf",
        )
    except Exception as exc:
        st.caption(f"Print unavailable: {exc}")

    st.subheader("Measurement details")
    saved = measurement_form(
        services,
        customer_id=record.customer_id,
        order_id=record.order_id,
        existing=record,
        key_prefix=f"measurement_detail_{record.id}",
    )
    if saved:
        st.success("Measurement updated")
        st.rerun()
