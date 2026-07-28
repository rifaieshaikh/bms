"""Reads the design system's CSS files for injection into Streamlit.

Streamlit's own CSS injection path is this same trick (plain .css files read
at runtime and injected via ``st.markdown(..., unsafe_allow_html=True)`` —
there's no native external-stylesheet API for app-authored CSS). This module
provides that read step. ``vaybooks.bms.ui.styles.inject_global_css`` calls
``theme_css()`` on every page render — ``tokens.css`` (primitives),
``theme.css`` (semantic tokens + components), and ``sidebar_icons.css`` (the
Tabler icon overlay for the sidebar, see that file's docstring) are the
single source of styling for the app.
"""

from __future__ import annotations

from pathlib import Path

_THEME_DIR = Path(__file__).parent
_CSS_FILES = ("tokens.css", "theme.css", "sidebar_icons.css")


def theme_css() -> str:
    """Return the concatenated design-system CSS (tokens, then theme)."""
    return "\n".join((_THEME_DIR / name).read_text(encoding="utf-8") for name in _CSS_FILES)


def inject_theme() -> None:
    """Inject the design-system CSS via ``st.markdown``. Not called anywhere yet."""
    import streamlit as st

    st.markdown(f"<style>\n{theme_css()}\n</style>", unsafe_allow_html=True)
