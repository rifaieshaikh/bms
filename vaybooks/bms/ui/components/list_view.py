"""Orchestrates filter bar -> load -> filter -> sort -> paginate -> render."""

from __future__ import annotations

from typing import Callable

import streamlit as st

from vaybooks.bms.ui import filtering as F
from vaybooks.bms.ui.components.filter_sort_bar import render_filter_sort_bar
from vaybooks.bms.ui.filtering import ListSchema
from vaybooks.bms.ui.pagination import paginate_list, render_page_controls
from vaybooks.bms.ui.responsive import page_size_for_width


def render_list(
    schema: ListSchema,
    *,
    services,
    load_fn: Callable[[dict, dict, dict], list],
    card_renderer: Callable[[list, dict], None],
    primary_label: str | None = None,
    primary_key: str | None = None,
    title: str | None = None,
    empty_text: str = "No records found.",
    count_label: str = "records",
) -> dict:
    """Render a standard list page. Returns the filter/sort bar result dict."""
    bar = render_filter_sort_bar(
        schema,
        services=services,
        primary_label=primary_label,
        primary_key=primary_key,
        title=title,
    )
    filters = bar["filters"]
    sort = bar["sort"]

    records = load_fn(services, filters, sort)
    filtered = F.apply_filters(records, schema, filters)
    ordered = F.sort_records(filtered, schema, sort)

    st.caption(f"{len(ordered)} {count_label}")
    if not ordered:
        st.info(empty_text)
        return bar

    token = F.filter_token(schema, filters, sort)
    page_key = f"{schema.entity_key}_page"
    page_size = page_size_for_width()
    page_items, page, total_pages = paginate_list(
        ordered,
        page_key=page_key,
        page_size=page_size,
        filter_key=f"{page_key}_token",
        filter_value=token,
    )
    card_renderer(page_items, services)
    render_page_controls(
        page, total_pages, len(ordered),
        page_key=page_key,
        prev_key=f"{schema.entity_key}_prev",
        next_key=f"{schema.entity_key}_next",
        label=count_label,
    )
    return bar
