"""Tabler Icons Webfont (MIT licensed, https://tabler.io/icons) integration.

Streamlit's own icon surfaces (``st.button``/``st.Page``/``st.toast``/
``st.error`` etc. ``icon=`` kwargs) only accept an emoji character or the
built-in ``:material/name:`` shorthand — they cannot render a webfont glyph,
so those stay on Material Symbols. Real icons only work in genuine HTML
contexts (``st.markdown(..., unsafe_allow_html=True)``); this module is for
those call sites.

The webfont CSS is loaded once via ``icon_font_link()`` — see
``vaybooks.bms.ui.styles.inject_global_css``.
"""

from __future__ import annotations

import streamlit as st

__all__ = ["TABLER_ICONS_CSS_URL", "icon_font_link", "icon_html", "icon_caption"]

TABLER_ICONS_CSS_URL = "https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@latest/tabler-icons.min.css"

# Semantic name -> Tabler webfont class name (https://tabler.io/icons).
# Only names actually used by the app are mapped here — add more as needed.
_ICON_CLASSES: dict[str, str] = {
    "phone": "ti-phone",
    "user": "ti-user",
    "notes": "ti-notes",
    "check": "ti-check",
    "x": "ti-x",
    "corner-down-right": "ti-corner-down-right",
    "chevron-right": "ti-chevron-right",
}


def icon_font_link() -> str:
    """Return the <link> tag that loads the Tabler Icons webfont CSS.

    Injected once via ``inject_global_css()`` — don't call this per-component.
    """
    return f'<link rel="stylesheet" href="{TABLER_ICONS_CSS_URL}">'


def icon_html(name: str, *, size: int = 16, color: str = "currentColor") -> str:
    """Return one Tabler icon as an inline webfont glyph (``<i class="ti ti-...">``).

    Only usable inside HTML (``st.markdown(..., unsafe_allow_html=True)``,
    or composed into another component's HTML string) — Streamlit widgets'
    native ``icon=`` kwargs won't render this.
    """
    css_class = _ICON_CLASSES[name]
    return (
        f'<i class="ti {css_class}" '
        f'style="font-size:{size}px;color:{color};vertical-align:-2px;line-height:1"></i>'
    )


def icon_caption(text: str, *, icon: str, size: int = 14) -> None:
    """Drop-in replacement for ``st.caption(f"<emoji> {text}")`` using a real icon.

    Renders a muted, caption-styled line with a leading Tabler icon. Purely
    visual (no interactivity) — safe anywhere ``st.caption`` previously held
    an icon-prefixed line.
    """
    st.markdown(
        f'<p class="z-icon-caption">{icon_html(icon, size=size)}<span>{text}</span></p>',
        unsafe_allow_html=True,
    )
