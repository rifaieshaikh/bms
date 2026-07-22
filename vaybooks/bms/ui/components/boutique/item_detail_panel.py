from datetime import date

import streamlit as st

from vaybooks.bms.domain.boutique.orders.bill_status import bill_is_delivered, bill_is_invoiced
from vaybooks.bms.domain.boutique.orders.entities import (
    COMPLETED_ACTIVITY_STATUS,
    CustomizationItem,
    CustomizationOrder,
)
from vaybooks.bms.domain.shared.date_utils import minutes_to_hours
from vaybooks.bms.domain.shared.enums import ActivityStatus, ExpenseSource
from vaybooks.bms.ui.components.boutique.time_entry_dialogs import (
    item_activities,
    item_time_dialog,
    save_time_entry,
    time_form_fields,
)
from vaybooks.bms.ui.dialog_utils import (
    clear_all_dialog_flags,
    dismiss_armed_dialogs,
    register_armed_dialog,
)
from vaybooks.bms.ui.session_keys import ACTIVITY_SKIP_NOTICE
from vaybooks.bms.ui.styles import metric_grid, panel, render_card_grid, status_badge


def _money(value: float) -> str:
    return f"\u20b9{value:,.0f}"


# --- session flag keys -------------------------------------------------------
def _add_flag_key(key_prefix: str) -> str:
    return f"add_activity_flag_{key_prefix}"


def _remove_flag_key(key_prefix: str) -> str:
    return f"remove_activity_flag_{key_prefix}"


def _time_flag_key(key_prefix: str) -> str:
    return f"time_dialog_{key_prefix}"


def _expense_flag_key(key_prefix: str) -> str:
    return f"expense_dialog_{key_prefix}"


def _complete_flag_key(key_prefix: str) -> str:
    return f"complete_flow_{key_prefix}"


def _change_status_flag_key(key_prefix: str) -> str:
    return f"change_status_flow_{key_prefix}"


def _activity_time_minutes(services, order_id, item_id, activity_id) -> int:
    return sum(
        e.duration_minutes
        for e in services["time_tracking"].get_entries_by_order(order_id)
        if e.bill_id == item_id and e.activity_id == activity_id
    )


def _activity_expenses(services, item_id, activity_id):
    return [
        e
        for e in services["expenses"].get_expenses_by_bill(item_id)
        if e.activity_id == activity_id
    ]


# --- helpers -----------------------------------------------------------------
def _item_activities(order: CustomizationOrder, item: CustomizationItem):
    return item_activities(order, item)


def _expense_source_for_activity(services: dict, activity_id: str) -> str:
    if activity_id:
        config = services["activities"].get_activity(activity_id)
        if config:
            try:
                return ExpenseSource(config.activity_type.value).value
            except ValueError:
                pass
    return ExpenseSource.OTHER.value


# --- order info card ---------------------------------------------------------
def _render_order_card(order, item, invoices, deliveries):
    with panel(f"item_head_{item.item_id}"):
        with st.container(border=True):
            head = st.columns([3, 1])
            with head[0]:
                st.markdown(f"### {item.bill_number}")
                st.caption(item.description or "No description")
            with head[1]:
                st.markdown(
                    status_badge(item.item_status.value), unsafe_allow_html=True
                )

            acts_done = order.item_activities_complete(item.item_id)
            invoiced = bill_is_invoiced(item.item_id, invoices)
            delivered = bill_is_delivered(item.item_id, deliveries)
            badges = " ".join(
                [
                    status_badge(
                        "Activities done" if acts_done else "Activities pending",
                        "green" if acts_done else "orange",
                    ),
                    status_badge(
                        "Invoiced" if invoiced else "Not invoiced",
                        "green" if invoiced else "gray",
                    ),
                    status_badge(
                        "Delivered" if delivered else "Not delivered",
                        "green" if delivered else "gray",
                    ),
                ]
            )
            st.markdown(badges, unsafe_allow_html=True)

    metric_grid(
        [
            ("Order", order.order_number),
            ("Customer", order.customer_name),
            ("Mobile", order.phone_number),
            ("Advance", _money(order.advance_amount)),
        ],
        suffix=f"item_info_{item.item_id}",
    )

    _render_item_mph(item, invoiced, delivered)


def _render_item_mph(item, invoiced: bool, delivered: bool):
    """Show the frozen per-item profitability snapshot."""
    if item.mph_snapshot_at:
        mph = item.margin_per_hour
        mph_txt = f"{_money(mph)}/h" if mph is not None else "—"
        metric_grid(
            [
                ("Revenue (net)", _money(item.sell_amount)),
                ("Margin", _money(item.margin_amount or 0)),
                ("In-house hours", f"{item.in_house_hours:.2f}"),
                ("MPH", mph_txt),
            ],
            suffix=f"item_mph_{item.item_id}",
        )
        st.caption(
            "Item MPH frozen on delivery "
            f"({item.mph_snapshot_at:%d %b %Y})."
            + ("" if item.margin_per_hour is not None else " No in-house hours logged.")
        )
    else:
        st.caption(
            "Item MPH is calculated once the item is both invoiced and delivered."
        )


# --- inline item edit --------------------------------------------------------
def _render_item_print(services, order, item, key_prefix):
    try:
        from vaybooks.bms.infrastructure.pdf.customization_item_pdf import (
            generate_customization_item_pdf,
        )

        business = services["business"].get_profile()
        customer = services["customers"].get_customer_detail(order.customer_id)
        measurement = None
        if item.measurement_id and "measurements" in services:
            measurement = services["measurements"].get_record(item.measurement_id)
        attachments = []
        if "attachments" in services:
            attachments = services["attachments"].list_by_item(item.item_id)
        pdf_bytes = generate_customization_item_pdf(
            order, item, customer, business, measurement, attachments
        )
        st.download_button(
            "Print Customization Item with Notes",
            data=pdf_bytes,
            file_name=f"{item.bill_number}.pdf",
            mime="application/pdf",
            key=f"item_pdf_{key_prefix}",
            icon=":material/print:",
            use_container_width=True,
        )
    except Exception as exc:
        st.caption(f"Print unavailable: {exc}")


def _render_item_edit_inline(services, order, item, key_prefix):
    order_service = services["orders"]
    has_measurement = bool(item.measurement_id)
    with st.container(border=True):
        st.markdown("**Item details**")
        cols = st.columns([1, 2, 1, 1])
        bill_number = cols[0].text_input(
            "Measurement Bill Number",
            value=item.bill_number,
            key=f"edit_bill_{key_prefix}",
            disabled=has_measurement,
            help=(
                f"Assigned from measurement {item.measurement_number}."
                if has_measurement
                else "Required when the item has no linked measurement."
            ),
        )
        description = cols[1].text_input(
            "Item Description", value=item.description, key=f"edit_desc_{key_prefix}"
        )
        item_etd = cols[2].date_input(
            "Item ETD",
            value=item.expected_delivery_date or order.expected_delivery_date,
            key=f"edit_etd_{key_prefix}",
        )
        cols[3].markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        if cols[3].button("Save", key=f"save_item_{key_prefix}", use_container_width=True):
            try:
                order_service.update_customization_item(
                    order.id, item.item_id, bill_number, description,
                    expected_delivery_date=item_etd,
                )
                st.toast("Item saved")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        if has_measurement and item.measurement_number:
            st.caption(f"Linked measurement: {item.measurement_number}")
        _render_item_print(services, order, item, key_prefix)

# --- activity dialogs --------------------------------------------------------
def _on_status_change(services, order_id, order_activity_id, widget_key, err_key):
    new_status = st.session_state.get(widget_key)
    try:
        services["orders"].update_activity_status(order_id, order_activity_id, new_status)
        st.session_state.pop(err_key, None)
    except Exception as exc:
        st.session_state[err_key] = str(exc)


@st.dialog("Add Activity", on_dismiss=dismiss_armed_dialogs)
def _add_activity_dialog(services: dict, order_id: str, item_id: str, flag_key: str):
    order_service = services["orders"]
    activity_service = services["activities"]
    order = order_service.get_order_detail(order_id)
    if not order:
        st.error("Order not found")
        return
    assigned_ids = {a.activity_id for a in order.activities_for_item(item_id)}
    available = [c for c in activity_service.list_activities() if c.id not in assigned_ids]
    if not available:
        st.info("All configured activities are already added to this item.")
        if st.button("Close"):
            st.session_state.pop(flag_key, None)
            st.rerun()
        return

    options = {c.activity_name: c.id for c in available}
    selected_name = st.selectbox("Select activity to add", list(options.keys()))
    cols = st.columns(2)
    if cols[0].button("Add", type="primary", use_container_width=True):
        try:
            order_service.add_activity_to_item(order_id, item_id, options[selected_name])
            st.session_state.pop(flag_key, None)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if cols[1].button("Cancel", use_container_width=True):
        st.session_state.pop(flag_key, None)
        st.rerun()


@st.dialog("Remove Activity", on_dismiss=dismiss_armed_dialogs)
def _remove_activity_dialog(services: dict, order_id: str, order_activity_id: str, flag_key: str):
    order_service = services["orders"]
    order = order_service.get_order_detail(order_id)
    activity = order.get_activity_by_id(order_activity_id) if order else None
    name = activity.activity_name if activity else "this activity"
    st.warning(f"Are you sure you want to remove **{name}**? This cannot be undone.")
    cols = st.columns(2)
    if cols[0].button("Yes, Remove", type="primary", use_container_width=True):
        try:
            order_service.remove_activity_from_item(order_id, order_activity_id)
            st.session_state.pop(flag_key, None)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if cols[1].button("Cancel", use_container_width=True):
        st.session_state.pop(flag_key, None)
        st.rerun()


# --- complete activity (records expense first) -------------------------------
def _complete_activity_body(services, order, item, activity, key_prefix, flag_key):
    expense_service = services["expenses"]
    config = services["activities"].get_activity(activity.activity_id)
    is_service = bool(config and config.requires_time_tracking)

    st.markdown(f"### Complete: {activity.activity_name}")

    minutes = _activity_time_minutes(services, order.id, item.item_id, activity.activity_id)
    hours = minutes_to_hours(minutes)
    if is_service and minutes == 0:
        st.warning(
            "Time tracking required. Please record time for "
            f"**{activity.activity_name}** before completing it."
        )
        cols = st.columns(2)
        if cols[0].button(
            "Record Time", key=f"cmpl_rectime_{key_prefix}", type="primary",
            use_container_width=True,
        ):
            st.session_state.pop(flag_key, None)
            st.session_state[f"section_{key_prefix}"] = "Time"
            st.rerun()
        if cols[1].button(
            "Close", key=f"cmpl_notime_close_{key_prefix}", use_container_width=True
        ):
            st.session_state.pop(flag_key, None)
            st.rerun()
        return
    if is_service:
        st.info(f"Hours spent on this activity: **{hours:.2f} h** ({minutes} min)")

    existing = _activity_expenses(services, item.item_id, activity.activity_id)
    if existing:
        total = sum(e.total_purchase_price for e in existing)
        st.success(
            f"Expense already recorded: {_money(total)} across {len(existing)} entry(ies)."
        )
        cols = st.columns(2)
        if cols[0].button(
            "Mark Completed", key=f"cmpl_done_{key_prefix}", type="primary", use_container_width=True
        ):
            try:
                services["orders"].complete_activity(
                    activity.order_activity_id, "Staff", add_expense=False
                )
                st.session_state.pop(flag_key, None)
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        if cols[1].button("Cancel", key=f"cmpl_cancel_{key_prefix}", use_container_width=True):
            st.session_state.pop(flag_key, None)
            st.rerun()
        return

    st.markdown("**Record expense to complete this activity**")
    default_rate = float(config.default_hourly_expense) if config else 0.0
    default_qty = hours if (is_service and hours > 0) else 1.0
    name = st.text_input(
        "Expense Name", value=activity.activity_name, key=f"cmpl_name_{key_prefix}"
    )
    cc = st.columns(2)
    rate = cc[0].number_input(
        "Price", value=default_rate, key=f"cmpl_rate_{key_prefix}"
    )
    qty = cc[1].number_input(
        "Qty", min_value=0.0, value=float(default_qty), key=f"cmpl_qty_{key_prefix}"
    )
    amount = round(rate * qty, 2)
    st.metric("Amount", _money(amount))
    notes = st.text_area("Notes", key=f"cmpl_notes_{key_prefix}")

    cols = st.columns(2)
    if cols[0].button(
        "Save Expense & Complete", key=f"cmpl_save_{key_prefix}", type="primary", use_container_width=True
    ):
        if rate <= 0:
            st.error("Price must be a positive value")
        else:
            try:
                source = _expense_source_for_activity(services, activity.activity_id)
                expense_service.add_expense(
                    order_id=order.id, expense_date=date.today(), expense_name=name,
                    expense_source=source, purchase_price=rate, selling_price=rate,
                    quantity=qty, bill_id=item.item_id, activity_id=activity.activity_id,
                    notes=notes,
                    linked_time_minutes=minutes if is_service else 0,
                    linked_time_hours=hours if is_service else 0.0,
                )
                services["orders"].complete_activity(
                    activity.order_activity_id, "Staff", add_expense=False
                )
                st.session_state.pop(flag_key, None)
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    if cols[1].button("Cancel", key=f"cmpl_cancel_{key_prefix}", use_container_width=True):
        st.session_state.pop(flag_key, None)
        st.rerun()


@st.dialog("Complete Activity", on_dismiss=dismiss_armed_dialogs)
def _complete_activity_dialog(services, order_id, key_prefix):
    flag_key = _complete_flag_key(key_prefix)
    target = st.session_state.get(flag_key)
    order = services["orders"].get_order_detail(order_id)
    activity = order.get_activity_by_id(target) if order else None
    item = order.get_item_by_id(activity.bill_id) if (order and activity) else None
    if not activity or not item:
        st.error("Activity not found")
        return
    _complete_activity_body(services, order, item, activity, key_prefix, flag_key)


# --- change status of a completed activity -----------------------------------
def _change_status_body(services, order, activity, key_prefix, flag_key):
    statuses = services["orders"].get_activity_statuses(activity.activity_id)
    selectable = [s for s in statuses if s != COMPLETED_ACTIVITY_STATUS] or ["Created"]
    st.write(
        f"**{activity.activity_name}** is currently *{activity.current_status}*. "
        "Pick a status to move it back into the workflow."
    )
    new_status = st.selectbox("New status", selectable, key=f"chg_sel_{key_prefix}")
    cols = st.columns(2)
    if cols[0].button("Update Status", key=f"chg_save_{key_prefix}", type="primary", use_container_width=True):
        try:
            services["orders"].update_activity_status(
                order.id, activity.order_activity_id, new_status
            )
            st.session_state.pop(flag_key, None)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if cols[1].button("Cancel", key=f"chg_cancel_{key_prefix}", use_container_width=True):
        st.session_state.pop(flag_key, None)
        st.rerun()


@st.dialog("Change Status", on_dismiss=dismiss_armed_dialogs)
def _change_status_dialog(services, order_id, key_prefix):
    flag_key = _change_status_flag_key(key_prefix)
    target = st.session_state.get(flag_key)
    order = services["orders"].get_order_detail(order_id)
    activity = order.get_activity_by_id(target) if order else None
    if not activity:
        st.error("Activity not found")
        return
    _change_status_body(services, order, activity, key_prefix, flag_key)


# --- activities management ---------------------------------------------------
def _render_activity_card(services, order, item, activity, key_prefix, allow_dialogs, locked):
    order_service = services["orders"]
    suffix = f"{key_prefix}_{activity.order_activity_id}"
    is_completed = activity.activity_status == ActivityStatus.COMPLETED
    is_skipped = activity.activity_status == ActivityStatus.SKIPPED

    with st.container(border=True):
        st.markdown(f"**{activity.activity_name}**")

        if is_completed:
            st.success(COMPLETED_ACTIVITY_STATUS)
            if st.button("Change Status", key=f"chg_btn_{suffix}", use_container_width=True):
                clear_all_dialog_flags()
                flag = _change_status_flag_key(key_prefix)
                st.session_state[flag] = activity.order_activity_id
                register_armed_dialog(flag)
                st.rerun()
            return

        if is_skipped:
            st.info(f"Activity {activity.activity_name} skipped")
            return

        statuses = order_service.get_activity_statuses(activity.activity_id)
        selectable = [s for s in statuses if s != COMPLETED_ACTIVITY_STATUS] or ["Created"]
        widget_key = f"status_sel_{suffix}"
        err_key = f"status_err_{suffix}"
        if widget_key not in st.session_state or st.session_state[widget_key] not in selectable:
            st.session_state[widget_key] = (
                activity.current_status if activity.current_status in selectable else selectable[0]
            )
        st.selectbox(
            "Status",
            selectable,
            key=widget_key,
            label_visibility="collapsed",
            on_change=_on_status_change,
            args=(services, order.id, activity.order_activity_id, widget_key, err_key),
        )
        if st.session_state.get(err_key):
            st.error(st.session_state[err_key])

        is_locked = activity.activity_id in locked
        if is_locked:
            btns = [st]
        elif activity.is_required:
            btns = st.columns(3)
        else:
            btns = st.columns(2)
        if btns[0].button("Complete", key=f"comp_{suffix}", type="primary", use_container_width=True):
            clear_all_dialog_flags()
            flag = _complete_flag_key(key_prefix)
            st.session_state[flag] = activity.order_activity_id
            register_armed_dialog(flag)
            st.rerun()
        if not is_locked:
            skip_col = 1 if activity.is_required else None
            if skip_col is not None and btns[skip_col].button(
                "Skip", key=f"skip_{suffix}", use_container_width=True
            ):
                try:
                    order_service.skip_activity(activity.order_activity_id, "Staff")
                    st.session_state[ACTIVITY_SKIP_NOTICE] = (
                        f"Activity {activity.activity_name} skipped"
                    )
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
            rem_col = 2 if activity.is_required else 1
            if btns[rem_col].button("Remove", key=f"rem_{suffix}", use_container_width=True):
                if allow_dialogs:
                    clear_all_dialog_flags()
                    flag = _remove_flag_key(key_prefix)
                    st.session_state[flag] = activity.order_activity_id
                    register_armed_dialog(flag)
                else:
                    st.session_state[f"inline_remove_{key_prefix}"] = activity.order_activity_id
                st.rerun()


def _render_inline_remove_confirm(services, order, key_prefix):
    target = st.session_state.get(f"inline_remove_{key_prefix}")
    if not target:
        return
    activity = order.get_activity_by_id(target)
    name = activity.activity_name if activity else "this activity"
    with st.container(border=True):
        st.warning(f"Remove **{name}**? This cannot be undone.")
        cols = st.columns(2)
        if cols[0].button("Yes, Remove", key=f"inl_rem_yes_{key_prefix}", type="primary"):
            try:
                services["orders"].remove_activity_from_item(order.id, target)
                st.session_state.pop(f"inline_remove_{key_prefix}", None)
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        if cols[1].button("Cancel", key=f"inl_rem_no_{key_prefix}"):
            st.session_state.pop(f"inline_remove_{key_prefix}", None)
            st.rerun()


def _render_inline_add_activity(services, order, item, key_prefix):
    if not st.session_state.get(f"inline_add_{key_prefix}"):
        return
    order_service = services["orders"]
    activity_service = services["activities"]
    assigned_ids = {a.activity_id for a in order.activities_for_item(item.item_id)}
    available = [c for c in activity_service.list_activities() if c.id not in assigned_ids]
    with st.container(border=True):
        if not available:
            st.caption("All configured activities are already added.")
            if st.button("Close", key=f"inl_add_close_{key_prefix}"):
                st.session_state.pop(f"inline_add_{key_prefix}", None)
                st.rerun()
            return
        options = {c.activity_name: c.id for c in available}
        selected_name = st.selectbox(
            "Select activity to add", list(options.keys()), key=f"inl_add_sel_{key_prefix}"
        )
        cols = st.columns(2)
        if cols[0].button("Add", key=f"inl_add_yes_{key_prefix}", type="primary"):
            try:
                order_service.add_activity_to_item(order.id, item.item_id, options[selected_name])
                st.session_state.pop(f"inline_add_{key_prefix}", None)
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        if cols[1].button("Cancel", key=f"inl_add_no_{key_prefix}"):
            st.session_state.pop(f"inline_add_{key_prefix}", None)
            st.rerun()


def _render_activity_management(services, order, item, key_prefix, allow_dialogs):
    if st.button("+ Add Activity", key=f"open_add_act_{key_prefix}", type="primary"):
        if allow_dialogs:
            clear_all_dialog_flags()
            _add_activity_dialog(
                services, order.id, item.item_id, _add_flag_key(key_prefix)
            )
        else:
            st.session_state[f"inline_add_{key_prefix}"] = True
            st.rerun()

    if not allow_dialogs:
        _render_inline_add_activity(services, order, item, key_prefix)
        _render_inline_remove_confirm(services, order, key_prefix)
        # Inline complete flow (order-view context can't open nested dialogs).
        complete_target = st.session_state.get(_complete_flag_key(key_prefix))
        if complete_target:
            activity = order.get_activity_by_id(complete_target)
            if activity:
                with st.container(border=True):
                    _complete_activity_body(
                        services, order, item, activity, key_prefix,
                        _complete_flag_key(key_prefix),
                    )
        change_target = st.session_state.get(_change_status_flag_key(key_prefix))
        if change_target:
            activity = order.get_activity_by_id(change_target)
            if activity:
                with st.container(border=True):
                    _change_status_body(
                        services, order, activity, key_prefix,
                        _change_status_flag_key(key_prefix),
                    )

    # Activities that have recorded time or expense cannot be removed.
    time_entries = services["time_tracking"].get_entries_by_order(order.id)
    expenses = services["expenses"].get_expenses_by_bill(item.item_id)
    locked = {e.activity_id for e in time_entries if e.bill_id == item.item_id}
    locked |= {e.activity_id for e in expenses}

    activities = _item_activities(order, item)
    if not activities:
        st.caption("No activities on this item yet.")
        return

    render_card_grid(
        activities,
        lambda activity, _i: _render_activity_card(
            services, order, item, activity, key_prefix, allow_dialogs, locked
        ),
        suffix=f"acts_{key_prefix}",
    )


# --- time dialogs / management ----------------------------------------------
def _render_time_summary(entries, item_activities_list):
    st.markdown("**Time summary**")
    totals = {}
    for e in entries:
        totals[e.activity_name] = totals.get(e.activity_name, 0) + e.duration_minutes
    total_minutes = sum(totals.values())
    metrics = [
        (name, f"{minutes_to_hours(minutes):.2f} h", f"{minutes} min")
        for name, minutes in totals.items()
    ]
    metrics.append(
        (
            "Total time",
            f"{minutes_to_hours(total_minutes):.2f} h",
            f"{total_minutes} min across {len(entries)} entries",
        )
    )
    metric_grid(metrics, suffix="time_summary")


def _render_time_management(services, order, item, key_prefix, allow_dialogs):
    time_service = services["time_tracking"]
    entries = [e for e in time_service.get_entries_by_order(order.id) if e.bill_id == item.item_id]
    item_activities = _item_activities(order, item)

    if st.button("+ Record Time", key=f"rec_time_{key_prefix}", type="primary"):
        if not item_activities:
            st.warning("Add an activity to this item first.")
        elif allow_dialogs:
            clear_all_dialog_flags()
            item_time_dialog(
                services, order.id, item.item_id, key_prefix, _time_flag_key(key_prefix)
            )
        else:
            st.session_state[f"inline_time_{key_prefix}"] = "new"
            st.rerun()

    if not allow_dialogs and st.session_state.get(f"inline_time_{key_prefix}"):
        target = st.session_state.get(f"inline_time_{key_prefix}")
        entry = None if target == "new" else time_service.get_entry(target)
        with st.container(border=True):
            st.markdown("**Record / Edit Time**")
            data = time_form_fields(item_activities, f"inl_{key_prefix}", entry)
            cols = st.columns(2)
            if cols[0].button("Save", key=f"inl_time_save_{key_prefix}", type="primary"):
                try:
                    if save_time_entry(
                        services, order, item, data, entry, f"inline_time_{key_prefix}"
                    ):
                        st.rerun()
                except Exception as exc:
                    st.error(str(exc))
            if cols[1].button("Cancel", key=f"inl_time_cancel_{key_prefix}"):
                st.session_state.pop(f"inline_time_{key_prefix}", None)
                st.rerun()

    _render_time_summary(entries, item_activities)

    st.markdown("**Recorded entries**")
    if not entries:
        st.caption("No time entries yet.")
        return

    def _entry_card(entry, _i):
        with st.container(border=True):
            st.markdown(f"**{entry.activity_name}**")
            st.write(f"{entry.work_date} | {entry.start_time}-{entry.end_time}")
            st.caption(f"{entry.duration_minutes} min · {entry.worker_name or '—'}")
            if entry.notes:
                st.caption(entry.notes)
            acts = st.columns(2)
            if acts[0].button("Edit", key=f"edit_time_{entry.id}", use_container_width=True):
                if allow_dialogs:
                    clear_all_dialog_flags()
                    flag = _time_flag_key(key_prefix)
                    st.session_state[flag] = entry.id
                    register_armed_dialog(flag)
                else:
                    st.session_state[f"inline_time_{key_prefix}"] = entry.id
                st.rerun()
            if acts[1].button("Delete", key=f"del_time_{entry.id}", use_container_width=True):
                try:
                    time_service.delete_time_entry(entry.id)
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    render_card_grid(entries, _entry_card, suffix=f"time_{key_prefix}")


# --- expense dialogs / management -------------------------------------------
def _expense_form_fields(item_activities, key_prefix, expense=None):
    activity_map = {a.activity_name: a.activity_id for a in item_activities}
    names = list(activity_map.keys())
    default_index = 0
    if expense is not None and expense.activity_name in names:
        default_index = names.index(expense.activity_name)
    name = st.text_input(
        "Expense Name", value=expense.expense_name if expense else "", key=f"exp_name_{key_prefix}"
    )
    activity_name = st.selectbox(
        "Activity", names, index=default_index, key=f"exp_act_{key_prefix}"
    ) if names else None
    cols = st.columns(2)
    rate = cols[0].number_input(
        "Price", value=float(expense.purchase_price) if expense else 0.0,
        key=f"exp_rate_{key_prefix}",
    )
    qty = cols[1].number_input(
        "Qty", min_value=0.0, value=float(expense.quantity) if expense else 1.0,
        key=f"exp_qty_{key_prefix}",
    )
    amount = round(rate * qty, 2)
    st.metric("Amount", _money(amount))
    notes = st.text_area(
        "Notes", value=expense.notes if expense else "", key=f"exp_notes_{key_prefix}"
    )
    return {
        "expense_name": name,
        "activity_id": activity_map.get(activity_name) if activity_name else None,
        "activity_name": activity_name,
        "rate": rate,
        "qty": qty,
        "amount": amount,
        "notes": notes,
    }


def _save_expense(services, order, item, data, expense, flag_key=None):
    expense_service = services["expenses"]
    if not data["expense_name"].strip():
        st.error("Expense name is required")
        return False
    if data["rate"] <= 0:
        st.error("Price must be a positive value")
        return False
    source = _expense_source_for_activity(services, data["activity_id"])
    if expense is not None:
        expense_service.update_expense_details(
            expense.id, expense.expense_date, data["expense_name"], source,
            data["rate"], data["rate"], data["qty"], "", data["notes"],
            activity_id=data["activity_id"], activity_name=data["activity_name"],
        )
    else:
        expense_service.add_expense(
            order_id=order.id, expense_date=date.today(), expense_name=data["expense_name"],
            expense_source=source, purchase_price=data["rate"], selling_price=data["rate"],
            quantity=data["qty"], bill_id=item.item_id, activity_id=data["activity_id"],
            notes=data["notes"],
        )
    if flag_key:
        st.session_state.pop(flag_key, None)
    return True


@st.dialog("Add Expense", on_dismiss=dismiss_armed_dialogs)
def _expense_dialog(services, order_id, item_id, key_prefix):
    flag_key = _expense_flag_key(key_prefix)
    target = st.session_state.get(flag_key)
    order = services["orders"].get_order_detail(order_id)
    item = order.get_item_by_id(item_id) if order else None
    if not item:
        st.error("Item not found")
        return
    expense = None if target in (None, "new") else services["expenses"].get_expense(target)
    data = _expense_form_fields(_item_activities(order, item), f"dlg_{key_prefix}", expense)
    cols = st.columns(2)
    if cols[0].button("Save", type="primary", use_container_width=True):
        try:
            if _save_expense(services, order, item, data, expense, flag_key):
                st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if cols[1].button("Cancel", use_container_width=True):
        st.session_state.pop(flag_key, None)
        st.rerun()


def _render_expense_summary(expenses):
    st.markdown("**Expense summary**")
    totals = {}
    for e in expenses:
        label = e.activity_name or "Unassigned"
        totals[label] = totals.get(label, 0) + e.total_purchase_price
    grand_total = sum(totals.values())
    metrics = [(label, _money(amount)) for label, amount in totals.items()]
    metrics.append(
        ("Total expense", _money(grand_total), f"{len(expenses)} entries")
    )
    metric_grid(metrics, suffix="exp_summary")


def _render_expense_management(services, order, item, key_prefix, allow_dialogs):
    expense_service = services["expenses"]
    expenses = expense_service.get_expenses_by_bill(item.item_id)
    item_activities = _item_activities(order, item)

    if st.button("+ Add Expense", key=f"add_exp_{key_prefix}", type="primary"):
        if allow_dialogs:
            clear_all_dialog_flags()
            _expense_dialog(services, order.id, item.item_id, key_prefix)
        else:
            st.session_state[f"inline_exp_{key_prefix}"] = "new"
            st.rerun()

    if not allow_dialogs and st.session_state.get(f"inline_exp_{key_prefix}"):
        target = st.session_state.get(f"inline_exp_{key_prefix}")
        expense = None if target == "new" else expense_service.get_expense(target)
        with st.container(border=True):
            st.markdown("**Add / Edit Expense**")
            data = _expense_form_fields(item_activities, f"inl_{key_prefix}", expense)
            cols = st.columns(2)
            if cols[0].button("Save", key=f"inl_exp_save_{key_prefix}", type="primary"):
                try:
                    if _save_expense(services, order, item, data, expense, f"inline_exp_{key_prefix}"):
                        st.rerun()
                except Exception as exc:
                    st.error(str(exc))
            if cols[1].button("Cancel", key=f"inl_exp_cancel_{key_prefix}"):
                st.session_state.pop(f"inline_exp_{key_prefix}", None)
                st.rerun()

    _render_expense_summary(expenses)

    st.markdown("**Recorded expenses**")
    if not expenses:
        st.caption("No expenses yet.")
        return

    def _expense_card(expense, _i):
        with st.container(border=True):
            st.markdown(f"**{expense.expense_name}**")
            st.caption(expense.activity_name or "Unassigned")
            st.write(
                f"{_money(expense.purchase_price)} × {expense.quantity:g} = "
                f"**{_money(expense.total_purchase_price)}**"
            )
            if expense.notes:
                st.caption(expense.notes)
            acts = st.columns(2)
            if acts[0].button("Edit", key=f"edit_exp_{expense.id}", use_container_width=True):
                if allow_dialogs:
                    clear_all_dialog_flags()
                    flag = _expense_flag_key(key_prefix)
                    st.session_state[flag] = expense.id
                    register_armed_dialog(flag)
                else:
                    st.session_state[f"inline_exp_{key_prefix}"] = expense.id
                st.rerun()
            if acts[1].button("Delete", key=f"del_exp_{expense.id}", use_container_width=True):
                try:
                    expense_service.delete_expense(expense.id)
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

    render_card_grid(expenses, _expense_card, suffix=f"exp_{key_prefix}")


# --- main panel --------------------------------------------------------------
def customization_item_detail_panel(
    services: dict,
    order: CustomizationOrder,
    item: CustomizationItem,
    invoices: list,
    deliveries: list,
    key_prefix: str,
    *,
    show_header: bool = True,
    show_item_edit: bool = True,
    allow_activity_dialogs: bool = False,
):
    if show_header:
        _render_order_card(order, item, invoices, deliveries)

    if show_item_edit:
        _render_item_edit_inline(services, order, item, key_prefix)
    else:
        _render_item_print(services, order, item, key_prefix)

    section_key = f"section_{key_prefix}"
    section = st.segmented_control(
        "Manage",
        ["Activities", "Time", "Expenses"],
        default="Activities",
        key=section_key,
        label_visibility="collapsed",
    ) or "Activities"

    if section == "Activities":
        _render_activity_management(services, order, item, key_prefix, allow_activity_dialogs)
    elif section == "Time":
        _render_time_management(services, order, item, key_prefix, allow_activity_dialogs)
    else:
        _render_expense_management(services, order, item, key_prefix, allow_activity_dialogs)

    # Popups are opened at panel top level (never nested inside another dialog).
    # Only one dialog may open per run, so this is a strict if/elif chain.
    if allow_activity_dialogs:
        remove_target = st.session_state.get(_remove_flag_key(key_prefix))
        if remove_target:
            _remove_activity_dialog(services, order.id, remove_target, _remove_flag_key(key_prefix))
        elif st.session_state.get(_complete_flag_key(key_prefix)):
            _complete_activity_dialog(services, order.id, key_prefix)
        elif st.session_state.get(_change_status_flag_key(key_prefix)):
            _change_status_dialog(services, order.id, key_prefix)
        elif st.session_state.get(_time_flag_key(key_prefix)):
            item_time_dialog(
                services,
                order.id,
                item.item_id,
                key_prefix,
                _time_flag_key(key_prefix),
            )
        elif st.session_state.get(_expense_flag_key(key_prefix)):
            _expense_dialog(services, order.id, item.item_id, key_prefix)
