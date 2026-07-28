"""Lightweight, non-blocking loading indicator shown while a page renders.

Streamlit streams elements to the frontend as the script executes, so the
``st.empty()`` placeholder created here appears the instant this context
manager is entered and disappears the moment ``.empty()`` is called after the
wrapped block finishes — no JS event wiring needed. Styling lives in
``ui/theme/theme.css`` under ``.z-page-loader``.
"""

from __future__ import annotations

from contextlib import contextmanager

import streamlit as st

_LOADER_HTML = '<div class="z-page-loader-wrap"><div class="z-page-loader"></div></div>'


@contextmanager
def page_loader():
    """Show the loader for the duration of the wrapped block, then hide it."""
    placeholder = st.empty()
    placeholder.markdown(_LOADER_HTML, unsafe_allow_html=True)
    try:
        yield
    finally:
        placeholder.empty()
