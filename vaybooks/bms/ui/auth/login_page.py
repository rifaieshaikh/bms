"""Full-page split-screen sign-in screen (replaces the old sign-in dialog).

Streamlit widgets can't be nested inside arbitrary HTML, so the split layout
is built the same way the rest of this app builds custom chrome (see
``components/shared/topbar.py`` / ``dashboard_card.py``): plain
``st.container(key=...)`` + ``st.columns`` scaffolding, styled from the
outside via the ``st-key-*`` selectors in ``theme.css``'s "Login page"
section. Only the banner image is raw HTML, since it needs ``object-fit``
and absolute positioning that ``st.image`` doesn't expose.
"""

from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.ui.auth.session import login_user
from vaybooks.bms.ui.components.shared.forms import checkbox_field, password_field, text_field

__all__ = ["render_login_page"]

_ASSETS_DIR = Path(__file__).resolve().parents[4] / "assets"
_BANNER_PATH = _ASSETS_DIR / "images" / "login-banner-placeholder.jpg"
_LOGO_PATH = _ASSETS_DIR / "logo.svg"

_HIDE_CHROME_CSS = """
<style>
section[data-testid="stSidebar"] { display: none !important; }
</style>
"""


@st.cache_data(show_spinner=False)
def _file_data_uri(path: Path, mime: str) -> str:
    if not path.exists():
        return ""
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def _banner_data_uri() -> str:
    return _file_data_uri(_BANNER_PATH, "image/jpeg")


def _logo_data_uri() -> str:
    return _file_data_uri(_LOGO_PATH, "image/svg+xml")


def _render_banner() -> None:
    uri = _banner_data_uri()
    if not uri:
        return
    st.markdown(
        f'<img class="z-login-banner-img" src="{uri}" alt="" />',
        unsafe_allow_html=True,
    )


def _render_form(services: dict) -> None:
    logo_uri = _logo_data_uri()
    logo_html = f'<img src="{logo_uri}" alt="" />' if logo_uri else ""
    st.markdown(
        f'<div class="z-login-logo">{logo_html}</div>'
        '<h1 class="z-login-title">Welcome back!</h1>'
        '<p class="z-login-subtitle">Enter your credentials to continue.</p>',
        unsafe_allow_html=True,
    )

    with st.form("zlogin_form", border=False):
        username = text_field(
            "Username", key="zlogin_username", placeholder="Enter your username"
        )
        password = password_field(
            "Password", key="zlogin_password", placeholder="Enter password"
        )
        remember_col, forgot_col = st.columns([1, 1])
        with remember_col:
            remember = checkbox_field("Remember me", value=True, key="zlogin_remember")
        with forgot_col:
            st.markdown(
                '<div class="z-login-forgot"><span>Forgot your password?</span></div>',
                unsafe_allow_html=True,
            )
        submitted = st.form_submit_button(
            "Log In", type="primary", use_container_width=True
        )

    if submitted:
        audit = services.get("access_audit")
        with st.spinner("Signing in..."):
            try:
                user = services["users"].authenticate(username, password)
                login_user(user, services, persist=remember)
                if audit:
                    audit.record(
                        "login",
                        actor_id=user.id,
                        actor_name=user.display_name or user.username,
                    )
            except ValidationError as exc:
                if audit:
                    audit.record(
                        "login_failed",
                        actor_name=(username or "").strip(),
                        detail={"username": (username or "").strip()},
                    )
                st.error(str(exc))
                return
            except Exception as exc:
                st.error(str(exc))
                return
        st.rerun()


def render_login_page(services: dict) -> None:
    """Render the full-screen split login page. Call in place of the sign-in dialog."""
    st.markdown(_HIDE_CHROME_CSS, unsafe_allow_html=True)
    with st.container(key="zlogin_page"):
        with st.container(key="zlogin_card"):
            left, right = st.columns([2, 3], gap="small")
            with left:
                with st.container(key="zlogin_form_col"):
                    _render_form(services)
            with right:
                with st.container(key="zlogin_banner"):
                    _render_banner()
