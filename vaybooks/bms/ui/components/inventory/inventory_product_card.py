"""Card components for inventory list views."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.application.finance.reports.services.inventory_report_service import LOW_STOCK_THRESHOLD
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.shared import CardAction, card, empty_state
from vaybooks.bms.ui.styles import render_card_grid

_STOCK_COLOR = "var(--color-success-text)"
_LOW_COLOR = "var(--color-warning-text)"
_OUT_COLOR = "var(--color-danger-text)"
_RATE_COLOR = "var(--color-text-muted)"


def _format_categories(product) -> str:
    names = list(getattr(product, "category_names", None) or [])
    if not names and getattr(product, "category_name", ""):
        names = [product.category_name]
    if not names:
        return "—"
    if len(names) <= 2:
        return " · ".join(names)
    return f"{names[0]} · {names[1]} +{len(names) - 2} more"


def _stock_badge_tuple(qty: float, threshold: float = LOW_STOCK_THRESHOLD) -> tuple[str, str]:
    if qty <= 0:
        return ("Out of stock", "red")
    if qty <= threshold:
        return ("Low stock", "orange")
    return ("In stock", "green")


def _status_badge_tuple(is_active: bool) -> tuple[str, str]:
    return ("Active", "green") if is_active else ("Inactive", "gray")


def inventory_product_card(
    product,
    *,
    key_prefix: str,
    show_qty: bool = True,
) -> tuple[bool, bool]:
    """Render a product card. Returns (view_clicked, edit_clicked)."""
    qty = float(getattr(product, "current_qty", 0) or 0)
    unit = getattr(product, "unit", "pcs") or "pcs"
    rate = float(getattr(product, "selling_rate", 0) or 0)
    qty_color = _OUT_COLOR if qty <= 0 else (_LOW_COLOR if qty <= LOW_STOCK_THRESHOLD else _STOCK_COLOR)

    clicks = {"view": False, "edit": False}

    def _on_view() -> None:
        clicks["view"] = True

    def _on_edit() -> None:
        clicks["edit"] = True

    with st.container(border=True):
        card(
            product.name,
            amount=f"{qty:g} {unit}" if show_qty else None,
            amount_style=f"color:{qty_color}",
            badges=[_stock_badge_tuple(qty)] if show_qty else [],
            caption_lines=[
                f"{product.sku} · {_format_categories(product)}",
                f"Rate ₹{rate:,.0f}",
            ],
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
    clicked = {"edit": False}

    def _on_edit() -> None:
        clicked["edit"] = True

    desc = (category.description or "").strip()
    if len(desc) > 72:
        desc = desc[:69] + "…"

    with st.container(border=True):
        card(
            path or category.name,
            badges=[_status_badge_tuple(category.is_active)],
            caption_lines=[
                desc,
                f"{product_count} product{'s' if product_count != 1 else ''}",
            ],
            actions=[
                CardAction(
                    "Edit",
                    key=f"edit_inv_cat_btn_{category.id}",
                    kind="secondary",
                    on_click=_on_edit,
                )
            ],
        )
    return clicked["edit"]


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
                caption_lines=[f"{item.get('sku', '')} · {item.get('category_name', '—')}"],
                actions=[CardAction("View →", key=f"{key_prefix}_{product_id}", kind="secondary", on_click=_on_view)]
                if product_id
                else [],
            )

    render_card_grid(items, _render, suffix=key_prefix, card_min_width=220)
