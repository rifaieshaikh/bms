"""Inject raw HTML/JS via ``st.iframe``.

Replaces deprecated ``st.components.v1.html`` (removed after 2026-06-01).
Used for tiny parent-document script injectors (keyboard focus, click helpers).
"""

from __future__ import annotations

import streamlit as st


def inject_html(html: str, *, height: int = 1, width: int = 1) -> None:
    """Embed ``html`` in a minimal iframe for side-effect scripts."""
    st.iframe(
        html,
        height=max(1, int(height or 1)),
        width=max(1, int(width or 1)),
    )
