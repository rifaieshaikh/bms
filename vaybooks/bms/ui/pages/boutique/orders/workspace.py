"""Resumable customization order workspace.

Steps: Customer → Measurements ⇄ Items ⇄ Advance & ETD
Order is created as DRAFT after customer selection.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import streamlit as st

from vaybooks.bms.domain.shared.enums import AttachmentCategory, OrderStatus
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.customer_identity_selector import (
    render_customer_identity_selector,
)
from vaybooks.bms.ui.components.measurement_form import measurement_form
from vaybooks.bms.ui.dialog_utils import (
    clear_all_dialog_flags,
    make_dismiss_handler,
    register_armed_dialog,
)

WORKSPACE_ORDER_ID = "order_workspace_order_id"
WORKSPACE_STEP = "order_workspace_step"
WS_ADD_ITEM = "ws_add_item_dialog"
WS_EDIT_ITEM = "ws_edit_item_dialog"
WS_REMOVE_ITEM = "ws_remove_item_dialog"
WS_ADD_MEASUREMENT = "ws_add_measurement_dialog"
WS_EDIT_MEASUREMENT = "ws_edit_measurement_dialog"
WS_REMOVE_MEASUREMENT = "ws_remove_measurement_dialog"

STEPS = ["Customer", "Measurements", "Items", "Advance & ETD"]


def _set_step(step: str) -> None:
    st.session_state[WORKSPACE_STEP] = step


def _step_nav(current: str) -> None:
    cols = st.columns(len(STEPS))
    for i, step in enumerate(STEPS):
        label = f"{i + 1}. {step}"
        if step == current:
            cols[i].button(label, type="primary", disabled=True, use_container_width=True)
        else:
            # Only allow leaving Customer after draft exists (except staying on Customer)
            order_id = st.session_state.get(WORKSPACE_ORDER_ID)
            disabled = step != "Customer" and not order_id
            if cols[i].button(label, disabled=disabled, use_container_width=True):
                _set_step(step)
                st.rerun()


def _render_customer_step(services: dict) -> None:
    order_service = services["orders"]
    customer_service = services["customers"]
    order_id = st.session_state.get(WORKSPACE_ORDER_ID)
    if order_id:
        order = order_service.get_order_detail(order_id)
        if order:
            st.success(
                f"Draft order **{order.order_number}** for "
                f"{order.customer_name} ({order.phone_number})"
            )
            notes = st.text_area("Order notes", value=order.notes, key="ws_order_notes")
            cols = st.columns(3)
            if cols[0].button("Save notes"):
                order_service.update_order_notes(order.id, notes)
                st.success("Notes saved")
            if cols[1].button("Next: Measurements", type="primary"):
                _set_step("Measurements")
                st.rerun()
            if cols[2].button("Save & Exit"):
                st.session_state.pop(WORKSPACE_ORDER_ID, None)
                st.session_state.pop(WORKSPACE_STEP, None)
                navigation.go_to_detail("order_detail", order.id)
            return

    st.subheader("Select or create customer")
    selection = render_customer_identity_selector(
        customer_service, key_prefix="ws_cust"
    )
    notes = st.text_area("Order notes", key="ws_new_order_notes")
    etd = st.date_input(
        "Expected delivery date",
        value=date.today() + timedelta(days=7),
        key="ws_new_order_etd",
    )
    if st.button("Create draft order", type="primary"):
        if not selection.customer_name or not selection.phone_number:
            st.error("Customer name and mobile are required")
            return
        try:
            order = order_service.create_draft_order(
                customer_name=selection.customer_name,
                phone_number=selection.phone_number,
                notes=notes,
                expected_delivery_date=etd,
                customer_id=selection.customer_id or None,
            )
            st.session_state[WORKSPACE_ORDER_ID] = order.id
            _set_step("Measurements")
            st.success(f"Created draft {order.order_number}")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def _measurement_print_button(
    services: dict, order, record, *, key: str, label: str = "Print"
) -> None:
    try:
        from vaybooks.bms.infrastructure.pdf.measurement_pdf import (
            generate_measurement_sheet_pdf,
        )

        business = services["business"].get_profile()
        customer = services["customers"].get_customer_detail(order.customer_id)
        pdf_bytes = generate_measurement_sheet_pdf(record, customer, business)
        st.download_button(
            label,
            data=pdf_bytes,
            file_name=f"{record.measurement_number}.pdf",
            mime="application/pdf",
            key=key,
            icon=":material/print:",
            use_container_width=True,
        )
    except Exception as exc:
        st.caption(f"Print unavailable: {exc}")


def _measurement_linked_on_customer_orders(services: dict, customer_id: str, record_id: str) -> list[str]:
    linked = []
    for customer_order in services["orders"].list_by_customer(customer_id):
        for item in customer_order.customization_items:
            if item.measurement_id == record_id:
                linked.append(
                    f"{customer_order.order_number} / {item.bill_number}"
                )
    return linked


@st.dialog(
    "Add Measurement",
    width="large",
    on_dismiss=make_dismiss_handler(WS_ADD_MEASUREMENT),
)
def _add_measurement_dialog(services: dict, order) -> None:
    st.caption("Saved to this customer and available for items on this and future orders.")
    saved = measurement_form(
        services,
        customer_id=order.customer_id,
        order_id=order.id,
        key_prefix="ws_add_ms",
    )
    if saved:
        st.session_state.pop(WS_ADD_MEASUREMENT, None)
        st.toast(f"Saved {saved.measurement_number}")
        st.rerun()
    if st.button("Cancel", key="ws_add_ms_cancel"):
        st.session_state.pop(WS_ADD_MEASUREMENT, None)
        st.rerun()


@st.dialog(
    "Edit Measurement",
    width="large",
    on_dismiss=make_dismiss_handler(WS_EDIT_MEASUREMENT),
)
def _edit_measurement_dialog(services: dict, order, record_id: str) -> None:
    record = services["measurements"].get_record(record_id)
    if not record:
        st.error("Measurement not found")
        st.session_state.pop(WS_EDIT_MEASUREMENT, None)
        return

    st.markdown(f"**{record.measurement_number}**")
    _measurement_print_button(
        services,
        order,
        record,
        key=f"ws_edit_ms_print_{record.id}",
        label="Print measurement",
    )
    saved = measurement_form(
        services,
        customer_id=order.customer_id,
        order_id=order.id,
        existing=record,
        key_prefix=f"ws_edit_ms_{record.id}",
    )
    if saved:
        st.session_state.pop(WS_EDIT_MEASUREMENT, None)
        st.toast(f"Updated {saved.measurement_number}")
        st.rerun()
    if st.button("Cancel", key=f"ws_edit_ms_cancel_{record.id}"):
        st.session_state.pop(WS_EDIT_MEASUREMENT, None)
        st.rerun()


@st.dialog(
    "Remove Measurement",
    on_dismiss=make_dismiss_handler(WS_REMOVE_MEASUREMENT),
)
def _remove_measurement_dialog(services: dict, order, record_id: str) -> None:
    record = services["measurements"].get_record(record_id)
    if not record:
        st.error("Measurement not found")
        st.session_state.pop(WS_REMOVE_MEASUREMENT, None)
        return

    linked = _measurement_linked_on_customer_orders(
        services, order.customer_id, record.id
    )
    st.warning(
        f"Remove **{record.measurement_number}**"
        + (f" · {record.wearer_name}" if record.wearer_name else "")
        + "?"
    )
    if linked:
        st.error(
            "This measurement is linked to customization items and cannot be removed:\n"
            + "\n".join(f"- {row}" for row in linked)
        )
        if st.button("Close", key=f"ws_rm_ms_close_{record.id}"):
            st.session_state.pop(WS_REMOVE_MEASUREMENT, None)
            st.rerun()
        return

    cols = st.columns(2)
    if cols[0].button(
        "Cancel", use_container_width=True, key=f"ws_rm_ms_cancel_{record.id}"
    ):
        st.session_state.pop(WS_REMOVE_MEASUREMENT, None)
        st.rerun()
    if cols[1].button(
        "Remove measurement",
        type="primary",
        use_container_width=True,
        key=f"ws_rm_ms_confirm_{record.id}",
    ):
        try:
            services["measurements"].delete_record(record.id)
            st.session_state.pop(WS_REMOVE_MEASUREMENT, None)
            st.toast("Measurement removed")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def _render_measurements_step(services: dict, order) -> None:
    measurement_service = services["measurements"]
    records = measurement_service.list_by_customer(order.customer_id)

    st.subheader("Measurements")
    if st.button(
        "Add measurement",
        type="primary",
        icon=":material/add:",
        key="ws_open_add_ms",
    ):
        clear_all_dialog_flags()
        st.session_state[WS_ADD_MEASUREMENT] = True
        register_armed_dialog(WS_ADD_MEASUREMENT)
        st.rerun()

    if not records:
        st.info(
            "No measurements yet. Use **Add measurement** to capture the first "
            "record for this customer."
        )
    else:
        for rec in records:
            with st.container(border=True):
                head = st.columns([3, 1, 1, 1])
                with head[0]:
                    title = f"**{rec.measurement_number}** · {rec.person_type.value}"
                    if rec.wearer_name:
                        title += f" · {rec.wearer_name}"
                    st.markdown(title)
                    st.caption(
                        f"Measured {rec.measured_at} · {len(rec.values)} fields · "
                        f"fit {rec.fit_preference.value}"
                    )
                if head[1].button(
                    "Edit",
                    key=f"ws_ms_edit_{rec.id}",
                    use_container_width=True,
                    icon=":material/edit:",
                ):
                    clear_all_dialog_flags()
                    st.session_state[WS_EDIT_MEASUREMENT] = rec.id
                    register_armed_dialog(WS_EDIT_MEASUREMENT)
                    st.rerun()
                if head[2].button(
                    "Remove",
                    key=f"ws_ms_remove_{rec.id}",
                    use_container_width=True,
                    icon=":material/delete:",
                ):
                    clear_all_dialog_flags()
                    st.session_state[WS_REMOVE_MEASUREMENT] = rec.id
                    register_armed_dialog(WS_REMOVE_MEASUREMENT)
                    st.rerun()
                with head[3]:
                    _measurement_print_button(
                        services,
                        order,
                        rec,
                        key=f"ws_ms_print_{rec.id}",
                        label="Print",
                    )

    if st.session_state.get(WS_ADD_MEASUREMENT):
        _add_measurement_dialog(services, order)
    edit_ms_id = st.session_state.get(WS_EDIT_MEASUREMENT)
    if edit_ms_id:
        _edit_measurement_dialog(services, order, edit_ms_id)
    remove_ms_id = st.session_state.get(WS_REMOVE_MEASUREMENT)
    if remove_ms_id:
        _remove_measurement_dialog(services, order, remove_ms_id)

    cols = st.columns(3)
    if cols[0].button("Back: Customer"):
        _set_step("Customer")
        st.rerun()
    if cols[1].button("Next: Items", type="primary"):
        _set_step("Items")
        st.rerun()
    if cols[2].button("Save & Exit"):
        st.session_state.pop(WORKSPACE_ORDER_ID, None)
        st.session_state.pop(WORKSPACE_STEP, None)
        navigation.go_to_detail("order_detail", order.id)


def _item_media_uploaders(services, order, item, key_prefix: str) -> None:
    attachment_service = services["attachments"]
    categories = [
        (AttachmentCategory.REFERENCE, "Reference images", ["png", "jpg", "jpeg", "webp"]),
        (AttachmentCategory.DESIGN, "Design pictures", ["png", "jpg", "jpeg", "webp"]),
        (AttachmentCategory.PATTERN, "Pattern pictures", ["png", "jpg", "jpeg", "webp"]),
        (
            AttachmentCategory.FILE_OUT,
            "File out (production)",
            ["pdf", "dxf", "ai", "zip", "png", "jpg"],
        ),
    ]
    for category, label, types in categories:
        st.markdown(f"**{label}**")
        existing = attachment_service.list_by_item(item.item_id, category.value)
        for att in existing:
            c1, c2 = st.columns([4, 1])
            c1.write(f"{att.name} ({att.size_bytes // 1024} KB)")
            if c2.button("Remove", key=f"{key_prefix}_rm_{att.id}"):
                attachment_service.delete(att.id)
                st.rerun()
            if att.category != AttachmentCategory.FILE_OUT and att.data:
                try:
                    st.image(att.data, width=120)
                except Exception:
                    pass
            else:
                st.download_button(
                    "Download",
                    data=att.data,
                    file_name=att.name,
                    mime=att.content_type,
                    key=f"{key_prefix}_dl_{att.id}",
                )
        uploaded = st.file_uploader(
            f"Upload {label}",
            type=types,
            accept_multiple_files=True,
            key=f"{key_prefix}_up_{category.value}",
        )
        if uploaded and st.button(
            f"Save {label}", key=f"{key_prefix}_save_{category.value}"
        ):
            try:
                for file in uploaded:
                    attachment_service.upload(
                        order_id=order.id,
                        item_id=item.item_id,
                        category=category.value,
                        name=file.name,
                        content_type=file.type or "application/octet-stream",
                        data=file.getvalue(),
                    )
                st.success("Uploaded")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))


def _clear_add_item_form_state() -> None:
    for key in list(st.session_state.keys()):
        if key.startswith("ws_add_item_"):
            st.session_state.pop(key, None)
    st.session_state.pop("ws_add_item_ms_prev", None)


def _measurement_options(measurements) -> dict[str, str]:
    return {
        m.id: f"{m.measurement_number} · {m.person_type.value}"
        + (f" · {m.wearer_name}" if m.wearer_name else "")
        for m in measurements
    }


def _activity_required_map(activities, key_prefix: str, defaults: Optional[dict] = None) -> dict:
    required_map = {}
    defaults = defaults or {}
    for activity in activities:
        default = defaults.get(
            activity.activity_name,
            activity.activity_name
            in ("Stitching", "Handwork", "Material Purchase"),
        )
        required_map[activity.activity_name] = st.checkbox(
            f"{activity.activity_name} (Required)",
            value=default,
            key=f"{key_prefix}_act_{activity.id}",
        )
    return required_map


@st.dialog("Add Item", width="large", on_dismiss=make_dismiss_handler(WS_ADD_ITEM))
def _add_item_dialog(services: dict, order) -> None:
    order_service = services["orders"]
    activity_service = services["activities"]
    measurement_service = services["measurements"]
    activities = activity_service.list_activities()
    measurements = measurement_service.list_by_customer(order.customer_id)
    ms_labels = _measurement_options(measurements)

    ms_choice = st.selectbox(
        "Link measurement (optional)",
        options=["(none)"] + list(ms_labels.values()),
        key="ws_add_item_ms",
        help=(
            "Optional. If linked, the measurement bill number is assigned from "
            "the measurement. If not linked, enter a measurement bill number."
        ),
    )
    measurement_id = None
    auto_bill = ""
    if ms_choice != "(none)":
        measurement_id = next(
            mid for mid, label in ms_labels.items() if label == ms_choice
        )
        record = measurement_service.get_record(measurement_id)
        try:
            auto_bill = order_service.allocate_measurement_bill_number(
                record.measurement_number
            )
        except Exception:
            auto_bill = f"{record.measurement_number}-01"

    prev_ms = st.session_state.get("ws_add_item_ms_prev")
    if ms_choice != prev_ms:
        st.session_state["ws_add_item_bill"] = auto_bill if measurement_id else ""
        st.session_state["ws_add_item_ms_prev"] = ms_choice

    has_measurement = measurement_id is not None
    bill_number = st.text_input(
        "Measurement bill number",
        key="ws_add_item_bill",
        disabled=has_measurement,
        help=(
            f"Assigned from the selected measurement ({auto_bill})."
            if has_measurement
            else "Required when no measurement is linked."
        ),
    )
    description = st.text_input("Item description", key="ws_add_item_desc")
    customer_specification = st.text_area(
        "Customer specification", key="ws_add_item_spec"
    )
    item_etd = st.date_input(
        "Item ETD",
        value=order.expected_delivery_date or date.today() + timedelta(days=7),
        key="ws_add_item_etd",
    )
    st.markdown("**Required activities**")
    required_map = _activity_required_map(activities, "ws_add_item")

    cols = st.columns(2)
    if cols[0].button("Cancel", use_container_width=True, key="ws_add_item_cancel"):
        st.session_state.pop(WS_ADD_ITEM, None)
        _clear_add_item_form_state()
        st.rerun()
    if cols[1].button(
        "Save item", type="primary", use_container_width=True, key="ws_add_item_save"
    ):
        if not description:
            st.error("Item description is required")
        elif not has_measurement and not (bill_number or "").strip():
            st.error(
                "Measurement bill number is required when no measurement is linked"
            )
        elif not any(required_map.values()):
            st.error("Select at least one required activity")
        else:
            try:
                order_service.add_item_to_order(
                    order.id,
                    description=description,
                    required_activities=required_map,
                    bill_number=bill_number,
                    expected_delivery_date=item_etd,
                    customer_specification=customer_specification,
                    measurement_id=measurement_id,
                )
                st.session_state.pop(WS_ADD_ITEM, None)
                _clear_add_item_form_state()
                st.toast("Item added")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))


@st.dialog("Edit Item", width="large", on_dismiss=make_dismiss_handler(WS_EDIT_ITEM))
def _edit_item_dialog(services: dict, order, item_id: str) -> None:
    order_service = services["orders"]
    item = order.get_item_by_id(item_id)
    if not item:
        st.error("Item not found")
        st.session_state.pop(WS_EDIT_ITEM, None)
        return

    has_measurement = bool(item.measurement_id)
    if item.measurement_number:
        st.caption(f"Linked measurement: {item.measurement_number}")

    bill_number = st.text_input(
        "Measurement bill number",
        value=item.bill_number,
        key=f"ws_edit_item_bill_{item_id}",
        disabled=has_measurement,
        help=(
            f"Assigned from measurement {item.measurement_number}."
            if has_measurement
            else "Required when the item has no linked measurement."
        ),
    )
    description = st.text_input(
        "Item description",
        value=item.description,
        key=f"ws_edit_item_desc_{item_id}",
    )
    customer_specification = st.text_area(
        "Customer specification",
        value=item.customer_specification or "",
        key=f"ws_edit_item_spec_{item_id}",
    )
    item_etd = st.date_input(
        "Item ETD",
        value=item.expected_delivery_date or order.expected_delivery_date,
        key=f"ws_edit_item_etd_{item_id}",
    )

    activities = order.activities_for_item(item.item_id)
    if activities:
        st.markdown("**Activities**")
        for activity in activities:
            st.caption(f"• {activity.activity_name} — {activity.current_status}")

    with st.expander("Media & files", expanded=False):
        _item_media_uploaders(
            services, order, item, key_prefix=f"ws_edit_media_{item.item_id}"
        )

    try:
        from vaybooks.bms.infrastructure.pdf.customization_item_pdf import (
            generate_customization_item_pdf,
        )

        business = services["business"].get_profile()
        customer = services["customers"].get_customer_detail(order.customer_id)
        ms = (
            services["measurements"].get_record(item.measurement_id)
            if item.measurement_id
            else None
        )
        attachments = services["attachments"].list_by_item(item.item_id)
        pdf_bytes = generate_customization_item_pdf(
            order, item, customer, business, ms, attachments
        )
        st.download_button(
            "Print Customization Item with Notes",
            data=pdf_bytes,
            file_name=f"{item.bill_number}.pdf",
            mime="application/pdf",
            key=f"ws_edit_item_pdf_{item.item_id}",
            icon=":material/print:",
        )
    except Exception as exc:
        st.caption(f"Print unavailable: {exc}")

    cols = st.columns(2)
    if cols[0].button("Cancel", use_container_width=True, key=f"ws_edit_cancel_{item_id}"):
        st.session_state.pop(WS_EDIT_ITEM, None)
        st.rerun()
    if cols[1].button(
        "Save changes",
        type="primary",
        use_container_width=True,
        key=f"ws_edit_save_{item_id}",
    ):
        if not description:
            st.error("Item description is required")
        elif not has_measurement and not (bill_number or "").strip():
            st.error("Measurement bill number is required")
        else:
            try:
                order_service.update_customization_item(
                    order.id,
                    item.item_id,
                    bill_number,
                    description,
                    expected_delivery_date=item_etd,
                    customer_specification=customer_specification,
                )
                st.session_state.pop(WS_EDIT_ITEM, None)
                st.toast("Item updated")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))


@st.dialog("Remove Item", on_dismiss=make_dismiss_handler(WS_REMOVE_ITEM))
def _remove_item_dialog(services: dict, order, item_id: str) -> None:
    order_service = services["orders"]
    item = order.get_item_by_id(item_id)
    if not item:
        st.error("Item not found")
        st.session_state.pop(WS_REMOVE_ITEM, None)
        return

    st.warning(
        f"Remove **{item.bill_number}** — {item.description or 'No description'}? "
        "This also removes its activities from the order."
    )
    cols = st.columns(2)
    if cols[0].button("Cancel", use_container_width=True, key=f"ws_rm_cancel_{item_id}"):
        st.session_state.pop(WS_REMOVE_ITEM, None)
        st.rerun()
    if cols[1].button(
        "Remove item",
        type="primary",
        use_container_width=True,
        key=f"ws_rm_confirm_{item_id}",
    ):
        try:
            order_service.remove_customization_item(order.id, item.item_id)
            st.session_state.pop(WS_REMOVE_ITEM, None)
            st.toast("Item removed")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))


def _render_items_step(services: dict, order) -> None:
    st.subheader("Customization items")
    if st.button("Add item", type="primary", icon=":material/add:", key="ws_open_add_item"):
        clear_all_dialog_flags()
        _clear_add_item_form_state()
        st.session_state[WS_ADD_ITEM] = True
        register_armed_dialog(WS_ADD_ITEM)
        st.rerun()

    if not order.customization_items:
        st.info("No items yet. Use **Add item** to create the first customization item.")
    else:
        for item in order.customization_items:
            with st.container(border=True):
                head = st.columns([3, 1, 1, 1])
                with head[0]:
                    st.markdown(
                        f"**{item.bill_number}** — {item.description or 'No description'}"
                    )
                    if item.measurement_number:
                        st.caption(f"Measurement: {item.measurement_number}")
                    elif item.customer_specification:
                        st.caption(item.customer_specification[:80])
                if head[1].button(
                    "Edit",
                    key=f"ws_item_edit_{item.item_id}",
                    use_container_width=True,
                    icon=":material/edit:",
                ):
                    clear_all_dialog_flags()
                    st.session_state[WS_EDIT_ITEM] = item.item_id
                    register_armed_dialog(WS_EDIT_ITEM)
                    st.rerun()
                if head[2].button(
                    "Remove",
                    key=f"ws_item_remove_{item.item_id}",
                    use_container_width=True,
                    icon=":material/delete:",
                ):
                    clear_all_dialog_flags()
                    st.session_state[WS_REMOVE_ITEM] = item.item_id
                    register_armed_dialog(WS_REMOVE_ITEM)
                    st.rerun()
                try:
                    from vaybooks.bms.infrastructure.pdf.customization_item_pdf import (
                        generate_customization_item_pdf,
                    )

                    business = services["business"].get_profile()
                    customer = services["customers"].get_customer_detail(
                        order.customer_id
                    )
                    ms = (
                        services["measurements"].get_record(item.measurement_id)
                        if item.measurement_id
                        else None
                    )
                    attachments = services["attachments"].list_by_item(item.item_id)
                    pdf_bytes = generate_customization_item_pdf(
                        order, item, customer, business, ms, attachments
                    )
                    head[3].download_button(
                        "Print",
                        data=pdf_bytes,
                        file_name=f"{item.bill_number}.pdf",
                        mime="application/pdf",
                        key=f"ws_item_pdf_{item.item_id}",
                        icon=":material/print:",
                        use_container_width=True,
                    )
                except Exception:
                    head[3].caption("Print N/A")

    if st.session_state.get(WS_ADD_ITEM):
        _add_item_dialog(services, order)
    edit_item_id = st.session_state.get(WS_EDIT_ITEM)
    if edit_item_id:
        _edit_item_dialog(services, order, edit_item_id)
    remove_item_id = st.session_state.get(WS_REMOVE_ITEM)
    if remove_item_id:
        _remove_item_dialog(services, order, remove_item_id)

    cols = st.columns(3)
    if cols[0].button("Back: Measurements"):
        _set_step("Measurements")
        st.rerun()
    if cols[1].button("Next: Advance & ETD", type="primary"):
        _set_step("Advance & ETD")
        st.rerun()
    if cols[2].button("Save & Exit"):
        st.session_state.pop(WORKSPACE_ORDER_ID, None)
        st.session_state.pop(WORKSPACE_STEP, None)
        navigation.go_to_detail("order_detail", order.id)


def _render_advance_step(services: dict, order) -> None:
    order_service = services["orders"]
    accounting = services["accounting"]
    st.subheader("Advance & ETD")
    etd = st.date_input(
        "Order ETD",
        value=order.expected_delivery_date or date.today() + timedelta(days=7),
        key="ws_adv_etd",
    )
    advance = st.number_input(
        "Advance amount",
        min_value=0.0,
        value=float(order.advance_amount or 0),
        step=100.0,
        key="ws_adv_amt",
    )
    cash_accounts = accounting.get_store_accounts()
    account_labels = {a.id: a.account_name for a in cash_accounts}
    receiving_id = None
    if account_labels:
        choice = st.selectbox(
            "Receiving account",
            options=list(account_labels.values()),
            key="ws_adv_recv",
        )
        receiving_id = next(
            aid for aid, name in account_labels.items() if name == choice
        )

    cols = st.columns(2)
    if cols[0].button("Save advance & ETD"):
        try:
            order_service.update_order_etd(order.id, etd)
            saved, voucher = order_service.save_order_advance(
                order.id, advance, receiving_id
            )
            st.session_state["ws_last_advance_voucher_id"] = (
                voucher.id if voucher else None
            )
            st.success("Saved")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    voucher = order_service.find_advance_voucher(order.id)
    if voucher:
        st.info(f"Advance voucher **{voucher.voucher_number}** · ₹{order.advance_amount:,.2f}")
        try:
            from vaybooks.bms.infrastructure.pdf.advance_receipt_pdf import (
                generate_advance_receipt_pdf,
            )

            business = services["business"].get_profile()
            customer = services["customers"].get_customer_detail(order.customer_id)
            pdf_bytes = generate_advance_receipt_pdf(
                voucher, order, customer, business
            )
            st.download_button(
                "Download advance receipt",
                data=pdf_bytes,
                file_name=f"{voucher.voucher_number}_advance.pdf",
                mime="application/pdf",
                key="ws_adv_pdf",
            )
        except Exception as exc:
            st.caption(f"Receipt print unavailable: {exc}")

    if cols[1].button("Confirm order", type="primary"):
        try:
            order_service.update_order_etd(order.id, etd)
            if advance > 0:
                order_service.save_order_advance(order.id, advance, receiving_id)
            confirmed = order_service.confirm_order(order.id)
            st.session_state.pop(WORKSPACE_ORDER_ID, None)
            st.session_state.pop(WORKSPACE_STEP, None)
            st.success(f"Order {confirmed.order_number} confirmed")
            navigation.go_to_detail("order_detail", confirmed.id)
        except Exception as exc:
            st.error(str(exc))

    if st.button("Back: Items"):
        _set_step("Items")
        st.rerun()


def render(services: dict):
    st.title("New Customization Order")
    st.caption(
        "Create a draft after selecting the customer, then add measurements "
        "and items in any order. Confirm when ready."
    )

    # Allow deep-link resume: ?order=<id>
    param_order = navigation.consume_list_param("order_workspace", "order")
    if param_order:
        st.session_state[WORKSPACE_ORDER_ID] = param_order
        st.session_state.setdefault(WORKSPACE_STEP, "Measurements")

    step = st.session_state.get(WORKSPACE_STEP, "Customer")
    _step_nav(step)

    order = None
    order_id = st.session_state.get(WORKSPACE_ORDER_ID)
    if order_id:
        order = services["orders"].get_order_detail(order_id)
        if not order:
            st.session_state.pop(WORKSPACE_ORDER_ID, None)
            order_id = None
            step = "Customer"
            _set_step(step)

    if step == "Customer" or not order:
        _render_customer_step(services)
        return
    if step == "Measurements":
        _render_measurements_step(services, order)
        return
    if step == "Items":
        _render_items_step(services, order)
        return
    if step == "Advance & ETD":
        _render_advance_step(services, order)
        return
