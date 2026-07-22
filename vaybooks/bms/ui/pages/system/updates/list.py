"""Software updates page (desktop only)."""

import streamlit as st

from vaybooks.bms.version import __version__
from vaybooks.bms.infrastructure.updater.checker import fetch_update_info
from vaybooks.bms.infrastructure.updater.installer import download_and_install


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_update_check():
    return fetch_update_info()


def render(services: dict):
    st.title("Software Updates")
    st.caption(f"Current version: **{__version__}**")

    if st.button("Check for Updates", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    info = _cached_update_check()
    if not info:
        st.warning("Could not reach the update server. Check your internet connection and update URL in Settings.")
        return

    st.write(f"Latest available version: **{info.latest_version}**")
    if info.published_at:
        st.caption(f"Published: {info.published_at}")

    if info.is_newer:
        st.success("New Version Available")
        if info.release_notes:
            st.markdown(info.release_notes)
        if st.button("Download & Install", type="primary", use_container_width=True):
            with st.spinner("Downloading and launching installer..."):
                ok, message = download_and_install(info)
            if ok:
                st.success(message)
                st.info("The installer will update the application. The service will restart automatically.")
            else:
                st.error(message)
    else:
        st.info("You are running the latest version.")
