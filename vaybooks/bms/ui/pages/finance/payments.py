"""Vendor Payments route (vendor payments + salaries)."""

import streamlit as st

from vaybooks.bms.domain.shared.enums import VoucherType
from vaybooks.bms.ui.components.list_view import render_list
from vaybooks.bms.ui.components.voucher_card import VoucherEditAction, voucher_cards
from vaybooks.bms.ui.list_schemas import PAYMENTS
from vaybooks.bms.ui.pages import accounts as acc


def _load(services, filters, sort):
    try:
        accounting = services["accounting"]
        payments = accounting.list_vouchers_by_type(VoucherType.VENDOR_PAYMENT)
        salaries = accounting.list_vouchers_by_type(VoucherType.SALARY_PAYMENT)
        return payments + salaries
    except Exception:
        return []


def _cards(page_vouchers, services):
    service_names = {
        s.id: s.service_name
        for s in services["vendor_services"].list_services(active_only=False)
    }

    def _builder(v):
        is_salary = v.voucher_type == VoucherType.SALARY_PAYMENT
        flag_key = acc.SAL if is_salary else acc.PAY
        edit_prefix = "edit_sal" if is_salary else "edit_pay"
        service_label = (
            None if is_salary else service_names.get(v.reference_service_id)
        )
        return {
            "service_label": service_label,
            "edit": VoucherEditAction(
                flag_key=flag_key,
                button_key=f"{edit_prefix}_{v.id}",
            ),
        }

    voucher_cards(page_vouchers, suffix="payments", card_builder=_builder)


def render(services: dict):
    accounting_service = services["accounting"]
    actions = st.columns(2)
    if actions[0].button(
        "+ Record Vendor Payment",
        type="primary",
        key="btn_rec_pay",
        use_container_width=True,
    ):
        acc._clear_other_payment_dialog_flags(acc.PAY)
        acc._payment_dialog(services)
    if actions[1].button(
        "+ Record Salary",
        type="primary",
        key="btn_rec_sal",
        use_container_width=True,
    ):
        acc._clear_other_payment_dialog_flags(acc.SAL)
        acc._salary_dialog(accounting_service)

    render_list(
        PAYMENTS,
        services=services,
        load_fn=_load,
        card_renderer=_cards,
        count_label="payments",
        empty_text="No payments recorded yet.",
    )
    acc.open_pending_dialogs(services)
