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

WORKSPACE_ORDER_ID = "order_workspace_order_id"
WORKSPACE_STEP = "order_workspace_step"

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


def _render_measurements_step(services: dict, order) -> None:
    measurement_service = services["measurements"]
    records = measurement_service.list_by_customer(order.customer_id)
    st.subheader("Measurements")
    if records:
        for rec in records:
            with st.expander(
                f"{rec.measurement_number} · {rec.person_type.value}"
                + (f" · {rec.wearer_name}" if rec.wearer_name else ""),
                expanded=False,
            ):
                st.write(
                    f"Measured {rec.measured_at} · "
                    f"{len(rec.values)} fields · fit {rec.fit_preference.value}"
                )
                if st.button("Edit", key=f"ws_edit_ms_{rec.id}"):
                    st.session_state["ws_editing_measurement"] = rec.id
                pdf_bytes = None
                try:
                    from vaybooks.bms.infrastructure.pdf.measurement_pdf import (
                        generate_measurement_sheet_pdf,
                    )

                    business = services["business"].get_profile()
                    customer = services["customers"].get_customer_detail(order.customer_id)
                    pdf_bytes = generate_measurement_sheet_pdf(
                        rec, customer, business
                    )
                except Exception:
                    pdf_bytes = None
                if pdf_bytes:
                    st.download_button(
                        "Download measurement PDF",
                        data=pdf_bytes,
                        file_name=f"{rec.measurement_number}.pdf",
                        mime="application/pdf",
                        key=f"ws_dl_ms_{rec.id}",
                    )

    editing_id = st.session_state.get("ws_editing_measurement")
    existing = (
        measurement_service.get_record(editing_id) if editing_id else None
    )
    st.markdown("### " + ("Edit measurement" if existing else "Add measurement"))
    saved = measurement_form(
        services,
        customer_id=order.customer_id,
        order_id=order.id,
        existing=existing,
        key_prefix=f"ws_ms_{editing_id or 'new'}",
    )
    if saved:
        st.session_state.pop("ws_editing_measurement", None)
        st.success(f"Saved {saved.measurement_number}")
        st.rerun()

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


def _render_items_step(services: dict, order) -> None:
    order_service = services["orders"]
    activity_service = services["activities"]
    measurement_service = services["measurements"]
    activities = activity_service.list_activities()
    measurements = measurement_service.list_by_customer(order.customer_id)

    st.subheader("Customization items")
    if order.customization_items:
        for item in order.customization_items:
            with st.expander(
                f"{item.bill_number} — {item.description or 'No description'}",
                expanded=False,
            ):
                st.write(item.customer_specification or "_No specification_")
                if item.measurement_number:
                    st.caption(f"Linked measurement: {item.measurement_number}")
                _item_media_uploaders(
                    services, order, item, key_prefix=f"ws_item_{item.item_id}"
                )
                try:
                    from vaybooks.bms.infrastructure.pdf.customization_item_pdf import (
                        generate_customization_item_pdf,
                    )

                    business = services["business"].get_profile()
                    customer = services["customers"].get_customer_detail(order.customer_id)
                    ms = (
                        measurement_service.get_record(item.measurement_id)
                        if item.measurement_id
                        else None
                    )
                    attachments = services["attachments"].list_by_item(item.item_id)
                    pdf_bytes = generate_customization_item_pdf(
                        order, item, customer, business, ms, attachments
                    )
                    st.download_button(
                        "Download item PDF",
                        data=pdf_bytes,
                        file_name=f"{item.bill_number}.pdf",
                        mime="application/pdf",
                        key=f"ws_item_pdf_{item.item_id}",
                    )
                except Exception as exc:
                    st.caption(f"Print unavailable: {exc}")

    st.markdown("### Add item")
    ms_labels = {
        m.id: f"{m.measurement_number} · {m.person_type.value}"
        + (f" · {m.wearer_name}" if m.wearer_name else "")
        for m in measurements
    }
    ms_choice = st.selectbox(
        "Link measurement (optional)",
        options=["(none)"] + list(ms_labels.values()),
        key="ws_new_item_ms",
    )
    measurement_id = None
    suggested_bill = ""
    if ms_choice != "(none)":
        measurement_id = next(
            mid for mid, label in ms_labels.items() if label == ms_choice
        )
        record = measurement_service.get_record(measurement_id)
        try:
            suggested_bill = order_service.allocate_measurement_bill_number(
                record.measurement_number
            )
        except Exception:
            suggested_bill = f"{record.measurement_number}-01"

    bill_number = st.text_input(
        "Bill number",
        value=suggested_bill,
        key="ws_new_item_bill",
    )
    description = st.text_input("Item description", key="ws_new_item_desc")
    customer_specification = st.text_area(
        "Customer specification", key="ws_new_item_spec"
    )
    item_etd = st.date_input(
        "Item ETD",
        value=order.expected_delivery_date or date.today() + timedelta(days=7),
        key="ws_new_item_etd",
    )
    required_map = {}
    for activity in activities:
        default = activity.activity_name in (
            "Stitching",
            "Handwork",
            "Material Purchase",
        )
        required_map[activity.activity_name] = st.checkbox(
            f"{activity.activity_name} (Required)",
            value=default,
            key=f"ws_new_item_act_{activity.id}",
        )

    if st.button("Save item", type="primary"):
        if not description or not bill_number:
            st.error("Bill number and description are required")
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
                st.success("Item added")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

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
