from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

import streamlit as st

from vaybooks.bms.ui.components.shared.badges import BadgeItem, badge_row
from vaybooks.bms.ui.styles import render_card_grid
from vaybooks.bms.ui.theme.icons import icon_html

__all__ = ["CardAction", "card", "card_grid"]

# Re-exported so callers migrating to ``shared.card`` only need one import.
card_grid = render_card_grid


@dataclass(frozen=True)
class CardAction:
    """One button (or download button) in a card's action row.

    Set ``download_data`` for a download button; otherwise ``on_click`` runs
    when the plain button is pressed.
    """

    label: str
    key: str
    on_click: Callable[[], None] | None = None
    kind: str = "primary"
    download_data: bytes | None = None
    download_file_name: str | None = None
    download_mime: str = "application/octet-stream"


def card(
    title: str,
    *,
    amount: str | None = None,
    amount_style: str | None = "color:var(--color-success-text)",
    badges: Sequence[BadgeItem] = (),
    caption_lines: Sequence[str | tuple[str, str]] = (),
    note: str | None = None,
    footer_badges: Sequence[BadgeItem] = (),
    actions: Sequence[CardAction] = (),
) -> None:
    """Render one entity card's body: title, amount, badges, captions, actions.

    Call from inside ``with st.container(border=True): ...`` (typically via
    ``render_card_grid``/``card_grid``), matching the existing convention
    every ``*_card.py`` already uses. Composes the title/amount/badge-row/
    caption/note/action-row slots that were previously hand-rolled per file.
    """
    st.markdown(f'<p class="z-card-title">{title}</p>', unsafe_allow_html=True)

    if amount is not None:
        style_attr = f' style="{amount_style}"' if amount_style else ""
        st.markdown(
            f'<p class="z-card-amount"{style_attr}>{amount}</p>',
            unsafe_allow_html=True,
        )

    badge_row(badges)

    for line in caption_lines:
        if not line:
            continue
        if isinstance(line, tuple):
            icon_name, text = line
            st.markdown(
                f'<p class="z-icon-caption">{icon_html(icon_name, size=14)}<span>{text}</span></p>',
                unsafe_allow_html=True,
            )
        else:
            st.caption(line)

    if note:
        st.markdown(f'<p class="z-card-journal">{note}</p>', unsafe_allow_html=True)

    badge_row(footer_badges)

    if not actions:
        return
    cols = st.columns(len(actions))
    for col, action in zip(cols, actions):
        if action.download_data is not None:
            col.download_button(
                action.label,
                data=action.download_data,
                file_name=action.download_file_name,
                mime=action.download_mime,
                key=action.key,
                use_container_width=True,
            )
        elif col.button(
            action.label,
            key=action.key,
            type=action.kind,
            use_container_width=True,
        ):
            if action.on_click:
                action.on_click()
