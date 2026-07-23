"""Inventory Overview — KPIs, charts, and low-stock queue."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime

import pandas as pd
import streamlit as st

from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.common.filter_sort_bar import (
    _mtd_range,
    _normalize_date_range,
    render_filter_sort_bar,
)
from vaybooks.bms.ui.components.inventory.inventory_product_card import (
    inventory_low_stock_cards,
)
from vaybooks.bms.ui.inventory_list_schemas import INVENTORY_OVERVIEW
from vaybooks.bms.ui.styles import metric_grid


def _fmt_currency(value: float) -> str:
    return f"₹{float(value or 0):,.0f}"


def _as_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _resolved_range(committed: dict) -> tuple[date, date]:
    return _normalize_date_range(committed.get("date_range")) or _mtd_range()


def _chart_or_caption(title: str, df: pd.DataFrame, chart_fn, empty_msg: str) -> None:
    st.markdown(f"**{title}**")
    if df.empty:
        st.caption(empty_msg)
        return
    chart_fn(df)


def _render_quick_actions() -> None:
    st.markdown("**Quick actions**")
    cols = st.columns(5)
    if cols[0].button("Products", use_container_width=True):
        navigation.go_to_list("inventory_products_list")
    if cols[1].button("Stock on Hand", use_container_width=True):
        navigation.go_to_list("inventory_stock_list")
    if cols[2].button("Stock Ledger", use_container_width=True):
        navigation.go_to_list("inventory_stock_ledger_list")
    if cols[3].button("Movements", use_container_width=True):
        navigation.go_to_list("inventory_movements_list")
    if cols[4].button("Reports", use_container_width=True):
        navigation.go_to_list("inventory_reports")


def _render_charts(summary: dict, movements_in_range: list[dict]) -> None:
    row1 = st.columns(2)
    with row1[0]:
        status_df = pd.DataFrame(
            [
                {"status": "In stock", "count": summary.get("in_stock_count", 0)},
                {"status": "Low stock", "count": summary.get("low_stock_count", 0)},
                {
                    "status": "Out of stock",
                    "count": summary.get("out_of_stock_count", 0),
                },
            ]
        ).set_index("status")
        _chart_or_caption(
            "Stock status (active products)",
            status_df,
            st.bar_chart,
            "No active products.",
        )
        st.caption("As of now — not filtered by date range.")

    with row1[1]:
        by_type: dict[str, int] = defaultdict(int)
        for row in movements_in_range:
            by_type[row.get("movement_type") or "(unknown)"] += 1
        if by_type:
            move_df = (
                pd.DataFrame(
                    [{"movement_type": k, "count": v} for k, v in sorted(by_type.items())]
                ).set_index("movement_type")
            )
        else:
            move_df = pd.DataFrame()
        _chart_or_caption(
            "Movements by type (period)",
            move_df,
            st.bar_chart,
            "No stock movements in this date range.",
        )


def render(services: dict) -> None:
    st.header("Inventory Overview")

    reports = services.get("reports_inventory")
    inventory = services.get("inventory")
    if reports is None or inventory is None:
        st.error("Inventory reports service is unavailable.")
        return

    bar = render_filter_sort_bar(
        INVENTORY_OVERVIEW,
        services=services,
        title="Inventory Overview",
    )
    start, end = _resolved_range(bar["filters"])
    st.caption(f"Period: **{start:%d %b %Y}** → **{end:%d %b %Y}**")

    _render_quick_actions()

    try:
        summary = reports.health_summary()
        ledger = inventory.get_stock_ledger()
    except Exception as exc:
        st.error(f"Could not load inventory overview: {exc}")
        return

    if summary.get("total_products", 0) == 0:
        st.info("No products yet. Add a product to get started.")
        return

    movements_in_range = [
        row
        for row in ledger
        if (md := _as_date(row.get("movement_date"))) is not None and start <= md <= end
    ]

    metric_grid(
        [
            ("Active products", summary.get("active_products", 0)),
            ("Active categories", summary.get("active_categories", 0)),
            ("Total units", f"{summary.get('total_units', 0):g}"),
            ("Stock value", _fmt_currency(summary.get("stock_value", 0))),
            ("Low stock", summary.get("low_stock_count", 0)),
            ("Out of stock", summary.get("out_of_stock_count", 0)),
            ("Movements (period)", len(movements_in_range)),
            ("Movements (MTD)", summary.get("movements_this_month", 0)),
        ],
        suffix="inventory_overview",
    )
    st.caption(
        "Stock KPIs are as of now. Movement counts use the Filters period "
        "(MTD metric is calendar month)."
    )

    _render_charts(summary, movements_in_range)

    low_items = summary.get("low_stock_items") or []
    with st.expander(
        f"Low / out-of-stock queue ({len(low_items)})",
        expanded=bool(low_items),
    ):
        inventory_low_stock_cards(low_items, key_prefix="inv_overview_low")
        if st.button("Open Stock on Hand", key="inv_overview_open_stock"):
            navigation.go_to_list("inventory_stock_list")
