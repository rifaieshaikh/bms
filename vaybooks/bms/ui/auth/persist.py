"""Persistent login cookie (survives browser refresh for AUTH_TTL_DAYS)."""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time
from typing import Optional

import streamlit as st
import streamlit.components.v1 as components

logger = logging.getLogger(__name__)

COOKIE_NAME = "vaybooks_auth"
AUTH_TTL_DAYS = 1
AUTH_TTL_SECONDS = AUTH_TTL_DAYS * 24 * 60 * 60


def _signing_secret() -> bytes:
    """Resolve an HMAC secret from secrets/env, else a stable local fallback."""
    raw = ""
    try:
        raw = str(st.secrets.get("AUTH_SESSION_SECRET") or "").strip()
    except Exception:
        raw = ""
    if not raw:
        raw = (os.environ.get("AUTH_SESSION_SECRET") or "").strip()
    if not raw:
        # Stable per-deployment fallback so refreshes work without extra config.
        try:
            uri = str(st.secrets.get("MONGODB_URI") or "")
        except Exception:
            uri = os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URI") or ""
        raw = "vaybooks-auth|" + (uri or "local-dev")
    return hashlib.sha256(raw.encode("utf-8")).digest()


def issue_token(user_id: str, *, ttl_seconds: int = AUTH_TTL_SECONDS) -> str:
    """Return ``user_id.expiry.signature`` for cookie storage."""
    uid = (user_id or "").strip()
    if not uid:
        raise ValueError("user_id required")
    expiry = int(time.time()) + max(60, int(ttl_seconds))
    payload = f"{uid}.{expiry}"
    sig = hmac.new(_signing_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def verify_token(token: str) -> Optional[str]:
    """Return user_id if the token is valid and not expired, else None."""
    token = (token or "").strip()
    if not token:
        return None
    parts = token.split(".")
    if len(parts) != 3:
        return None
    uid, expiry_s, sig = parts
    if not uid or not expiry_s or not sig:
        return None
    try:
        expiry = int(expiry_s)
    except ValueError:
        return None
    if expiry < int(time.time()):
        return None
    payload = f"{uid}.{expiry}"
    expected = hmac.new(
        _signing_secret(), payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return None
    return uid


def read_auth_cookie() -> str:
    """Read the auth cookie sent with the current browser request."""
    try:
        cookies = getattr(st.context, "cookies", None) or {}
        value = cookies.get(COOKIE_NAME) or ""
        return str(value).strip()
    except Exception:
        return ""


def set_auth_cookie(token: str, *, ttl_days: float = AUTH_TTL_DAYS) -> None:
    """Write the auth cookie in the browser (survives refresh / new Streamlit session)."""
    safe = (
        (token or "")
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("'", "\\'")
        .replace("\n", "")
        .replace("\r", "")
    )
    if not safe:
        return
    components.html(
        f"""
        <script>
        (function() {{
            var days = {float(ttl_days)};
            var date = new Date();
            date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
            document.cookie = "{COOKIE_NAME}=" + "{safe}"
                + "; expires=" + date.toUTCString()
                + "; path=/; SameSite=Lax";
        }})();
        </script>
        """,
        height=0,
        width=0,
    )


def clear_auth_cookie() -> None:
    """Expire the auth cookie in the browser."""
    components.html(
        f"""
        <script>
        document.cookie = "{COOKIE_NAME}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; SameSite=Lax";
        </script>
        """,
        height=0,
        width=0,
    )
