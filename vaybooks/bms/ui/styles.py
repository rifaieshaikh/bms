from __future__ import annotations

from typing import Callable, Sequence

import streamlit as st

from vaybooks.bms.ui.responsive import columns_for_width

CARD_GRID_PREFIX = "card_grid"


def inject_global_css() -> None:
    """Inject compact styling for buttons and cards.

    We deliberately do NOT override column layout here. Card grids use real
    Streamlit columns whose count is computed from the viewport width (see
    ``render_card_grid``), which keeps buttons inside their cards and lets each
    row fill the available width. CSS only makes things compact.
    """

    st.markdown(
        """
        <style>
          :root {
            --z-plum: #7B2D4E;
            --z-plum-dark: #5E2038;
            --z-gold: #C9A24B;
            --z-ink: #2A1E24;
            --z-line: #E7DBE0;
            --z-card: #FFFFFF;
          }

          /* ---- Buttons + popover triggers -------------------------------- */
          div.stButton > button,
          div.stDownloadButton > button,
          div[data-testid="stPopover"] > div > button,
          div[data-testid="stPopover"] button {
            padding: 0.22rem 0.6rem;
            min-height: 1.75rem;
            font-size: 0.78rem;
            line-height: 1.2;
            white-space: nowrap;
            border-radius: 8px;
            transition: all 0.15s ease;
          }
          div.stButton > button[kind="primary"] {
            background: linear-gradient(135deg, var(--z-plum), var(--z-plum-dark));
            border: none;
          }
          div.stButton > button[kind="primary"]:hover {
            filter: brightness(1.08);
            box-shadow: 0 2px 8px rgba(123, 45, 78, 0.35);
          }
          div.stButton > button[kind="secondary"]:hover {
            border-color: var(--z-plum);
            color: var(--z-plum);
          }

          /* ---- Section headings get a subtle gold underline -------------- */
          h1, h2, h3 { color: var(--z-ink); }

          /* ---- Cards: elevation, accent edge, hover lift ----------------- */
          div[class*="st-key-card_grid"] div[data-testid="stVerticalBlockBorderWrapper"] {
            padding: 0.6rem 0.7rem;
            border: 1px solid var(--z-line);
            border-left: 3px solid var(--z-plum);
            border-radius: 10px;
            background: var(--z-card);
            box-shadow: 0 1px 3px rgba(42, 30, 36, 0.06);
            transition: box-shadow 0.18s ease, transform 0.18s ease;
          }
          div[class*="st-key-card_grid"]
            div[data-testid="stVerticalBlockBorderWrapper"]:hover {
            box-shadow: 0 6px 18px rgba(42, 30, 36, 0.14);
            transform: translateY(-2px);
          }
          div[class*="st-key-card_grid"]
            div[data-testid="stVerticalBlockBorderWrapper"]
            div[data-testid="stVerticalBlock"] {
            gap: 0.28rem;
          }
          /* Nested bordered blocks inside grid cards: no double chrome */
          div[class*="st-key-card_grid"]
            div[data-testid="stVerticalBlockBorderWrapper"]
            > div[data-testid="stVerticalBlock"]
            > div[data-testid="stVerticalBlockBorderWrapper"] {
            border: none !important;
            box-shadow: none !important;
            border-left: none !important;
            padding: 0;
            background: transparent;
          }
          div[class*="st-key-card_grid"]
            div[data-testid="stVerticalBlockBorderWrapper"]:hover
            > div[data-testid="stVerticalBlock"]
            > div[data-testid="stVerticalBlockBorderWrapper"] {
            transform: none;
            box-shadow: none;
          }

          .z-card-amount {
            font-size: 1.3rem;
            font-weight: 700;
            line-height: 1.2;
            margin: 0.1rem 0 0.3rem 0;
            color: var(--z-ink);
          }
          .z-card-journal {
            font-size: 0.72rem;
            color: #5B5560;
            background: #F8F5F7;
            border: 1px solid #EDE6EA;
            border-radius: 6px;
            padding: 0.35rem 0.5rem;
            margin: 0.2rem 0 0.35rem 0;
            line-height: 1.45;
          }
          .z-badge.z-amount {
            font-size: 0.82rem;
            padding: 0.15rem 0.6rem;
          }

          .z-badge.z-compact {
            white-space: nowrap;
            font-size: 0.68rem;
            padding: 0.06rem 0.45rem;
          }
          .z-card-title {
            font-size: 0.95rem;
            font-weight: 700;
            line-height: 1.25;
            margin: 0 0 0.2rem 0;
            color: var(--z-ink);
          }

          /* ---- Status badge chips ---------------------------------------- */
          .z-badge {
            display: inline-block;
            padding: 0.08rem 0.55rem;
            border-radius: 999px;
            font-size: 0.7rem;
            font-weight: 600;
            letter-spacing: 0.02em;
            border: 1px solid transparent;
          }
          .z-badge.gray   { background:#EEE9EC; color:#5B5560; border-color:#DED6DB; }
          .z-badge.blue   { background:#E5EDFB; color:#2C5AA8; border-color:#CBDcF5; }
          .z-badge.orange { background:#FBEEDD; color:#B4711A; border-color:#F3DBBB; }
          .z-badge.violet { background:#EFE6F7; color:#6B3FA0; border-color:#E0CEF0; }
          .z-badge.green  { background:#E2F2E6; color:#2E7D46; border-color:#C7E6CF; }
          .z-badge.red    { background:#FBE6E6; color:#B03636; border-color:#F3C9C9; }
          .z-badge.plum   { background:#F3E4EB; color:#7B2D4E; border-color:#EAD0DB; }
          .z-badge.gold   { background:#F7EFD9; color:#8A6D1F; border-color:#EBDDB4; }

          /* ---- Sidebar polish -------------------------------------------- */
          section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #FBF8F6 0%, #F3ECEF 100%);
            border-right: 1px solid var(--z-line);
          }
          section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] {
            border-radius: 8px;
            padding: 0.15rem 0.4rem;
            transition: background 0.15s ease;
          }
          section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"]:hover {
            background: rgba(123, 45, 78, 0.08);
          }

          /* ---- Metric tiles ---------------------------------------------- */
          div[data-testid="stMetric"] {
            background: var(--z-card);
            border: 1px solid var(--z-line);
            border-radius: 10px;
            padding: 0.5rem 0.75rem;
          }

          /* ---- Detail panels: single bordered cards on detail pages ------ */
          /* Same plum accent + elevation as grid cards, but no hover lift    */
          /* (they are full-width sections, not clickable tiles).             */
          div[class*="st-key-zpanel"] > div[data-testid="stVerticalBlockBorderWrapper"],
          div[class*="st-key-zpanel"] div[data-testid="stExpander"] {
            border: 1px solid var(--z-line);
            border-left: 3px solid var(--z-plum);
            border-radius: 10px;
            background: var(--z-card);
            box-shadow: 0 1px 3px rgba(42, 30, 36, 0.06);
          }

          /* ---- Phone padding trim ---------------------------------------- */
          @media (max-width: 640px) {
            .block-container {
              padding-left: 0.75rem;
              padding-right: 0.75rem;
            }
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def card_grid(suffix: str = "default"):
    """Return a uniquely-keyed container so scoped card CSS applies."""
    return st.container(key=f"{CARD_GRID_PREFIX}_{suffix}")


def panel(suffix: str = "default"):
    """Return a uniquely-keyed container for a single detail-page panel.

    Bordered containers rendered inside get the plum accent + elevation (via
    the ``st-key-zpanel`` CSS scope) without the hover-lift used for grid
    cards. Use for the header/summary sections on detail pages.
    """
    return st.container(key=f"zpanel_{suffix}")


def render_card_grid(
    items: Sequence,
    render_fn: Callable[[object, int], None],
    *,
    suffix: str,
    card_min_width: int = 240,
) -> None:
    """Render ``items`` as a responsive grid of native Streamlit columns.

    The number of columns is computed from the current viewport width so rows
    fill the available space and reflow per device. ``render_fn(item, index)``
    draws a single card (typically inside its own ``st.container(border=True)``).
    """
    if not items:
        return

    n_cols = max(1, columns_for_width(card_min=card_min_width))
    with card_grid(suffix):
        for row_start in range(0, len(items), n_cols):
            row = items[row_start : row_start + n_cols]
            cols = st.columns(n_cols)
            for offset, item in enumerate(row):
                with cols[offset]:
                    render_fn(item, row_start + offset)


def card_columns(n_items: int, max_cols: int | None = None):
    """Deprecated shim: return viewport-sized columns for legacy callers."""
    n_cols = max(1, columns_for_width())
    if max_cols is not None:
        n_cols = min(max_cols, n_cols)
    return st.columns(n_cols)


# Shared status -> badge color map (used by cards across pages).
STATUS_BADGE_COLORS = {
    "Draft": "gray",
    "In Progress": "blue",
    "Ready For Delivery": "orange",
    "Invoice Generated": "violet",
    "Completed": "green",
    "Delivered": "green",
    "Cancelled": "red",
}


def status_badge(label: str, color: str | None = None, *, compact: bool = False) -> str:
    """Return an HTML pill for a status/label. Render with st.markdown(..., True)."""
    tone = color or STATUS_BADGE_COLORS.get(label, "plum")
    extra = " z-compact" if compact else ""
    return f'<span class="z-badge {tone}{extra}">{label}</span>'


def metric_grid(
    metrics: Sequence[tuple],
    *,
    suffix: str,
    card_min_width: int = 220,
) -> None:
    """Render KPI metrics responsively (wraps on tablet/phone).

    ``metrics`` is a sequence of ``(label, value)`` or ``(label, value, help)``.
    """
    if not metrics:
        return
    n_cols = max(1, columns_for_width(card_min=card_min_width))
    with card_grid(f"metric_{suffix}"):
        for row_start in range(0, len(metrics), n_cols):
            row = metrics[row_start : row_start + n_cols]
            cols = st.columns(n_cols)
            for offset, metric in enumerate(row):
                label, value = metric[0], metric[1]
                helptext = metric[2] if len(metric) > 2 else None
                cols[offset].metric(label, value, help=helptext, border=True)
