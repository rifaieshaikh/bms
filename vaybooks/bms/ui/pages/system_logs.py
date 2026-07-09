"""System logs viewer (desktop only)."""

import streamlit as st

from vaybooks.bms.infrastructure.logging.setup import get_log_file_paths, tail_log_file


def render(services: dict):
    st.title("System Logs")

    log_files = get_log_file_paths()
    if not log_files:
        st.info("No log files found. Logs are written to ProgramData when running as a desktop service.")
        return

    selected = st.selectbox("Log file", options=log_files, format_func=lambda p: p.name)
    level = st.selectbox("Level filter", options=["ALL", "DEBUG", "INFO", "WARNING", "ERROR"])
    max_lines = st.slider("Lines to show", min_value=50, max_value=1000, value=200, step=50)

    if st.button("Refresh"):
        st.rerun()

    level_filter = None if level == "ALL" else level
    lines = tail_log_file(selected, max_lines=max_lines, level_filter=level_filter)
    st.code("\n".join(lines) if lines else "(empty)", language="log")
