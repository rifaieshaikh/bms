from datetime import date

import streamlit as st

from vaybooks.bms.domain.shared.exceptions import (
    DuplicateVendorError,
    ValidationError,
)
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.common.list_view import render_list
from vaybooks.bms.ui.components.parties.vendor_form import render_vendor_form
from vaybooks.bms.ui.dialog_utils import (
    clear_all_dialog_flags,
    make_dismiss_handler,
    register_armed_dialog,
)
from vaybooks.bms.ui.keyboard.dialog_actions import consume_submit, open_dialog
from vaybooks.bms.ui.keyboard.wired import mark_wired
from vaybooks.bms.ui.styles import render_card_grid
from vaybooks.bms.ui.list_schemas import VENDORS

V_ADD = "vendor_add_dialog"
V_EDIT = "vendor_edit_dialog"
V_PAY = "vendor_pay_dialog"
V_DUP_VENDOR_ID = "vendor_duplicate_existing_id"
SUBMIT_ADD = "submit_vendor_add"
SUBMIT_EDIT = "submit_vendor_edit"


def _open_add_vendor() -> None:
    clear_all_dialog_flags()
    st.session_state.pop(V_DUP_VENDOR_ID, None)
    open_dialog(V_ADD, submit_key=SUBMIT_ADD, clear_others=False)
    mark_wired("vendors.add", "list.primary", "dialog.save")


def _render_duplicate_vendor_warning(existing_vendor_id: str, vendor_service) -> None:
    existing = vendor_service.get_vendor_detail(existing_vendor_id)
    label = existing.vendor_name if existing else "existing vendor"
    st.warning(f"A vendor with this phone or GSTIN already exists: **{label}**")
    if st.button("Open existing vendor", key="vendor_open_existing", type="primary"):
        st.session_state.pop(V_ADD, None)
        st.session_state.pop(V_DUP_VENDOR_ID, None)
        navigation.go_to_detail("vendor_detail", existing_vendor_id)
        st.rerun()


# --- dialogs -----------------------------------------------------------------
@st.dialog("Add Vendor", width="large", on_dismiss=make_dismiss_handler(V_ADD))
def _add_vendor_dialog(vendor_service):
    dup_id = st.session_state.get(V_DUP_VENDOR_ID)
    if dup_id:
        _render_duplicate_vendor_warning(dup_id, vendor_service)

    vendor_input = render_vendor_form("v_add")

    cols = st.columns(2)
    do_create = cols[0].button(
        "Create Vendor", type="primary", use_container_width=True
    ) or consume_submit(SUBMIT_ADD)
    if do_create:
        try:
            vendor = vendor_service.create_vendor(vendor_input)
            st.session_state.pop(V_ADD, None)
            st.session_state.pop(V_DUP_VENDOR_ID, None)
            st.success(f"Created vendor: {vendor.vendor_name}")
            st.rerun()
        except DuplicateVendorError as exc:
            st.session_state[V_DUP_VENDOR_ID] = exc.existing_vendor_id
            st.rerun()
        except ValidationError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(str(exc))
    if cols[1].button("Cancel", use_container_width=True):
        st.session_state.pop(V_ADD, None)
        st.session_state.pop(V_DUP_VENDOR_ID, None)
        st.rerun()


@st.dialog("Edit Vendor", width="large", on_dismiss=make_dismiss_handler(V_EDIT))
def _edit_vendor_dialog(vendor_service):
    vendor = vendor_service.get_vendor_detail(st.session_state.get(V_EDIT))
    if not vendor:
        st.error("Vendor not found")
        return

    vendor_input = render_vendor_form("v_edit", vendor=vendor)

    cols = st.columns(2)
    do_save = cols[0].button(
        "Save Changes", type="primary", use_container_width=True
    ) or consume_submit(SUBMIT_EDIT)
    if do_save:
        try:
            vendor_service.update_vendor(vendor.id, vendor_input)
            st.session_state.pop(V_EDIT, None)
            st.success("Vendor updated")
            st.rerun()
        except DuplicateVendorError as exc:
            st.warning(str(exc))
            if st.button("Open existing vendor", key="vendor_edit_open_existing"):
                st.session_state.pop(V_EDIT, None)
                navigation.go_to_detail("vendor_detail", exc.existing_vendor_id)
                st.rerun()
        except ValidationError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(str(exc))
    if cols[1].button("Cancel", use_container_width=True):
        st.session_state.pop(V_EDIT, None)
        st.rerun()


@st.dialog("Pay Vendor", width="medium", on_dismiss=make_dismiss_handler(V_PAY))
def _pay_vendor_dialog(services, vendor_id: str):
    accounting = services["accounting"]
    service_config = services["vendor_services"]
    vendor_account = accounting.get_vendor_account(vendor_id)
    if not vendor_account:
        st.error("Vendor account not found.")
        if st.button("Close"):
            st.session_state.pop(V_PAY, None)
            st.rerun()
        return

    store_accounts = accounting.get_store_accounts()
    service_list = service_config.list_services(active_only=True)
    if not store_accounts or not service_list:
        st.error(
            "Need at least one store account and one configured service "
            "(see Service Configuration)."
        )
        if st.button("Close"):
            st.session_state.pop(V_PAY, None)
            st.rerun()
        return

    target = st.session_state.get(V_PAY)
    voucher = None if target in (None, "new") else accounting.get_voucher(target)
    # Vendor payment lines: [expense Dr, vendor Cr, vendor Dr, paying Cr].
    existing_pay = voucher.lines[3].account_id if voucher else None
    existing_amt = voucher.lines[0].debit_amount if voucher else 0.0
    existing_service = voucher.reference_service_id if voucher else None

    st.caption(f"Vendor account: **{vendor_account.account_name}**")

    svc_opts = {s.service_name: s for s in service_list}
    pay_opts = {a.account_name: a.id for a in store_accounts}
    svc_names = list(svc_opts.keys())
    pay_names = list(pay_opts.keys())

    svc_default = 0
    if existing_service and existing_service in {s.id for s in service_list}:
        svc_default = next(
            i for i, s in enumerate(service_list) if s.id == existing_service
        )
    pay_default = (
        pay_names.index(next(k for k, v in pay_opts.items() if v == existing_pay))
        if voucher and existing_pay in pay_opts.values()
        else 0
    )

    service_name = st.selectbox("Service / Material", svc_names, index=svc_default)
    paying_name = st.selectbox("Paying Account (Store)", pay_names, index=pay_default)
    amount = st.number_input("Amount", min_value=0.0, value=float(existing_amt))
    v_date = st.date_input("Date", value=date.today())
    desc = st.text_input("Description", value=voucher.description if voucher else "")

    selected_service = svc_opts[service_name]

    cols = st.columns(2)
    if cols[0].button("Save", type="primary", use_container_width=True):
        try:
            if voucher:
                accounting.update_vendor_payment(
                    voucher.id, vendor_account.id, selected_service.expense_account_id,
                    pay_opts[paying_name], amount, desc, v_date,
                    service_id=selected_service.id,
                )
            else:
                services["purchases"].merge_vendor_payment_into_purchase(
                    vendor_account.id, selected_service.expense_account_id,
                    pay_opts[paying_name], amount, desc, v_date,
                    service_id=selected_service.id,
                )
            st.session_state.pop(V_PAY, None)
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if cols[1].button("Cancel", use_container_width=True):
        st.session_state.pop(V_PAY, None)
        st.rerun()


# --- views -------------------------------------------------------------------
def _load_vendors(services, filters, sort):
    vendors = services["vendors"].list_all_vendors()
    accounting = services["accounting"]
    for vendor in vendors:
        try:
            account = accounting.get_vendor_account(vendor.id)
        except Exception:
            account = None
        setattr(vendor, "current_balance", account.current_balance if account else 0.0)
    return vendors


def _render_cards(page_vendors, services):
    def _render(vendor, _i):
        with st.container(border=True):
            st.markdown(f"**{vendor.vendor_name}**")
            st.write(vendor.phone_number)
            if vendor.gstin:
                st.caption(f"GSTIN: {vendor.gstin}")
            balance = getattr(vendor, "current_balance", 0.0)
            st.caption(f"Payable: ₹{abs(balance):,.0f}")
            btns = st.columns(2)
            if btns[0].button("Edit", key=f"v_edit_{vendor.id}",
                              use_container_width=True):
                clear_all_dialog_flags()
                open_dialog(V_EDIT, submit_key=SUBMIT_EDIT, value=vendor.id, clear_others=False)
                st.rerun()
            if btns[1].button("View", key=f"v_view_{vendor.id}",
                              use_container_width=True):
                navigation.go_to_detail("vendor_detail", vendor.id)

    render_card_grid(page_vendors, _render, suffix="vendors")


def render(services: dict):
    mark_wired("vendors.add", "list.primary", "list.filters.open", "list.sort.open")
    bar = render_list(
        VENDORS,
        services=services,
        load_fn=_load_vendors,
        card_renderer=_render_cards,
        primary_label="Add Vendor",
        primary_key="vendors_add_btn",
        count_label="vendors",
        empty_text="No vendors found.",
        page_key_nav="vendors_list",
    )
    if bar["primary_clicked"]:
        _open_add_vendor()
    if bar.get("view_nth"):
        navigation.go_to_detail("vendor_detail", bar["view_nth"])
    if bar.get("edit_nth"):
        clear_all_dialog_flags()
        open_dialog(
            V_EDIT, submit_key=SUBMIT_EDIT, value=bar["edit_nth"], clear_others=False
        )
        st.rerun()
    if st.session_state.get(V_ADD):
        from vaybooks.bms.ui.keyboard.context import get_submit_map

        get_submit_map().setdefault(V_ADD, SUBMIT_ADD)
        register_armed_dialog(V_ADD)
        _add_vendor_dialog(services["vendors"])
    if st.session_state.get(V_EDIT):
        from vaybooks.bms.ui.keyboard.context import get_submit_map

        get_submit_map().setdefault(V_EDIT, SUBMIT_EDIT)
        register_armed_dialog(V_EDIT)
        _edit_vendor_dialog(services["vendors"])


# Re-export for callers that still import from list.
def render_vendor_detail(services: dict):
    from vaybooks.bms.ui.pages.parties.vendors.detail import render as render_detail

    render_detail(services)

