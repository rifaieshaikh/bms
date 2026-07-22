"""Orchestrates filter bar -> load -> filter -> sort -> paginate -> render."""

from __future__ import annotations

from typing import Callable

import streamlit as st

from vaybooks.bms.ui import filtering as F
from vaybooks.bms.ui.components.filter_sort_bar import render_filter_sort_bar
from vaybooks.bms.ui.filtering import ListSchema
from vaybooks.bms.ui.pagination import paginate_list, render_page_controls
from vaybooks.bms.ui.responsive import page_size_for_width


def _record_id(record) -> str | None:
    rid = getattr(record, "id", None)
    if rid is None and isinstance(record, dict):
        rid = record.get("id")
    return str(rid) if rid is not None else None


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
    page_key_nav: str | None = None,
) -> dict:
    """Render a standard list page. Returns the filter/sort bar result dict.

    Extra keys: ``page_items``, ``view_nth``, ``edit_nth``.
    """
    from vaybooks.bms.ui.keyboard.actions import consume_action
    from vaybooks.bms.ui.keyboard.context import set_card_page, set_current_page
    from vaybooks.bms.ui.keyboard.wired import mark_wired

    if page_key_nav:
        set_current_page(page_key_nav)

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
        bar["page_items"] = []
        bar["view_nth"] = None
        bar["edit_nth"] = None
        return bar

    token = F.filter_token(schema, filters, sort)
    page_key = f"{schema.entity_key}_page"
    page_size = page_size_for_width()

    # Keyboard pagination before computing page slice
    mark_wired("list.prev_page", "list.next_page")
    if consume_action("list.prev_page"):
        st.session_state[page_key] = max(0, int(st.session_state.get(page_key, 0)) - 1)
    if consume_action("list.next_page"):
        st.session_state[page_key] = int(st.session_state.get(page_key, 0)) + 1

    page_items, page, total_pages = paginate_list(
        ordered,
        page_key=page_key,
        page_size=page_size,
        filter_key=f"{page_key}_token",
        filter_value=token,
    )

    ids = [i for i in (_record_id(r) for r in page_items) if i]
    set_card_page(ids, editable=True)
    mark_wired(
        *[f"list.view_nth.{i}" for i in range(1, 10)],
        *[f"list.edit_nth.{i}" for i in range(1, 10)],
    )

    view_nth = edit_nth = None
    for i in range(1, 10):
        if consume_action(f"list.view_nth.{i}") and i <= len(ids):
            view_nth = ids[i - 1]
            break
    for i in range(1, 10):
        if consume_action(f"list.edit_nth.{i}") and i <= len(ids):
            edit_nth = ids[i - 1]
            break

    card_renderer(page_items, services)
    render_page_controls(
        page, total_pages, len(ordered),
        page_key=page_key,
        prev_key=f"{schema.entity_key}_prev",
        next_key=f"{schema.entity_key}_next",
        label=count_label,
    )
    bar["page_items"] = page_items
    bar["view_nth"] = view_nth
    bar["edit_nth"] = edit_nth
    return bar
