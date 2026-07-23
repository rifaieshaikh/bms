"""Manual stock movements — filterable ledger view with record dialog."""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import streamlit as st

from vaybooks.bms.ui.components.common.list_view import render_list
from vaybooks.bms.ui.components.inventory.record_movement_dialog import (
    arm_record_movement_dialog,
    open_record_movement_dialog_if_armed,
)
from vaybooks.bms.ui.inventory_list_schemas import INVENTORY_MOVEMENTS
from vaybooks.bms.ui.keyboard.wired import mark_wired


def _fmt_date(value) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime("%d %b %Y")
    return str(value) if value else "—"


def _load_movements(services, filters, sort):
    try:
        return services["inventory"].get_stock_ledger()
    except Exception:
        return []


def _render_table(page_rows, services):
    if not page_rows:
        return

    rows = []
    for row in page_rows:
        ref = row.get("reference_id") or row.get("reference_type") or "—"
        rows.append(
            {
                "Date": _fmt_date(row.get("movement_date")),
                "Product": row.get("product_name", ""),
                "SKU": row.get("sku", ""),
                "Category": row.get("category_name", ""),
                "Type": row.get("movement_type", ""),
                "Qty In": row.get("qty_in") or "",
                "Qty Out": row.get("qty_out") or "",
                "Reference": ref,
                "Notes": row.get("notes", ""),
            }
        )

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render(services: dict):
    mark_wired(
        "inventory.movement.add",
        "list.primary",
        "list.filters.open",
        "list.sort.open",
    )
    st.caption(
        "Record manual stock movements here. Full history is also on **Stock Ledger**; "
        "open a product for its running balance."
    )
    bar = render_list(
        INVENTORY_MOVEMENTS,
        services=services,
        load_fn=_load_movements,
        card_renderer=_render_table,
        primary_label="Record Movement",
        primary_key="inv_movements_record_btn",
        count_label="movements",
        empty_text="No stock movements yet.",
        page_key_nav="inventory_movements_list",
    )
    if bar["primary_clicked"]:
        arm_record_movement_dialog()
        st.rerun()

    open_record_movement_dialog_if_armed(services)
