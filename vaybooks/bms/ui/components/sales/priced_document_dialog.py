"""Create and edit dialogs for estimates and quotations."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.ui.components.sales.priced_document_form import (
    render_priced_document_form,
)
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler


def _dialog_key(document_type: str) -> str:
    return f"{document_type}_document_dialog"


def _form_prefix(document_type: str) -> str:
    return f"{document_type}_document_form"


def arm_priced_document_dialog(
    document_type: str, *, document_id: str | None = None
) -> None:
    dialog_key = _dialog_key(document_type)
    form_prefix = _form_prefix(document_type)
    for key in list(st.session_state.keys()):
        if key == dialog_key or key.startswith(form_prefix):
            st.session_state.pop(key, None)
    st.session_state[dialog_key] = document_id or "new"


def _clear(document_type: str) -> None:
    dialog_key = _dialog_key(document_type)
    form_prefix = _form_prefix(document_type)
    for key in list(st.session_state.keys()):
        if key == dialog_key or key.startswith(form_prefix):
            st.session_state.pop(key, None)


def _render_dialog(services: dict, document_type: str) -> None:
    document_id = st.session_state.get(_dialog_key(document_type))
    if not document_id:
        return

    existing = None
    if document_id != "new":
        getter = (
            services["sales"].get_estimate
            if document_type == "estimate"
            else services["sales"].get_quotation
        )
        existing = getter(document_id)
        if existing is None:
            st.error("Document not found")
            return

    try:
        if render_priced_document_form(
            services,
            document_type=document_type,
            existing=existing,
            key_prefix=_form_prefix(document_type),
        ):
            _clear(document_type)
            st.rerun()
    except Exception as exc:
        st.error(str(exc))


@st.dialog(
    "Create Estimate",
    width="large",
    on_dismiss=make_dismiss_handler("estimate_document_dialog"),
)
def _create_estimate_dialog(services: dict) -> None:
    _render_dialog(services, "estimate")


@st.dialog(
    "Edit Estimate",
    width="large",
    on_dismiss=make_dismiss_handler("estimate_document_dialog"),
)
def _edit_estimate_dialog(services: dict) -> None:
    _render_dialog(services, "estimate")


@st.dialog(
    "Create Quotation",
    width="large",
    on_dismiss=make_dismiss_handler("quotation_document_dialog"),
)
def _create_quotation_dialog(services: dict) -> None:
    _render_dialog(services, "quotation")


@st.dialog(
    "Edit Quotation",
    width="large",
    on_dismiss=make_dismiss_handler("quotation_document_dialog"),
)
def _edit_quotation_dialog(services: dict) -> None:
    _render_dialog(services, "quotation")


def open_priced_document_dialog_if_armed(
    services: dict, document_type: str
) -> None:
    document_id = st.session_state.get(_dialog_key(document_type))
    if not document_id:
        return
    if document_type == "estimate":
        dialog = (
            _create_estimate_dialog
            if document_id == "new"
            else _edit_estimate_dialog
        )
    else:
        dialog = (
            _create_quotation_dialog
            if document_id == "new"
            else _edit_quotation_dialog
        )
    dialog(services)
