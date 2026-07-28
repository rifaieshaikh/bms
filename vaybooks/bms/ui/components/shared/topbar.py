"""Custom fixed top header: search + action buttons + utility icons + user menu.

Pure presentational HTML/CSS (see the ``z-topbar-*`` rules in
``ui/theme/theme.css``) — no Streamlit widgets, so it survives every rerun
without extra wiring. The dropdown user menu uses a native
``<details>/<summary>`` disclosure (opens/closes entirely client-side, no
Python round-trip needed). Rendered once from ``app.py``, fixed above every
page's content — see that file's call site for why it lives there rather
than inside individual pages.
"""

from __future__ import annotations

import streamlit as st

__all__ = ["render_topbar"]

_MENU_ITEMS = (
    ("user", "My Profile"),
    ("settings", "Account Settings"),
    ("lock", "Change Password"),
)

_MENU_ITEMS_HTML = "".join(
    f'<a href="#" class="z-topbar-menu-item"><i class="ti ti-{icon}"></i>{label}</a>'
    for icon, label in _MENU_ITEMS
)

_TOPBAR_HTML = f"""
<div class="z-topbar">
  <div class="z-topbar-search">
    <i class="ti ti-search"></i>
    <input class="z-topbar-search-input" type="text" placeholder="Search..." />
  </div>
  <div class="z-topbar-actions">
    <button type="button" class="z-topbar-btn z-topbar-btn-primary">
      <i class="ti ti-plus"></i>New
    </button>
    <button type="button" class="z-topbar-btn z-topbar-btn-secondary">
      <i class="ti ti-download"></i>Export
    </button>
    <div class="z-topbar-divider"></div>
    <button type="button" class="z-topbar-icon-btn" title="Apps"><i class="ti ti-grid-dots"></i></button>
    <button type="button" class="z-topbar-icon-btn" title="Help"><i class="ti ti-help-circle"></i></button>
    <button type="button" class="z-topbar-icon-btn" title="Notifications">
      <i class="ti ti-bell"></i>
      <span class="z-topbar-badge"></span>
    </button>
    <details class="z-topbar-user">
      <summary>
        <span class="z-topbar-avatar">A</span>
        <span class="z-topbar-user-info">
          <span class="z-topbar-user-name">Administrator</span>
          <span class="z-topbar-user-role">Admin</span>
        </span>
        <i class="ti ti-chevron-down"></i>
      </summary>
      <div class="z-topbar-menu">
        {_MENU_ITEMS_HTML}
        <div class="z-topbar-menu-divider"></div>
        <a href="#" class="z-topbar-menu-item z-topbar-menu-danger"><i class="ti ti-logout"></i>Sign Out</a>
      </div>
    </details>
  </div>
</div>
"""


def render_topbar() -> None:
    """Render the fixed top header. Call once per app run from app.py."""
    st.markdown(_TOPBAR_HTML, unsafe_allow_html=True)
