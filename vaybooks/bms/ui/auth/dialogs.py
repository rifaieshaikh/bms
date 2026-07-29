"""Sign-out confirmation dialog.

The sign-in flow is a dedicated full-page screen, not a dialog — see
``vaybooks.bms.ui.auth.login_page``.
"""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.ui.auth.session import logout_user


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
        st.rerun()
    if cancel.button("Stay signed in", use_container_width=True):
        st.rerun()
