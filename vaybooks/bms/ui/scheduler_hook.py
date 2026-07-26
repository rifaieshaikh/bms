"""First-login trigger for the background scheduler.

Runs once per Streamlit session, immediately after authentication is
established (explicit sign-in or cookie restore). Everything it starts is
handed to a daemon thread, so the render path is never blocked.
"""

from __future__ import annotations

import logging

import streamlit as st

_SESSION_FLAG = "_scheduler_login_checked"

logger = logging.getLogger("vaybooks.bms.schedulers")


def maybe_start_schedulers(services: dict) -> None:
    if st.session_state.get(_SESSION_FLAG):
        return
    st.session_state[_SESSION_FLAG] = True

    service = services.get("schedulers")
    if service is None:
        return
    try:
        from vaybooks.bms.ui.auth.session import current_user_id

        actor_id = current_user_id()
    except Exception:
        actor_id = ""
    try:
        service.maybe_start_due_jobs(actor_id=actor_id)
    except Exception:
        # A scheduler problem must never keep a user out of the application.
        logger.exception("Scheduler login trigger failed")
