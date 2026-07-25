"""Sign-in dialog (popup) replacing the dedicated login page."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.ui.auth.session import login_user, logout_user
from vaybooks.bms.ui.dialog_utils import make_dismiss_handler

SIGNIN_FLAG = "signin_dialog_open"
SIGNIN_PROMPTED = "signin_dialog_prompted"


@st.dialog("Sign in", on_dismiss=make_dismiss_handler(SIGNIN_FLAG))
def sign_in_dialog(services: dict) -> None:
    st.caption("VayBooks — enter your username and password.")
    with st.form("signin_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in", type="primary")
    if submitted:
        audit = services.get("access_audit")
        try:
            user = services["users"].authenticate(username, password)
            login_user(user, services)
            if audit:
                audit.record(
                    "login",
                    actor_id=user.id,
                    actor_name=user.display_name or user.username,
                )
            st.session_state.pop(SIGNIN_FLAG, None)
            st.rerun()
        except ValidationError as exc:
            if audit:
                audit.record(
                    "login_failed",
                    actor_name=(username or "").strip(),
                    detail={"username": (username or "").strip()},
                )
            st.error(str(exc))
        except Exception as exc:
            st.error(str(exc))


def open_sign_in_dialog_if_needed(services: dict) -> None:
    """Auto-open on first unauthenticated load; reopen only via the button."""
    if SIGNIN_PROMPTED not in st.session_state:
        st.session_state[SIGNIN_PROMPTED] = True
        st.session_state[SIGNIN_FLAG] = True
    if st.session_state.get(SIGNIN_FLAG):
        sign_in_dialog(services)


@st.dialog("Sign out")
def sign_out_dialog(services: dict) -> None:
    """Confirm sign-out and clear both memory and persistent login state."""
    st.write("Are you sure you want to sign out of VayBooks?")
    confirm, cancel = st.columns(2)
    if confirm.button(
        "Sign out",
        type="primary",
        icon=":material/logout:",
        use_container_width=True,
    ):
        audit = services.get("access_audit")
        if audit:
            try:
                audit.record("logout")
            except Exception:
                pass
        logout_user()
        st.session_state.pop(SIGNIN_PROMPTED, None)
        st.rerun()
    if cancel.button("Stay signed in", use_container_width=True):
        st.rerun()
