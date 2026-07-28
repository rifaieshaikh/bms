"""Card components for inventory list views."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.application.finance.reports.services.inventory_report_service import (
    LOW_STOCK_THRESHOLD,
)
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.shared import CardAction, card, empty_state
from vaybooks.bms.ui.styles import render_card_grid, status_badge

_STOCK_COLOR = "var(--color-success-text)"
_LOW_COLOR = "var(--color-warning-text)"
_OUT_COLOR = "var(--color-danger-text)"


def _format_categories(product) -> str:
    names = list(getattr(product, "category_names", None) or [])
    if not names and getattr(product, "category_name", ""):
        names = [product.category_name]
    if not names:
        return "—"
    if len(names) <= 2:
        return " · ".join(names)
    return f"{names[0]} · {names[1]} +{len(names) - 2} more"


def _stock_badge(qty: float, threshold: float = LOW_STOCK_THRESHOLD) -> str:
    if qty <= 0:
        return status_badge("Out of stock", "red", compact=True)
    if qty <= threshold:
        return status_badge("Low stock", "orange", compact=True)
    return status_badge("In stock", "green", compact=True)


def _stock_badge_tuple(
    qty: float, threshold: float = LOW_STOCK_THRESHOLD
) -> tuple[str, str]:
    if qty <= 0:
        return ("Out of stock", "red")
    if qty <= threshold:
        return ("Low stock", "orange")
    return ("In stock", "green")


def _status_badge(is_active: bool) -> str:
    if is_active:
        return status_badge("Active", "green", compact=True)
    return status_badge("Inactive", "gray", compact=True)


def inventory_product_card(
    product,
    *,
    key_prefix: str,
    show_qty: bool = True,
    qty_override: float | None = None,
    breakdown_caption: str = "",
) -> tuple[bool, bool]:
    """Render a product card. Returns (view_clicked, edit_clicked)."""
    qty = float(
        qty_override
        if qty_override is not None
        else getattr(product, "current_qty", 0) or 0
    )
    unit = getattr(product, "unit", "pcs") or "pcs"
    rate = float(getattr(product, "selling_rate", 0) or 0)
    qty_color = (
        _OUT_COLOR
        if qty <= 0
        else (_LOW_COLOR if qty <= LOW_STOCK_THRESHOLD else _STOCK_COLOR)
    )

    clicks = {"view": False, "edit": False}

    def _on_view() -> None:
        clicks["view"] = True

    def _on_edit() -> None:
        clicks["edit"] = True

    captions = [
        f"{product.sku} · {_format_categories(product)}",
        f"Rate ₹{rate:,.0f}",
    ]
    if breakdown_caption:
        captions.append(breakdown_caption)

    with st.container(border=True):
        card(
            product.name,
            amount=f"{qty:g} {unit}" if show_qty else None,
            amount_style=f"color:{qty_color}",
            badges=[_stock_badge_tuple(qty)] if show_qty else [],
            caption_lines=captions,
            actions=[
                CardAction(
                    "View",
                    key=f"{key_prefix}_view_{product.id}",
                    kind="secondary",
                    on_click=_on_view,
                ),
                CardAction(
                    "Edit",
                    key=f"{key_prefix}_edit_{product.id}",
                    kind="secondary",
                    on_click=_on_edit,
                ),
            ],
        )
    return clicks["view"], clicks["edit"]


def inventory_category_card(category, *, product_count: int = 0, path: str = "") -> bool:
    """Render a category card. Returns True if edit was clicked."""
    with st.container(border=True):
        st.markdown(
            f'<p class="z-card-title">{path or category.name}</p>',
            unsafe_allow_html=True,
        )
        st.markdown(_status_badge(category.is_active), unsafe_allow_html=True)
        if category.description:
            desc = category.description.strip()
            if len(desc) > 72:
                desc = desc[:69] + "…"
            st.caption(desc)
        st.caption(f"{product_count} product{'s' if product_count != 1 else ''}")
        return st.button(
            "Edit",
            key=f"edit_inv_cat_btn_{category.id}",
            width="stretch",
        )


def inventory_warehouse_card(warehouse) -> bool:
    """Render a warehouse card. Returns True if edit was clicked."""
    with st.container(border=True):
        st.markdown(
            f'<p class="z-card-title">{warehouse.name}</p>',
            unsafe_allow_html=True,
        )
        st.caption(warehouse.code)
        st.markdown(_status_badge(warehouse.is_active), unsafe_allow_html=True)
        if warehouse.address:
            addr = warehouse.address.strip()
            if len(addr) > 72:
                addr = addr[:69] + "…"
            st.caption(addr)
        return st.button(
            "Edit",
            key=f"edit_inv_wh_btn_{warehouse.id}",
            width="stretch",
        )


def inventory_location_card(location) -> bool:
    """Render a location card (warehouse or retail store). Returns True if edit clicked."""
    loc_type = getattr(location, "location_type", None)
    type_label = getattr(loc_type, "value", loc_type) or "Warehouse"
    type_color = "blue" if type_label == "Retail Store" else "gray"
    with st.container(border=True):
        st.markdown(
            f'<p class="z-card-title">{location.name}</p>',
            unsafe_allow_html=True,
        )
        st.caption(location.code)
        badge_cols = st.columns(2)
        with badge_cols[0]:
            st.markdown(_status_badge(location.is_active), unsafe_allow_html=True)
        with badge_cols[1]:
            st.markdown(
                status_badge(type_label, type_color, compact=True),
                unsafe_allow_html=True,
            )
        if location.address:
            addr = location.address.strip()
            if len(addr) > 72:
                addr = addr[:69] + "…"
            st.caption(addr)
        return st.button(
            "Edit",
            key=f"edit_settings_loc_btn_{location.id}",
            width="stretch",
        )


def inventory_low_stock_cards(items: list[dict], *, key_prefix: str = "inv_low") -> None:
    """Dashboard-style cards for low / out-of-stock products."""
    if not items:
        empty_state("No low-stock alerts right now.")
        return

    def _render(item, _i):
        qty = float(item.get("current_qty") or 0)
        unit = item.get("unit") or "pcs"
        color = _OUT_COLOR if qty <= 0 else _LOW_COLOR
        product_id = item.get("id")

        def _on_view() -> None:
            if product_id:
                navigation.go_to_detail("inventory_product_detail", product_id)

        with st.container(border=True):
            card(
                item.get("name", "—"),
                amount=f"{qty:g} {unit}",
                amount_style=f"color:{color}",
                badges=[(item.get("stock_status", "Low stock"), "orange")],
                caption_lines=[
                    f"{item.get('sku', '')} · {item.get('category_name', '—')}"
                ],
                actions=(
                    [
                        CardAction(
                            "View →",
                            key=f"{key_prefix}_{product_id}",
                            kind="secondary",
                            on_click=_on_view,
                        )
                    ]
                    if product_id
                    else []
                ),
            )

    render_card_grid(items, _render, suffix=key_prefix, card_min_width=220)
