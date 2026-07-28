from __future__ import annotations

from typing import Callable, Sequence

import streamlit as st

from vaybooks.bms.ui.components.shared.badges import badge
from vaybooks.bms.ui.theme.icons import icon_html

__all__ = ["avatar", "breadcrumb", "chip"]


def breadcrumb(items: Sequence[tuple[str, Callable[[], None] | None]]) -> None:
    """Render a row of breadcrumb crumbs.

    Each item is ``(label, on_click)``. Pass ``on_click=None`` for the
    current, non-clickable crumb — typically the last one.
    """
    if not items:
        return
    widths = [max(len(label), 4) for label, _ in items]
    cols = st.columns(widths)
    for idx, (col, (label, on_click)) in enumerate(zip(cols, items)):
        with col:
            if on_click is not None:
                # Native st.button only accepts plain text, so the separator
                # stays a plain "›" here (can't embed an SVG in a button label).
                text = f"› {label}" if idx else label
                if st.button(text, key=f"breadcrumb_{idx}_{label}", use_container_width=True):
                    on_click()
            else:
                text = f"{icon_html('chevron-right', size=12)} {label}" if idx else label
                st.markdown(
                    f'<span class="z-badge gray z-compact">{text}</span>',
                    unsafe_allow_html=True,
                )


def avatar(label: str, *, size: str = "md") -> None:
    """Render an initials-circle avatar for a person/entity name."""
    initials = "".join(part[0] for part in label.split()[:2]).upper() or "?"
    px = {"sm": 24, "md": 32, "lg": 40}.get(size, 32)
    st.markdown(
        f'<span style="display:inline-flex;align-items:center;justify-content:center;'
        f"width:{px}px;height:{px}px;border-radius:var(--radius-pill);"
        f"background:var(--color-primary-subtle);color:var(--color-primary);"
        f'font-weight:var(--font-weight-bold);font-size:{px * 0.4:.0f}px;">{initials}</span>',
        unsafe_allow_html=True,
    )


def chip(label: str, *, on_remove: Callable[[], None] | None = None, key: str | None = None) -> None:
    """Render a badge-styled chip, optionally removable via a trailing ✕ button."""
    if on_remove is None:
        st.markdown(badge(label), unsafe_allow_html=True)
        return
    label_col, remove_col = st.columns([4, 1])
    label_col.markdown(badge(label), unsafe_allow_html=True)
    if remove_col.button("✕", key=key or f"chip_remove_{label}"):
        on_remove()
