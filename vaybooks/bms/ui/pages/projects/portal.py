"""Read-only customer portal confirmation (Wave 8)."""

from __future__ import annotations

import streamlit as st


def render(services: dict) -> None:
    st.title("Project portal")
    portal_svc = services.get("project_portal")
    projects_svc = services.get("projects")
    params = st.query_params
    raw = params.get("token")
    if isinstance(raw, list):
        raw = raw[0] if raw else None
    token = st.text_input("Access token", value=str(raw or ""), key="portal_token")

    if not token:
        st.info("Enter a portal token (or open with `?token=…`).")
        return
    if portal_svc is None:
        st.warning("Portal service is not configured.")
        return

    try:
        portal = portal_svc.validate_portal_token(token)
    except Exception as exc:
        st.error(str(exc))
        return

    project = None
    if projects_svc:
        try:
            project = projects_svc.get_project(portal.project_id)
        except Exception:
            project = None

    st.success("Token valid — read-only confirmation")
    st.write(f"**Scope:** {portal.scope}")
    if portal.expires_at:
        st.caption(f"Expires {portal.expires_at}")
    if project:
        st.write(f"**Project:** {project.project_number} — {project.name}")
        st.write(f"**Customer:** {project.customer_name}")
        st.caption(
            f"Contract value: {float(project.contract_value or 0):,.2f} "
            f"{getattr(project, 'currency_code', 'INR') or 'INR'}"
        )
    else:
        st.write(f"**Project id:** {portal.project_id}")

    if portal.scope == "quote":
        st.caption("Quote confirmation view (read-only stub).")
    elif portal.scope == "measurement":
        st.caption("Measurement certification view (read-only stub).")
    else:
        st.caption("Bill / RA confirmation view (read-only stub).")
