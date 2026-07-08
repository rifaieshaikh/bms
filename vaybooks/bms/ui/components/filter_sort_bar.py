"""Shared filter + sort bar (icon popovers) for every list route."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import streamlit as st

from vaybooks.bms.ui import filtering as F
from vaybooks.bms.ui.filtering import ListSchema
from vaybooks.bms.ui.session_keys import filters_key, sort_key


def _committed_filters(schema: ListSchema) -> dict:
    key = filters_key(schema.entity_key)
    if key not in st.session_state:
        st.session_state[key] = F.default_filters(schema)
    # Backfill any newly added fields.
    stored = st.session_state[key]
    for fld in schema.filter_fields:
        stored.setdefault(fld.key, F.default_filters(schema)[fld.key])
    return stored


def _committed_sort(schema: ListSchema) -> dict:
    key = sort_key(schema.entity_key)
    if key not in st.session_state:
        st.session_state[key] = F.default_sort(schema)
    return st.session_state[key]


def _widget_key(entity: str, field_key: str) -> str:
    return f"{entity}_flt_{field_key}"


def _seed(widget_key: str, value) -> None:
    if widget_key not in st.session_state:
        st.session_state[widget_key] = value


def _resolve_options(fld: F.FilterField, services) -> list[tuple]:
    """Return a list of ``(value, label)`` pairs for select-like fields."""
    if fld.options is not None:
        out = []
        for opt in fld.options:
            if isinstance(opt, tuple):
                out.append(opt)
            else:
                out.append((opt, str(opt)))
        return out
    if fld.options_loader:
        from vaybooks.bms.ui.list_schemas import OPTION_LOADERS

        loader = OPTION_LOADERS.get(fld.options_loader)
        if loader is not None and services is not None:
            return loader(services)
    return []


def _count_active(schema: ListSchema, filters: dict) -> int:
    return sum(
        1
        for fld in schema.filter_fields
        if F.is_active_value(fld, filters.get(fld.key))
    )


def _render_filter_widgets(schema: ListSchema, committed: dict, services) -> None:
    entity = schema.entity_key
    for fld in schema.filter_fields:
        wkey = _widget_key(entity, fld.key)
        if fld.type == F.EXACT:
            _seed(wkey, committed.get(fld.key) or "")
            st.text_input(fld.label, key=wkey, placeholder=fld.placeholder,
                          help=fld.help or None)
        elif fld.type in (F.SELECT, F.ENTITY_SELECT):
            options = _resolve_options(fld, services)
            values = [None] + [v for v, _ in options]
            labels = {None: F.ALL_LABEL, **{v: lbl for v, lbl in options}}
            _seed(wkey, committed.get(fld.key))
            if st.session_state.get(wkey) not in values:
                st.session_state[wkey] = None
            st.selectbox(
                fld.label, values, key=wkey,
                format_func=lambda v, m=labels: m.get(v, str(v)),
                help=fld.help or None,
            )
        elif fld.type == F.MULTISELECT:
            options = _resolve_options(fld, services)
            values = [v for v, _ in options]
            labels = {v: lbl for v, lbl in options}
            current = [v for v in (committed.get(fld.key) or []) if v in values]
            _seed(wkey, current)
            st.multiselect(
                fld.label, values, key=wkey,
                format_func=lambda v, m=labels: m.get(v, str(v)),
                help=fld.help or None,
            )
        elif fld.type == F.DATE_RANGE:
            current = committed.get(fld.key)
            _seed(wkey, list(current) if current else [])
            st.date_input(fld.label, key=wkey, help=fld.help or None)
            quick = st.columns(2)
            if quick[0].button("MTD", key=f"{wkey}_mtd", use_container_width=True):
                today = date.today()
                st.session_state[wkey] = (today.replace(day=1), today)
                st.rerun()
            if quick[1].button("Last 30d", key=f"{wkey}_30d",
                               use_container_width=True):
                today = date.today()
                st.session_state[wkey] = (today - timedelta(days=30), today)
                st.rerun()
        elif fld.type == F.DATE:
            _seed(wkey, committed.get(fld.key) or date.today())
            st.date_input(fld.label, key=wkey, help=fld.help or None)
        elif fld.type == F.NUMBER_MIN:
            _seed(wkey, float(committed.get(fld.key) or 0))
            st.number_input(fld.label, min_value=0.0, key=wkey,
                            help=fld.help or None)
        elif fld.type == F.CHECKBOX:
            _seed(wkey, bool(committed.get(fld.key)))
            st.checkbox(fld.label, key=wkey, help=fld.help or None)


def _collect_filter_values(schema: ListSchema) -> dict:
    entity = schema.entity_key
    result: dict = {}
    for fld in schema.filter_fields:
        wkey = _widget_key(entity, fld.key)
        value = st.session_state.get(wkey)
        if fld.type == F.EXACT:
            result[fld.key] = (value or "").strip() or None
        elif fld.type == F.DATE_RANGE:
            if isinstance(value, (list, tuple)) and len(value) == 2:
                result[fld.key] = (value[0], value[1])
            else:
                result[fld.key] = None
        elif fld.type == F.MULTISELECT:
            result[fld.key] = list(value or [])
        else:
            result[fld.key] = value
    return result


def _clear_widgets(schema: ListSchema) -> None:
    entity = schema.entity_key
    for fld in schema.filter_fields:
        st.session_state.pop(_widget_key(entity, fld.key), None)


def _render_chips(schema: ListSchema, committed: dict, services) -> None:
    active = [
        (fld, committed.get(fld.key))
        for fld in schema.filter_fields
        if F.is_active_value(fld, committed.get(fld.key))
    ]
    if not active:
        return
    cols = st.columns(min(len(active), 4))
    for i, (fld, value) in enumerate(active):
        label = _chip_label(fld, value, services)
        with cols[i % len(cols)]:
            if st.button(f"✕ {label}", key=f"{schema.entity_key}_chip_{fld.key}",
                         use_container_width=True):
                default = F.default_filters(schema)[fld.key]
                committed[fld.key] = default
                st.session_state.pop(_widget_key(schema.entity_key, fld.key), None)
                st.rerun()


def _chip_label(fld: F.FilterField, value, services) -> str:
    if fld.type == F.DATE_RANGE and isinstance(value, (list, tuple)):
        return f"{fld.label}: {value[0]:%d %b} – {value[1]:%d %b}"
    if fld.type in (F.SELECT, F.ENTITY_SELECT):
        labels = {v: lbl for v, lbl in _resolve_options(fld, services)}
        return f"{fld.label}: {labels.get(value, value)}"
    if fld.type == F.MULTISELECT:
        return f"{fld.label}: {', '.join(str(v) for v in value)}"
    if fld.type == F.CHECKBOX:
        return fld.label
    if fld.type == F.NUMBER_MIN:
        return f"{fld.label}: ≥ {value}"
    return f"{fld.label}: {value}"


def render_filter_sort_bar(
    schema: ListSchema,
    *,
    services=None,
    primary_label: Optional[str] = None,
    primary_key: Optional[str] = None,
    title: Optional[str] = None,
) -> dict:
    """Render the header bar; return ``{filters, sort, primary_clicked}``."""
    committed = _committed_filters(schema)
    sort_state = _committed_sort(schema)
    entity = schema.entity_key

    left, mid_a, mid_b, right = st.columns([9, 1, 1, 1.6], vertical_alignment="center")
    with left:
        st.markdown(f"### {title or schema.title}")

    with mid_a:
        n_active = _count_active(schema, committed)
        flabel = f":material/filter_list: {n_active}" if n_active else \
            ":material/filter_list:"
        with st.popover(flabel, use_container_width=True):
            st.markdown("**Filters**")
            _render_filter_widgets(schema, committed, services)
            btns = st.columns(2)
            if btns[0].button("Apply", type="primary", use_container_width=True,
                              key=f"{entity}_apply_filters"):
                st.session_state[filters_key(entity)] = _collect_filter_values(schema)
                st.rerun()
            if btns[1].button("Clear all", use_container_width=True,
                              key=f"{entity}_clear_filters"):
                st.session_state[filters_key(entity)] = F.default_filters(schema)
                _clear_widgets(schema)
                st.rerun()

    with mid_b:
        with st.popover(":material/sort:", use_container_width=True):
            st.markdown("**Sort by**")
            sort_keys = [s.key for s in schema.sort_options]
            labels = {s.key: s.label for s in schema.sort_options}
            cur_key = sort_state.get("key", schema.default_sort)
            if cur_key not in sort_keys:
                cur_key = schema.default_sort
            field_wkey = f"{entity}_sort_field"
            dir_wkey = f"{entity}_sort_dir"
            _seed(field_wkey, cur_key)
            _seed(dir_wkey, "Newest first" if sort_state.get("desc", True)
                  else "Oldest first")
            st.selectbox(
                "Field", sort_keys, key=field_wkey,
                format_func=lambda k, m=labels: m.get(k, k),
            )
            st.radio("Direction", ["Newest first", "Oldest first"], key=dir_wkey)
            if st.button("Apply sort", type="primary", use_container_width=True,
                         key=f"{entity}_apply_sort"):
                st.session_state[sort_key(entity)] = {
                    "key": st.session_state[field_wkey],
                    "desc": st.session_state[dir_wkey] == "Newest first",
                }
                st.rerun()

    primary_clicked = False
    with right:
        if primary_label:
            primary_clicked = st.button(
                primary_label, type="primary", use_container_width=True,
                key=primary_key or f"{entity}_primary",
            )

    _render_chips(schema, committed, services)

    return {
        "filters": st.session_state[filters_key(entity)],
        "sort": st.session_state[sort_key(entity)],
        "primary_clicked": primary_clicked,
    }
