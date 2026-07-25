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

          /* ---- Streamlit chrome: keep expand arrow, drop visual chrome ------ */
          /* CRITICAL: stExpandSidebarButton is a CHILD of stToolbar. Hiding the
             toolbar with display:none also removes the only way to reopen a
             collapsed sidebar. Never display:none the toolbar. */
          header[data-testid="stHeader"] {
            background: transparent !important;
            box-shadow: none !important;
            /* Transparent overlay still steals clicks from our header actions. */
            pointer-events: none !important;
            /* Sit under our custom bar so popovers receive clicks. */
            z-index: 999900 !important;
          }
          div[data-testid="stDecoration"] {
            display: none !important;
          }
          /* Hide deploy / overflow toolbar chrome, but keep the expand control. */
          header[data-testid="stHeader"] [data-testid="stMainMenu"],
          header[data-testid="stHeader"] [data-testid="stToolbarActions"],
          header[data-testid="stHeader"] [data-testid="stAppDeployButton"],
          header[data-testid="stHeader"] .stDeployButton {
            display: none !important;
          }
          /* When the sidebar is collapsed, pin the expand arrow above our bar. */
          [data-testid="stExpandSidebarButton"] {
            display: inline-flex !important;
            visibility: visible !important;
            pointer-events: auto !important;
            position: fixed !important;
            top: 0.45rem !important;
            left: 0.45rem !important;
            z-index: 1000001 !important;
            background: #FBF8F6 !important;
            border: 1px solid var(--z-line) !important;
            border-radius: 8px !important;
            box-shadow: 0 1px 4px rgba(42, 30, 36, 0.1) !important;
            width: 2.25rem !important;
            height: 2.25rem !important;
            align-items: center !important;
            justify-content: center !important;
          }
          /* Keep the in-sidebar collapse arrow clickable above page chrome. */
          [data-testid="stSidebarCollapseButton"] {
            position: relative;
            z-index: 10050;
            pointer-events: auto !important;
          }
          /* Drop the large top padding Streamlit keeps for its own header. */
          section.main > div.block-container,
          div[data-testid="stMainBlockContainer"].block-container,
          .block-container {
            padding-top: 0 !important;
          }

          /* ---- Global top header (keyed container: zheader) --------------- */
          /* Use exact-ish key match so nested zh_actions is not also sticky. */
          div[class*="st-key-zheader"]:not([class*="zh_actions"]) {
            position: sticky;
            top: 0;
            z-index: 999990;
            background: #FBF8F6;
            border-bottom: 1px solid var(--z-line);
            box-shadow: 0 1px 4px rgba(42, 30, 36, 0.06);
            margin: 0 -1.5rem 0.85rem -1.5rem;
            padding: 0.35rem 1rem 0.35rem 1.25rem;
            pointer-events: auto !important;
          }
          /* Kill Streamlit's default vertical gaps inside the header bar. */
          div[class*="st-key-zheader"] div[data-testid="stVerticalBlock"] {
            gap: 0 !important;
          }
          div[class*="st-key-zheader"] [data-testid="stElementContainer"],
          div[class*="st-key-zheader"] [data-testid="element-container"] {
            margin-top: 0 !important;
            margin-bottom: 0 !important;
          }
          div[class*="st-key-zheader"] .z-header-brand,
          div[class*="st-key-zheader"] p.z-header-brand {
            font-size: 1.05rem;
            font-weight: 700;
            color: var(--z-plum);
            letter-spacing: 0.01em;
            line-height: 1.2;
            margin: 0 !important;
            white-space: nowrap;
          }
          /* Icon-action cluster: hug the right edge as a tight group. */
          div[class*="st-key-zh_actions"] {
            display: flex !important;
            justify-content: flex-end !important;
            width: 100%;
          }
          div[class*="st-key-zh_actions"] div[data-testid="stHorizontalBlock"] {
            gap: 0.3rem !important;
            justify-content: flex-end !important;
            width: auto !important;
            margin-left: auto !important;
          }
          div[class*="st-key-zh_actions"] div[data-testid="stColumn"] {
            flex: 0 0 auto !important;
            width: auto !important;
            min-width: 0 !important;
          }
          div[class*="st-key-zheader"] div[data-testid="stPopover"],
          div[class*="st-key-zh_actions"] div[data-testid="stPopover"] {
            pointer-events: auto !important;
          }
          div[class*="st-key-zheader"] div[data-testid="stPopover"] > div > button,
          div[class*="st-key-zheader"] div[data-testid="stPopover"] button {
            border-radius: 8px;
            border-color: var(--z-line);
            background: var(--z-card);
            min-height: 2.1rem;
            height: 2.1rem;
            min-width: 2.1rem;
            padding: 0.2rem 0.45rem;
            white-space: nowrap;
            pointer-events: auto !important;
            position: relative;
            z-index: 2;
          }
          div[class*="st-key-zheader"] div[data-testid="stPopover"] > div > button:hover {
            border-color: var(--z-plum);
            color: var(--z-plum);
          }
          /* Outer brand | actions: let the actions column size to its icons and
             sit flush on the right edge of the bar. */
          div[class*="st-key-zheader"]:not([class*="zh_actions"])
            > div
            > div[data-testid="stHorizontalBlock"]
            > div[data-testid="stColumn"]:first-child {
            flex: 1 1 auto !important;
            width: auto !important;
          }
          div[class*="st-key-zheader"]:not([class*="zh_actions"])
            > div
            > div[data-testid="stHorizontalBlock"]
            > div[data-testid="stColumn"]:last-child {
            flex: 0 0 auto !important;
            width: auto !important;
            min-width: fit-content !important;
          }

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
          div[class*="st-key-metric_tone_warn"] div[data-testid="stMetric"] {
            border-left: 3px solid #B4711A;
            background: #FFFBF5;
          }
          div[class*="st-key-metric_tone_danger"] div[data-testid="stMetric"] {
            border-left: 3px solid #B03636;
            background: #FFF8F8;
          }
          div[class*="st-key-metric_tone_good"] div[data-testid="stMetric"] {
            border-left: 3px solid #2E7D46;
            background: #F6FBF7;
          }
          div[class*="st-key-metric_tone_neutral"] div[data-testid="stMetric"] {
            border-left: 3px solid var(--z-plum);
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
              padding-top: 0 !important;
            }
            div[class*="st-key-zheader"] {
              margin-left: -0.75rem;
              margin-right: -0.75rem;
              padding-left: 0.85rem;
              padding-right: 0.85rem;
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
    "Paid": "green",
    "Unpaid": "red",
    "Sent": "blue",
    "Accepted": "green",
    "Rejected": "red",
    "Expired": "orange",
    "Converted": "violet",
    "Confirmed": "blue",
    "Partially Delivered": "orange",
    "Closed": "gray",
    "Dispatched": "orange",
    "Received": "green",
}


def status_badge(label: str, color: str | None = None, *, compact: bool = False) -> str:
    """Return an HTML pill for a status/label. Render with st.markdown(..., True)."""
    tone = color or STATUS_BADGE_COLORS.get(label, "plum")
    extra = " z-compact" if compact else ""
    return f'<span class="z-badge {tone}{extra}">{label}</span>'


_METRIC_TONES = frozenset({"neutral", "warn", "danger", "good"})


def _parse_metric(metric: tuple) -> tuple[str, object, str | None, str]:
    """Normalize ``(label, value[, help[, tone]])`` to four fields."""
    label, value = metric[0], metric[1]
    helptext = metric[2] if len(metric) > 2 else None
    tone = metric[3] if len(metric) > 3 else "neutral"
    if helptext in _METRIC_TONES and len(metric) == 3:
        # Allow ``(label, value, tone)`` without a help string.
        tone = helptext
        helptext = None
    if tone not in _METRIC_TONES:
        tone = "neutral"
    return label, value, helptext, tone


def metric_grid(
    metrics: Sequence[tuple],
    *,
    suffix: str,
    card_min_width: int = 220,
) -> None:
    """Render KPI metrics responsively (wraps on tablet/phone).

    ``metrics`` is a sequence of ``(label, value)``, ``(label, value, help)``,
    ``(label, value, tone)``, or ``(label, value, help, tone)``.
    Tone is one of ``neutral``, ``warn``, ``danger``, ``good``.
    """
    if not metrics:
        return
    n_cols = max(1, columns_for_width(card_min=card_min_width))
    with card_grid(f"metric_{suffix}"):
        for row_start in range(0, len(metrics), n_cols):
            row = metrics[row_start : row_start + n_cols]
            cols = st.columns(n_cols)
            for offset, metric in enumerate(row):
                label, value, helptext, tone = _parse_metric(metric)
                with cols[offset]:
                    with st.container(key=f"metric_tone_{tone}_{suffix}_{row_start}_{offset}"):
                        st.metric(label, value, help=helptext, border=True)
