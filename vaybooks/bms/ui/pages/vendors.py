from datetime import date

import streamlit as st

from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.ui.dialog_utils import (
    clear_all_dialog_flags,
    make_dismiss_handler,
    register_armed_dialog,
)
from vaybooks.bms.ui.pagination import CARD_PAGE_SIZE, paginate_list, render_page_controls

V_ADD = "vendor_add_dialog"
V_EDIT = "vendor_edit_dialog"
V_VIEW = "vendor_view"
V_PAY = "vendor_pay_dialog"


# --- dialogs -----------------------------------------------------------------
@st.dialog("Add Vendor", width="medium", on_dismiss=make_dismiss_handler(V_ADD))
def _add_vendor_dialog(vendor_service):
    name = st.text_input("Vendor Name", key="v_add_name")
    phone = st.text_input("Phone Number", key="v_add_phone")
    alt_phone = st.text_input("Alternate Phone", key="v_add_alt")
    address = st.text_area("Address", key="v_add_addr")
    notes = st.text_area("Notes", key="v_add_notes")

    cols = st.columns(2)
    if cols[0].button("Create Vendor", type="primary", use_container_width=True):
        if not name or not phone:
            st.error("Name and phone are required")
        else:
            try:
                vendor = vendor_service.create_vendor(
                    name, phone, alt_phone or None, address, notes
                )
                st.session_state.pop(V_ADD, None)
                st.success(f"Created vendor: {vendor.vendor_name}")
                st.rerun()
            except ValidationError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(str(exc))
    if cols[1].button("Cancel", use_container_width=True):
        st.session_state.pop(V_ADD, None)
        st.rerun()


@st.dialog("Edit Vendor", width="medium", on_dismiss=make_dismiss_handler(V_EDIT))
def _edit_vendor_dialog(vendor_service):
    vendor = vendor_service.get_vendor_detail(st.session_state.get(V_EDIT))
    if not vendor:
        st.error("Vendor not found")
        return
    name = st.text_input("Vendor Name", value=vendor.vendor_name, key="v_edit_name")
    phone = st.text_input("Phone Number", value=vendor.phone_number, key="v_edit_phone")
    alt_phone = st.text_input(
        "Alternate Phone", value=vendor.alternate_phone_number or "", key="v_edit_alt"
    )
    address = st.text_area("Address", value=vendor.address or "", key="v_edit_addr")
    notes = st.text_area("Notes", value=vendor.notes or "", key="v_edit_notes")

    cols = st.columns(2)
    if cols[0].button("Save Changes", type="primary", use_container_width=True):
        try:
            vendor_service.update_vendor(
                vendor.id, name, phone, alt_phone or None, address, notes
            )
            st.session_state.pop(V_EDIT, None)
            st.success("Vendor updated")
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
                accounting.create_vendor_payment(
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
def _render_vendor_detail(services, vendor_id: str):
    vendor_service = services["vendors"]
    accounting = services["accounting"]
    vendor = vendor_service.get_vendor_detail(vendor_id)
    if not vendor:
        st.warning("Vendor detail not found")
        return

    if st.button("← Back to vendors", key="vendor_back"):
        st.session_state.pop(V_VIEW, None)
        st.rerun()

    st.subheader("Vendor Detail")
    st.title(vendor.vendor_name)
    with st.container(border=True):
        info = st.columns(3)
        info[0].write(f"**Phone:** {vendor.phone_number}")
        info[1].write(f"**Alt:** {vendor.alternate_phone_number or '—'}")
        vendor_account = accounting.get_vendor_account(vendor.id)
        balance = vendor_account.current_balance if vendor_account else 0.0
        info[2].write(f"**Payable:** ₹{abs(balance):,.0f}")
        if vendor_account:
            st.caption(f"System Account: {vendor_account.account_name}")
        if vendor.address:
            st.caption(f"Address: {vendor.address}")
        if vendor.notes:
            st.caption(f"Notes: {vendor.notes}")

    if st.button("+ Record Payment", type="primary", key="vendor_rec_pay"):
        clear_all_dialog_flags()
        _pay_vendor_dialog(services, vendor.id)

    service_names = {
        s.id: s.service_name
        for s in services["vendor_services"].list_services(active_only=False)
    }
    payments = (
        accounting.list_vendor_payments(vendor_account.id) if vendor_account else []
    )
    associated_services = sorted(
        {
            service_names[v.reference_service_id]
            for v in payments
            if v.reference_service_id and v.reference_service_id in service_names
        }
    )
    st.markdown("**Outsourced service association**")
    if associated_services:
        st.write(", ".join(associated_services))
    else:
        st.caption("No outsourced services linked via payments yet.")

    st.markdown("**Payments**")
    if not payments:
        st.caption("No payments recorded yet.")
    else:
        for v in sorted(payments, key=lambda x: x.voucher_date, reverse=True):
            amount = v.lines[0].debit_amount if v.lines else 0.0
            service_label = service_names.get(v.reference_service_id)
            with st.container(border=True):
                st.markdown(f"**{v.voucher_number}** — ₹{amount:,.0f}")
                if service_label:
                    st.caption(f"Service: {service_label}")
                st.caption(f"{v.voucher_date:%Y-%m-%d} | {v.description or '—'}")
                if st.button("Edit", key=f"edit_vpay_{v.id}"):
                    clear_all_dialog_flags()
                    st.session_state[V_PAY] = v.id
                    register_armed_dialog(V_PAY)
                    st.rerun()

    if st.session_state.get(V_PAY):
        _pay_vendor_dialog(services, vendor.id)


def _render_vendor_list(services):
    vendor_service = services["vendors"]

    header = st.columns([4, 1])
    with header[0]:
        query = st.text_input(
            "Search by name or phone", key="vendor_search",
            placeholder="Search vendors...",
        )
    with header[1]:
        if st.button("Add Vendor", type="primary", use_container_width=True):
            clear_all_dialog_flags()
            _add_vendor_dialog(vendor_service)

    vendors = vendor_service.search_vendors(query)
    st.caption(f"Vendor list displays {len(vendors)} records")
    if not vendors:
        st.info("No vendors found.")
    else:
        page_vendors, page, total_pages = paginate_list(
            vendors,
            page_key="vendor_page",
            page_size=CARD_PAGE_SIZE,
            filter_key="vendor_search",
            filter_value=query,
        )
        cols = st.columns(3)
        for i, vendor in enumerate(page_vendors):
            with cols[i % 3].container(border=True):
                st.markdown(f"**{vendor.vendor_name}**")
                st.write(vendor.phone_number)
                btns = st.columns(2)
                if btns[0].button("Edit", key=f"v_edit_{vendor.id}", use_container_width=True):
                    clear_all_dialog_flags()
                    st.session_state[V_EDIT] = vendor.id
                    register_armed_dialog(V_EDIT)
                    st.rerun()
                if btns[1].button("Payments", key=f"v_pay_{vendor.id}", use_container_width=True):
                    st.session_state[V_VIEW] = str(vendor.id)
                    st.rerun()
        render_page_controls(
            page, total_pages, len(vendors),
            page_key="vendor_page", prev_key="vendor_prev", next_key="vendor_next",
            label="vendors",
        )

    if st.session_state.get(V_EDIT):
        _edit_vendor_dialog(vendor_service)


def render(services: dict):
    if st.session_state.get(V_VIEW):
        _render_vendor_detail(services, st.session_state[V_VIEW])
        return
    st.title("Vendors")
    _render_vendor_list(services)
