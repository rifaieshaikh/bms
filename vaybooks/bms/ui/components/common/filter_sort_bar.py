"""Shared filter + sort bar (icon buttons → dialogs) for every list route."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import streamlit as st

from vaybooks.bms.ui import filtering as F
from vaybooks.bms.ui.dialog_utils import (
    clear_dialog_flags,
    dismiss_armed_dialogs,
    register_armed_dialog,
)
from vaybooks.bms.ui.filtering import ListSchema
from vaybooks.bms.ui.session_keys import filters_key, sort_key


def _filters_flag(entity: str) -> str:
    return f"list_filters_dialog_{entity}"


def _sort_flag(entity: str) -> str:
    return f"list_sort_dialog_{entity}"


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


def _render_filter_widgets(
    schema: ListSchema,
    committed: dict,
    services,
    *,
    include_date_presets: bool = True,
) -> list[str]:
    """Render filter fields; return focus-chain widget keys in order.

    When ``include_date_presets`` is False (inside ``st.form``), MTD / Last 30d
    buttons are omitted — Streamlit disallows ordinary buttons inside forms.
    """
    entity = schema.entity_key
    chain: list[str] = []
    for fld in schema.filter_fields:
        wkey = _widget_key(entity, fld.key)
        if fld.type in (F.EXACT, F.REGEX):
            _seed(wkey, committed.get(fld.key) or "")
            placeholder = fld.placeholder
            if not placeholder and fld.type == F.REGEX:
                placeholder = "regex, case-insensitive"
            st.text_input(
                fld.label,
                key=wkey,
                placeholder=placeholder,
                help=fld.help or None,
            )
            chain.append(wkey)
        elif fld.type in (F.SELECT, F.ENTITY_SELECT):
            options = _resolve_options(fld, services)
            values = [None] + [v for v, _ in options]
            labels = {None: F.ALL_LABEL, **{v: lbl for v, lbl in options}}
            _seed(wkey, committed.get(fld.key))
            if st.session_state.get(wkey) not in values:
                st.session_state[wkey] = None
            st.selectbox(
                fld.label,
                values,
                key=wkey,
                format_func=lambda v, m=labels: m.get(v, str(v)),
                help=fld.help or None,
            )
            chain.append(wkey)
        elif fld.type == F.MULTISELECT:
            options = _resolve_options(fld, services)
            values = [v for v, _ in options]
            labels = {v: lbl for v, lbl in options}
            current = [v for v in (committed.get(fld.key) or []) if v in values]
            _seed(wkey, current)
            st.multiselect(
                fld.label,
                values,
                key=wkey,
                format_func=lambda v, m=labels: m.get(v, str(v)),
                help=fld.help or None,
            )
            chain.append(wkey)
        elif fld.type == F.DATE_RANGE:
            # Presets must run before date_input: Streamlit forbids writing a
            # widget's session key after that widget is instantiated.
            mtd_key = f"{wkey}_mtd"
            d30_key = f"{wkey}_30d"
            if include_date_presets:
                quick = st.columns(2)
                if quick[0].button("MTD", key=mtd_key, use_container_width=True):
                    today = date.today()
                    st.session_state[wkey] = (today.replace(day=1), today)
                    st.rerun()
                if quick[1].button(
                    "Last 30d", key=d30_key, use_container_width=True
                ):
                    today = date.today()
                    st.session_state[wkey] = (today - timedelta(days=30), today)
                    st.rerun()
                chain.extend([mtd_key, d30_key])
            current = committed.get(fld.key)
            _seed(wkey, list(current) if current else [])
            st.date_input(fld.label, key=wkey, help=fld.help or None)
            chain.append(wkey)
        elif fld.type == F.DATE:
            _seed(wkey, committed.get(fld.key) or date.today())
            st.date_input(fld.label, key=wkey, help=fld.help or None)
            chain.append(wkey)
        elif fld.type == F.NUMBER_MIN:
            _seed(wkey, float(committed.get(fld.key) or 0))
            st.number_input(
                fld.label, min_value=0.0, key=wkey, help=fld.help or None
            )
            chain.append(wkey)
        elif fld.type == F.CHECKBOX:
            _seed(wkey, bool(committed.get(fld.key)))
            st.checkbox(fld.label, key=wkey, help=fld.help or None)
            chain.append(wkey)
    return chain


def _render_date_range_presets(schema: ListSchema, committed: dict) -> list[str]:
    """MTD / Last 30d controls that must sit outside ``st.form``."""
    entity = schema.entity_key
    chain: list[str] = []
    for fld in schema.filter_fields:
        if fld.type != F.DATE_RANGE:
            continue
        wkey = _widget_key(entity, fld.key)
        mtd_key = f"{wkey}_mtd"
        d30_key = f"{wkey}_30d"
        st.caption(fld.label)
        quick = st.columns(2)
        if quick[0].button("MTD", key=mtd_key, use_container_width=True):
            today = date.today()
            st.session_state[wkey] = (today.replace(day=1), today)
            st.rerun()
        if quick[1].button("Last 30d", key=d30_key, use_container_width=True):
            today = date.today()
            st.session_state[wkey] = (today - timedelta(days=30), today)
            st.rerun()
        chain.extend([mtd_key, d30_key])
    return chain


def _collect_filter_values(schema: ListSchema) -> dict:
    entity = schema.entity_key
    result: dict = {}
    for fld in schema.filter_fields:
        wkey = _widget_key(entity, fld.key)
        value = st.session_state.get(wkey)
        if fld.type in (F.EXACT, F.REGEX):
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
        wkey = _widget_key(entity, fld.key)
        st.session_state.pop(wkey, None)
        st.session_state.pop(f"{wkey}_mtd", None)
        st.session_state.pop(f"{wkey}_30d", None)


def _clear_sort_widgets(entity: str) -> None:
    st.session_state.pop(f"{entity}_sort_field", None)
    st.session_state.pop(f"{entity}_sort_dir", None)


def _close_filters_dialog(entity: str) -> None:
    from vaybooks.bms.ui.keyboard.context import clear_list_panel_ui

    clear_dialog_flags(_filters_flag(entity))
    dismiss_armed_dialogs()
    clear_list_panel_ui()


def _close_sort_dialog(entity: str) -> None:
    from vaybooks.bms.ui.keyboard.context import clear_list_panel_ui

    clear_dialog_flags(_sort_flag(entity))
    dismiss_armed_dialogs()
    clear_list_panel_ui()


def _on_filters_dismiss() -> None:
    from vaybooks.bms.ui.keyboard.context import clear_list_panel_ui

    dismiss_armed_dialogs()
    clear_list_panel_ui()


def _on_sort_dismiss() -> None:
    from vaybooks.bms.ui.keyboard.context import clear_list_panel_ui

    dismiss_armed_dialogs()
    clear_list_panel_ui()


def _inject_linear_focus(chain: list[str], apply_key: str, *, component_key: str) -> None:
    from vaybooks.bms.ui.keyboard.focus_manager import inject_focus_manager

    if not chain:
        return
    inject_focus_manager(
        chain,
        restore_key=chain[0],
        mode="linear_apply",
        apply_key=apply_key,
        component_key=component_key,
    )


@st.dialog("Filters", on_dismiss=_on_filters_dismiss)
def _filters_dialog(schema: ListSchema, services) -> None:
    from vaybooks.bms.ui.keyboard.actions import consume_action
    from vaybooks.bms.ui.keyboard.context import set_filters_ui_open
    from vaybooks.bms.ui.keyboard.wired import mark_wired

    entity = schema.entity_key
    flag = _filters_flag(entity)
    register_armed_dialog(flag)
    set_filters_ui_open(entity)
    mark_wired("list.filters.apply", "list.filters.clear")

    committed = _committed_filters(schema)
    st.markdown("**Filters**")
    # Date presets must stay outside the form (ordinary buttons are forbidden).
    preset_chain = _render_date_range_presets(schema, committed)
    apply_key = f"{entity}_apply_filters"
    clear_key = f"{entity}_clear_filters"
    chain: list[str] = []

    # Form so Enter in text fields commits values and submits Apply together.
    with st.form(f"{entity}_filters_form", border=False):
        chain = _render_filter_widgets(
            schema, committed, services, include_date_presets=False
        )
        chain = [*preset_chain, *chain, apply_key, clear_key]
        btns = st.columns(2)
        apply_clicked = btns[0].form_submit_button(
            "Apply",
            type="primary",
            use_container_width=True,
            key=apply_key,
        )
        clear_clicked = btns[1].form_submit_button(
            "Clear all",
            use_container_width=True,
            key=clear_key,
        )

    if consume_action("list.filters.apply"):
        apply_clicked = True
    if consume_action("list.filters.clear"):
        clear_clicked = True

    if apply_clicked:
        st.session_state[filters_key(entity)] = _collect_filter_values(schema)
        _close_filters_dialog(entity)
        st.rerun()
    if clear_clicked:
        st.session_state[filters_key(entity)] = F.default_filters(schema)
        _clear_widgets(schema)
        _close_filters_dialog(entity)
        st.rerun()

    _inject_linear_focus(
        chain, apply_key, component_key=f"focus_filters_{entity}"
    )


@st.dialog("Sort", on_dismiss=_on_sort_dismiss)
def _sort_dialog(schema: ListSchema) -> None:
    from vaybooks.bms.ui.keyboard.context import set_sort_ui_open

    entity = schema.entity_key
    flag = _sort_flag(entity)
    register_armed_dialog(flag)
    set_sort_ui_open(entity)

    sort_state = _committed_sort(schema)
    st.markdown("**Sort by**")
    sort_keys = [s.key for s in schema.sort_options]
    labels = {s.key: s.label for s in schema.sort_options}
    cur_key = sort_state.get("key", schema.default_sort)
    if cur_key not in sort_keys:
        cur_key = schema.default_sort
    field_wkey = f"{entity}_sort_field"
    dir_wkey = f"{entity}_sort_dir"
    apply_key = f"{entity}_apply_sort"
    _seed(field_wkey, cur_key)
    _seed(dir_wkey, "Descending" if sort_state.get("desc", True) else "Ascending")
    # Migrate legacy direction labels from older sessions.
    legacy_dir = {
        "Newest first": "Descending",
        "Oldest first": "Ascending",
    }
    if st.session_state.get(dir_wkey) in legacy_dir:
        st.session_state[dir_wkey] = legacy_dir[st.session_state[dir_wkey]]
    st.selectbox(
        "Field",
        sort_keys,
        key=field_wkey,
        format_func=lambda k, m=labels: m.get(k, k),
    )
    st.radio("Direction", ["Ascending", "Descending"], key=dir_wkey)
    if st.button(
        "Apply sort", type="primary", use_container_width=True, key=apply_key
    ):
        st.session_state[sort_key(entity)] = {
            "key": st.session_state[field_wkey],
            "desc": st.session_state[dir_wkey] == "Descending",
        }
        _close_sort_dialog(entity)
        st.rerun()

    _inject_linear_focus(
        [field_wkey, dir_wkey, apply_key],
        apply_key,
        component_key=f"focus_sort_{entity}",
    )


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
            if st.button(
                f"✕ {label}",
                key=f"{schema.entity_key}_chip_{fld.key}",
                use_container_width=True,
            ):
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
    from vaybooks.bms.ui.keyboard.actions import consume_action
    from vaybooks.bms.ui.keyboard.bindings import get_bindings
    from vaybooks.bms.ui.keyboard.context import (
        is_filters_ui_open,
        is_sort_ui_open,
    )
    from vaybooks.bms.ui.keyboard.wired import mark_wired

    committed = _committed_filters(schema)
    _committed_sort(schema)
    entity = schema.entity_key

    bindings = get_bindings()
    filter_help = bindings["actions"].get("list.filters.open", "ctrl+shift+q")
    sort_help = bindings["actions"].get("list.sort.open", "ctrl+shift+s")
    primary_help = bindings["actions"].get("list.primary", "ctrl+shift+n")
    clear_filters_help = bindings["actions"].get("list.filters.clear", "ctrl+1")
    clear_sort_help = bindings["actions"].get("list.sort.clear", "ctrl+2")

    open_filters = consume_action("list.filters.open")
    open_sort = consume_action("list.sort.open")
    clear_filters = consume_action("list.filters.clear")
    clear_sort = consume_action("list.sort.clear")

    mark_wired(
        "list.filters.open",
        "list.sort.open",
        "list.filters.apply",
        "list.filters.clear",
        "list.sort.clear",
        "list.primary",
    )

    # Clear from list view only (not while a filter/sort dialog is open).
    panel_open = is_filters_ui_open() or is_sort_ui_open()
    if clear_filters and not panel_open:
        st.session_state[filters_key(entity)] = F.default_filters(schema)
        _clear_widgets(schema)
        st.rerun()
    if clear_sort and not panel_open:
        st.session_state[sort_key(entity)] = F.default_sort(schema)
        _clear_sort_widgets(entity)
        st.rerun()

    left, mid_a, mid_b, right = st.columns([9, 1, 1, 1.6], vertical_alignment="center")
    with left:
        st.markdown(f"### {title or schema.title}")

    with mid_a:
        n_active = _count_active(schema, committed)
        flabel = (
            f":material/filter_list: {n_active}"
            if n_active
            else ":material/filter_list:"
        )
        if st.button(
            flabel,
            use_container_width=True,
            help=f"{filter_help} · clear {clear_filters_help}",
            key=f"{entity}_filters_open_btn",
        ):
            st.session_state[_filters_flag(entity)] = True
            st.rerun()

    with mid_b:
        if st.button(
            ":material/sort:",
            use_container_width=True,
            help=f"{sort_help} · clear {clear_sort_help}",
            key=f"{entity}_sort_open_btn",
        ):
            st.session_state[_sort_flag(entity)] = True
            st.rerun()

    primary_clicked = False
    with right:
        if primary_label:
            primary_clicked = st.button(
                primary_label,
                type="primary",
                use_container_width=True,
                key=primary_key or f"{entity}_primary",
                help=primary_help,
            )

    if consume_action("list.primary"):
        primary_clicked = True

    if open_filters:
        st.session_state[_filters_flag(entity)] = True
        st.session_state.pop(_sort_flag(entity), None)
    if open_sort:
        st.session_state[_sort_flag(entity)] = True
        st.session_state.pop(_filters_flag(entity), None)

    if st.session_state.get(_filters_flag(entity)):
        st.session_state.pop(_sort_flag(entity), None)
        _filters_dialog(schema, services)
    elif st.session_state.get(_sort_flag(entity)):
        _sort_dialog(schema)

    _render_chips(schema, committed, services)

    return {
        "filters": _committed_filters(schema),
        "sort": _committed_sort(schema),
        "primary_clicked": primary_clicked,
    }
