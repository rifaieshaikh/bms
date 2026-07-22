"""Card components for inventory list views."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.application.finance.reports.services.inventory_report_service import LOW_STOCK_THRESHOLD
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.styles import render_card_grid, status_badge

_STOCK_COLOR = "#2E7D46"
_LOW_COLOR = "#B4711A"
_OUT_COLOR = "#B03636"
_RATE_COLOR = "#5B5560"


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


def _status_badge(is_active: bool) -> str:
    if is_active:
        return status_badge("Active", "green", compact=True)
    return status_badge("Inactive", "gray", compact=True)


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

    with st.container(border=True):
        st.markdown(
            f'<p class="z-card-title">{product.name}</p>',
            unsafe_allow_html=True,
        )
        st.caption(f"{product.sku} · {_format_categories(product)}")
        if show_qty:
            st.markdown(
                f'<p class="z-card-amount" style="color:{qty_color}">'
                f"{qty:g} {unit}</p>",
                unsafe_allow_html=True,
            )
            st.markdown(_stock_badge(qty), unsafe_allow_html=True)
        st.caption(f"Rate ₹{rate:,.0f}")
        cols = st.columns(2)
        view = cols[0].button(
            "View",
            key=f"{key_prefix}_view_{product.id}",
            use_container_width=True,
        )
        edit = cols[1].button(
            "Edit",
            key=f"{key_prefix}_edit_{product.id}",
            use_container_width=True,
        )
    return view, edit


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
            use_container_width=True,
        )


def inventory_low_stock_cards(items: list[dict], *, key_prefix: str = "inv_low") -> None:
    """Dashboard-style cards for low / out-of-stock products."""
    if not items:
        st.caption("No low-stock alerts right now.")
        return

    def _render(item, _i):
        qty = float(item.get("current_qty") or 0)
        unit = item.get("unit") or "pcs"
        with st.container(border=True):
            st.markdown(
                f'<p class="z-card-title">{item.get("name", "—")}</p>',
                unsafe_allow_html=True,
            )
            st.caption(f"{item.get('sku', '')} · {item.get('category_name', '—')}")
            color = _OUT_COLOR if qty <= 0 else _LOW_COLOR
            st.markdown(
                f'<p class="z-card-amount" style="color:{color}">{qty:g} {unit}</p>',
                unsafe_allow_html=True,
            )
            st.markdown(
                status_badge(item.get("stock_status", "Low stock"), "orange", compact=True),
                unsafe_allow_html=True,
            )
            product_id = item.get("id")
            if product_id and st.button(
                "View →",
                key=f"{key_prefix}_{product_id}",
                use_container_width=True,
            ):
                navigation.go_to_detail("inventory_product_detail", product_id)

    render_card_grid(items, _render, suffix=key_prefix, card_min_width=220)
