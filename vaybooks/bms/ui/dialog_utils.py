"""Shared helpers for Streamlit dialog open/dismiss session-state management.

Streamlit does not run Cancel handlers when a dialog is closed via ✕, Escape,
or backdrop click. Use ``on_dismiss`` on ``@st.dialog`` plus these helpers so
stale flags do not reopen dialogs on the next rerun.

Patterns:
- **New** dialogs: call the dialog function directly from the button (no flag).
- **Edit** dialogs: set a session flag, dispatch at page bottom, register the
  flag with ``register_armed_dialog``, and use ``dismiss_armed_dialogs`` as
  ``on_dismiss`` (or ``make_dismiss_handler`` for static keys).
"""

from __future__ import annotations

from typing import Callable

import streamlit as st

# Session keys whose presence means "reopen this dialog on rerun".
DIALOG_FLAG_PREFIXES = (
    "add_activity_flag_",
    "remove_activity_flag_",
    "time_dialog_",
    "expense_dialog_",
    "complete_flow_",
    "change_status_flow_",
    "inv_dialog_",
    "del_dialog_",
    "rcpt_dialog_",
    "pay_dialog_",
    "refund_dialog_",
    "cancel_dialog_",
    "acc_create_dialog",
    "acc_edit_dialog",
    "acc_ledger_dialog",
    "acc_receipt_dialog",
    "acc_payment_dialog",
    "acc_salary_dialog",
    "acc_cust_inv_dialog",
    "acc_sales_inv_dialog",
    "acc_journal_dialog",
    "vendor_add_dialog",
    "vendor_edit_dialog",
    "vendor_pay_dialog",
    "customer_add_dialog",
    "customer_edit_dialog",
    "inv_category_add_dialog",
    "inv_category_edit_dialog",
    "inv_product_add_dialog",
    "inv_product_edit_dialog",
    "estimate_document_dialog",
    "quotation_document_dialog",
    "so_edit_dialog",
    "so_invoice_dialog",
    "dn_edit_dialog",
    "dn_invoice_dialog",
    "invoice_edit_dialog",
    "sales_return_dialog",
    "sales_return_edit_dialog",
    "ws_add_item_dialog",
    "ws_edit_item_dialog",
    "ws_remove_item_dialog",
    "ws_add_measurement_dialog",
    "ws_edit_measurement_dialog",
    "ws_remove_measurement_dialog",
    "prj_template_add_dialog",
    "prj_template_edit_dialog",
    "prj_template_remove_dialog",
    "prj_boq_add_dialog",
    "prj_boq_edit_dialog",
    "prj_boq_del_dialog",
    "prj_boq_import_dialog",
    "prj_budget_add_dialog",
    "prj_budget_rev_dialog",
    "prj_enquiry_create_dialog",
    "prj_enquiry_assess_dialog",
    "prj_boq_rate_dialog",
    "prj_mr_add_dialog",
    "prj_stock_add_dialog",
    "prj_qi_add_dialog",
    "prj_dpr_add_dialog",
    "list_filters_dialog_",
    "list_sort_dialog_",
)

_ARMED_FLAGS = "_armed_dialog_flags"


def clear_dialog_flags(*keys: str) -> None:
    for key in keys:
        st.session_state.pop(key, None)


def clear_all_dialog_flags() -> None:
    """Drop every dialog-open flag (used before opening a different dialog)."""
    for key in list(st.session_state.keys()):
        if key.startswith(DIALOG_FLAG_PREFIXES):
            st.session_state.pop(key, None)
    st.session_state.pop(_ARMED_FLAGS, None)


def register_armed_dialog(*flag_keys: str) -> None:
    """Remember which flags an edit-style dialog owns (cleared on dismiss)."""
    st.session_state[_ARMED_FLAGS] = list(flag_keys)


def dismiss_armed_dialogs() -> None:
    """``on_dismiss`` callback for dialogs using dynamic per-entity flag keys."""
    for key in st.session_state.pop(_ARMED_FLAGS, []) or []:
        st.session_state.pop(key, None)


def make_dismiss_handler(*flag_keys: str) -> Callable[[], None]:
    """``on_dismiss`` callback for dialogs with fixed session-flag keys."""

    def _on_dismiss() -> None:
        clear_dialog_flags(*flag_keys)
        dismiss_armed_dialogs()

    return _on_dismiss
