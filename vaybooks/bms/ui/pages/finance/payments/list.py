"""Salary, commission, and delivery-charge payments route."""

import streamlit as st

from vaybooks.bms.domain.shared.enums import VoucherType
from vaybooks.bms.ui.components.common.list_view import render_list
from vaybooks.bms.ui.components.common.voucher_card import VoucherEditAction, voucher_cards
from vaybooks.bms.ui.components.sales.delivery_charge_payment import (
    render_pay_delivery_charges,
)
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler, register_armed_dialog
from vaybooks.bms.ui.keyboard.actions import consume_action
from vaybooks.bms.ui.keyboard.dialog_actions import open_dialog
from vaybooks.bms.ui.keyboard.wired import mark_wired
from vaybooks.bms.ui.list_schemas import PAYMENTS
from vaybooks.bms.ui.pages.finance.accounts import list as acc

DC_PAY = "delivery_charge_pay_dialog"


def _load_payments(services, filters, sort):
    try:
        from vaybooks.bms.domain.identity.location_access import location_id_mongo_filter
        from vaybooks.bms.ui.auth.session import working_location_list_context

        working, accessible = working_location_list_context(services)
        filt = location_id_mongo_filter(working, accessible)
        accounting = services["accounting"]
        salaries = accounting.list_vouchers_by_type(
            VoucherType.SALARY_PAYMENT, location_filter=filt
        )
        commissions = accounting.list_vouchers_by_type(
            VoucherType.COMMISSION_PAYMENT, location_filter=filt
        )
        journals = [
            v
            for v in accounting.list_vouchers_by_type(
                VoucherType.JOURNAL, location_filter=filt
            )
            if "delivery" in (v.description or "").lower()
            and "partner payment" in (v.description or "").lower()
        ]
        return sorted(
            list(salaries) + list(commissions) + list(journals),
            key=lambda v: v.voucher_date,
            reverse=True,
        )
    except Exception:
        return []


def _cards(page_vouchers, services):
    def _builder(v):
        if v.voucher_type == VoucherType.COMMISSION_PAYMENT:
            return {
                "service_label": "Commission",
                "edit": VoucherEditAction(
                    flag_key=acc.COMM,
                    button_key=f"edit_comm_{v.id}",
                ),
            }
        if v.voucher_type == VoucherType.JOURNAL:
            return {"service_label": "Delivery charge"}
        return {
            "service_label": "Salary",
            "edit": VoucherEditAction(
                flag_key=acc.SAL,
                button_key=f"edit_sal_{v.id}",
            ),
        }

    voucher_cards(page_vouchers, suffix="payments", card_builder=_builder)


@st.dialog(
    "Pay Delivery Charge",
    width="large",
    on_dismiss=make_dismiss_handler(DC_PAY),
)
def _delivery_charge_pay_dialog(services: dict) -> None:
    if not st.session_state.get(DC_PAY):
        return
    register_armed_dialog(DC_PAY)
    render_pay_delivery_charges(services, partner_id=None, key_prefix="fin_dc_pay")


def render(services: dict):
    accounting_service = services["accounting"]
    mark_wired("list.primary", "finance.salary.add")
    st.info(
        "Vendor purchases are under **Purchases → Purchase Bills**. "
        "Use this page for salary, commission, and delivery-partner charge payments."
    )
    cols = st.columns(3)
    if cols[0].button(
        "+ Record Salary",
        type="primary",
        key="btn_rec_sal",
        width="stretch",
    ) or consume_action("list.primary"):
        acc._clear_other_payment_dialog_flags(acc.SAL)
        acc._salary_dialog(accounting_service)
    if cols[1].button(
        "+ Record Commission",
        type="secondary",
        key="btn_rec_comm",
        width="stretch",
    ):
        acc._clear_other_payment_dialog_flags(acc.COMM)
        st.session_state[acc.COMM] = "new"
    if cols[2].button(
        "+ Pay Delivery Charge",
        type="secondary",
        key="btn_rec_dc",
        width="stretch",
    ):
        open_dialog(DC_PAY, value="new", clear_others=True)
        st.rerun()

    render_list(
        PAYMENTS,
        services=services,
        load_fn=_load_payments,
        card_renderer=_cards,
        count_label="payments",
        empty_text="No salary, commission, or delivery-charge payments yet.",
        page_key_nav="payments_list",
    )
    acc.open_pending_dialogs(services)
    if st.session_state.get(DC_PAY):
        _delivery_charge_pay_dialog(services)
