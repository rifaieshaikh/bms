"""Shared filter + sort bar (icon buttons → dialogs) for every list route."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import streamlit as st

from vaybooks.bms.ui import filtering as F
from vaybooks.bms.ui.components.common.filter_focus_nav import inject_filters_chain_nav
from vaybooks.bms.ui.dialog_utils import (
    clear_dialog_flags,
    dismiss_armed_dialogs,
    register_armed_dialog,
)
from vaybooks.bms.ui.filtering import ListSchema
from vaybooks.bms.ui.session_keys import filters_key, sort_key


def _quarter_start(today: date | None = None) -> date:
    today = today or date.today()
    month = ((today.month - 1) // 3) * 3 + 1
    return today.replace(month=month, day=1)


def _mtd_range(today: date | None = None) -> tuple[date, date]:
    today = today or date.today()
    return today.replace(day=1), today


def _normalize_date_range(value) -> tuple[date, date] | None:
    if isinstance(value, (list, tuple)) and len(value) == 2:
        start, end = value
        if start and end:
            if start > end:
                start, end = end, start
            return start, end
    return None


def _date_range_presets(today: date | None = None) -> list[tuple[str, tuple[date, date]]]:
    today = today or date.today()
    return [
        ("Today", (today, today)),
        ("Last 7 days", (today - timedelta(days=6), today)),
        ("MTD", _mtd_range(today)),
        ("Last 30 days", (today - timedelta(days=29), today)),
        ("This quarter", (_quarter_start(today), today)),
    ]


def _preset_suffix(label: str) -> str:
    return {
        "Today": "today",
        "Last 7 days": "7d",
        "MTD": "mtd",
        "Last 30 days": "30d",
        "This quarter": "qtr",
    }.get(label, label.lower().replace(" ", "_"))


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


def _committed_sort(schema: ListSchema) -> list[dict]:
    key = sort_key(schema.entity_key)
    stored = st.session_state.get(key)
    normalized = F.normalize_sort(schema, stored)
    st.session_state[key] = normalized
    return normalized


def _sort_level_count_key(entity: str) -> str:
    return f"{entity}_sort_level_count"


def _sort_pending_key(entity: str) -> str:
    return f"{entity}_sort_pending_levels"


def _sort_field_wkey(entity: str, index: int) -> str:
    return f"{entity}_sort_field_{index}"


def _sort_dir_wkey(entity: str, index: int) -> str:
    return f"{entity}_sort_dir_{index}"


def _clear_sort_widgets(entity: str) -> None:
    st.session_state.pop(f"{entity}_sort_field", None)
    st.session_state.pop(f"{entity}_sort_dir", None)
    st.session_state.pop(_sort_level_count_key(entity), None)
    st.session_state.pop(_sort_pending_key(entity), None)
    for i in range(F.MAX_SORT_LEVELS):
        st.session_state.pop(_sort_field_wkey(entity, i), None)
        st.session_state.pop(_sort_dir_wkey(entity, i), None)


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


def _as_list(value) -> list:
    """Normalize a stored filter value (scalar or list) to a list."""
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple, set)):
        return [v for v in value if v is not None]
    return [value]


def _render_filter_widgets(
    schema: ListSchema,
    committed: dict,
    services,
    *,
    include_date_presets: bool = True,
) -> list[str]:
    """Render filter fields and return the focus-chain widget keys.

    Filters use only dropdowns, text boxes and date pickers. When
    ``include_date_presets`` is False (inside ``st.form``), MTD / Last 30d
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
        elif fld.type in (F.SELECT, F.ENTITY_SELECT, F.MULTISELECT):
            options = _resolve_options(fld, services)
            values = [v for v, _ in options]
            labels = {v: lbl for v, lbl in options}
            all_label = getattr(fld, "all_label", None) or F.ALL_LABEL
            if F.is_multi_select(fld):
                current = [v for v in _as_list(committed.get(fld.key)) if v in values]
                _seed(wkey, current)
                # Drop stale widget state (scalar from a previous single select,
                # or options that no longer exist) before instantiating.
                stored = st.session_state.get(wkey)
                if not isinstance(stored, list):
                    st.session_state[wkey] = current
                else:
                    valid = [v for v in stored if v in values]
                    if valid != stored:
                        st.session_state[wkey] = valid
                st.multiselect(
                    fld.label,
                    values,
                    key=wkey,
                    format_func=lambda v, m=labels: m.get(v, str(v)),
                    placeholder=all_label,
                    help=fld.help or None,
                )
            else:
                single_values = [None] + values
                single_labels = {None: all_label, **labels}
                _seed(wkey, committed.get(fld.key))
                if st.session_state.get(wkey) not in single_values:
                    st.session_state[wkey] = None
                st.selectbox(
                    fld.label,
                    single_values,
                    key=wkey,
                    format_func=lambda v, m=single_labels: m.get(v, str(v)),
                    help=fld.help or None,
                )
            chain.append(wkey)
        elif fld.type == F.DATE_RANGE:
            # Presets must run before date_input: Streamlit forbids writing a
            # widget's session key after that widget is instantiated.
            if include_date_presets:
                chain.extend(
                    _render_date_range_preset_buttons(
                        _widget_key(schema.entity_key, fld.key),
                        label=fld.label,
                        entity=schema.entity_key,
                        field_key=fld.key,
                    )
                )
            seeded = _normalize_date_range(committed.get(fld.key)) or _mtd_range()
            _seed(wkey, seeded)
            st.date_input(
                fld.label,
                key=wkey,
                help=fld.help or None,
                format="DD/MM/YYYY",
            )
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


def _render_date_range_preset_buttons(
    wkey: str,
    *,
    label: str = "",
    entity: str | None = None,
    field_key: str | None = None,
) -> list[str]:
    """Preset buttons that write ``wkey`` (and committed filters) then rerun.

    Must run before ``date_input`` for the same ``wkey``.
    """
    if label:
        st.caption(label)
    presets = _date_range_presets()
    cols = st.columns(len(presets))
    chain: list[str] = []
    for col, (name, rang) in zip(cols, presets):
        pkey = f"{wkey}_{_preset_suffix(name)}"
        if col.button(name, key=pkey, width="stretch"):
            st.session_state[wkey] = rang
            if entity and field_key:
                fkey = filters_key(entity)
                if fkey not in st.session_state:
                    st.session_state[fkey] = {}
                st.session_state[fkey][field_key] = rang
            st.rerun()
        chain.append(pkey)
    return chain


def _render_date_range_presets(schema: ListSchema, committed: dict) -> list[str]:
    """Date presets that must sit outside ``st.form``."""
    chain: list[str] = []
    for fld in schema.filter_fields:
        if fld.type != F.DATE_RANGE:
            continue
        wkey = _widget_key(schema.entity_key, fld.key)
        chain.extend(
            _render_date_range_preset_buttons(
                wkey,
                label=fld.label,
                entity=schema.entity_key,
                field_key=fld.key,
            )
        )
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
            normalized = _normalize_date_range(value)
            result[fld.key] = normalized
        elif F.is_multi_select(fld):
            result[fld.key] = _as_list(value)
        else:
            result[fld.key] = value
    return result


def _clear_widgets(schema: ListSchema) -> None:
    entity = schema.entity_key
    for fld in schema.filter_fields:
        wkey = _widget_key(entity, fld.key)
        st.session_state.pop(wkey, None)
        if fld.type == F.DATE_RANGE:
            for name, _ in _date_range_presets():
                st.session_state.pop(f"{wkey}_{_preset_suffix(name)}", None)


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


def _inject_linear_focus(
    chain: list[str],
    apply_key: str,
    *,
    component_key: str,
    manager_id: str,
    clear_key: str | None = None,
    last_field_key: str | None = None,
    restore_key: str | None = None,
) -> None:
    from vaybooks.bms.ui.keyboard.focus.registry import get_strategy

    if not chain:
        return
    get_strategy("linear_apply").inject(
        manager_id=manager_id,
        chain=chain,
        # Do not steal focus back to the first field on every dialog rerun.
        restore_key=restore_key,
        apply_key=apply_key,
        clear_key=clear_key,
        last_field_key=last_field_key,
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
    last_field_key = None
    chain: list[str] = []

    # enter_to_submit=False so Enter inside an open dropdown picks an option
    # instead of submitting the form; chain nav applies on Enter otherwise.
    with st.form(
        f"{entity}_filters_form",
        border=False,
        enter_to_submit=False,
    ):
        field_chain = _render_filter_widgets(
            schema,
            committed,
            services,
            include_date_presets=False,
        )
        last_field_key = field_chain[-1] if field_chain else None
        # Native Tab order follows DOM: fields → Clear all → Apply.
        # Clear is column 0 (left), Apply is column 1 (right).
        chain = [*preset_chain, *field_chain, clear_key, apply_key]
        btns = st.columns(2)
        clear_clicked = btns[0].form_submit_button(
            "Clear all",
            width="stretch",
            key=clear_key,
        )
        apply_clicked = btns[1].form_submit_button(
            "Apply",
            type="primary",
            width="stretch",
            key=apply_key,
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

    # Dedicated arrow nav first (wins capture): Up/Down between fields, Enter
    # applies unless a dropdown menu is open (then it picks the option).
    inject_filters_chain_nav(
        chain=chain,
        apply_key=apply_key,
        clear_key=clear_key,
    )
    _inject_linear_focus(
        chain,
        apply_key,
        clear_key=clear_key,
        last_field_key=last_field_key,
        restore_key=None,
        component_key=f"focus_filters_{entity}",
        manager_id=f"filters_{entity}",
    )


def _apply_pending_sort_levels(entity: str) -> None:
    """Apply deferred sort-level edits before any sort widgets instantiate.

    Streamlit forbids writing a widget key after that widget exists in the
    current run. Remove/rebuild therefore stashes the new levels and we apply
    them here on the next run.
    """
    pending_key = _sort_pending_key(entity)
    pending = st.session_state.pop(pending_key, None)
    if not isinstance(pending, list):
        return
    count_key = _sort_level_count_key(entity)
    st.session_state[count_key] = max(1, min(len(pending), F.MAX_SORT_LEVELS))
    for j, crit in enumerate(pending[: F.MAX_SORT_LEVELS]):
        if not isinstance(crit, dict):
            continue
        st.session_state[_sort_field_wkey(entity, j)] = crit.get("key")
        st.session_state[_sort_dir_wkey(entity, j)] = (
            "Descending" if crit.get("desc", True) else "Ascending"
        )
    for j in range(len(pending), F.MAX_SORT_LEVELS):
        st.session_state.pop(_sort_field_wkey(entity, j), None)
        st.session_state.pop(_sort_dir_wkey(entity, j), None)


@st.dialog("Sort", on_dismiss=_on_sort_dismiss)
def _sort_dialog(schema: ListSchema) -> None:
    from vaybooks.bms.ui.keyboard.context import set_sort_ui_open

    entity = schema.entity_key
    flag = _sort_flag(entity)
    register_armed_dialog(flag)
    set_sort_ui_open(entity)

    # Must run before any selectbox/radio with these keys is created.
    _apply_pending_sort_levels(entity)

    sort_state = _committed_sort(schema)
    st.markdown("**Sort by**")
    sort_keys = [s.key for s in schema.sort_options]
    labels = {s.key: s.label for s in schema.sort_options}
    count_key = _sort_level_count_key(entity)
    if count_key not in st.session_state:
        st.session_state[count_key] = max(1, min(len(sort_state), F.MAX_SORT_LEVELS))
    n_levels = int(st.session_state[count_key])
    n_levels = max(1, min(n_levels, F.MAX_SORT_LEVELS, len(sort_keys) or 1))

    legacy_dir = {
        "Newest first": "Descending",
        "Oldest first": "Ascending",
    }
    # Seed widgets from committed multi-sort (or legacy single dict via normalize).
    for i in range(n_levels):
        crit = sort_state[i] if i < len(sort_state) else sort_state[0]
        fk = _sort_field_wkey(entity, i)
        dk = _sort_dir_wkey(entity, i)
        seed_key = crit.get("key", schema.default_sort)
        if seed_key not in sort_keys:
            seed_key = schema.default_sort
        _seed(fk, seed_key)
        if st.session_state.get(fk) not in sort_keys:
            st.session_state[fk] = seed_key
        _seed(dk, "Descending" if crit.get("desc", True) else "Ascending")
        if st.session_state.get(dk) in legacy_dir:
            st.session_state[dk] = legacy_dir[st.session_state[dk]]

    chain: list[str] = []
    radio_keys: list[str] = []
    used_fields: list[str] = []
    for i in range(n_levels):
        fk = _sort_field_wkey(entity, i)
        dk = _sort_dir_wkey(entity, i)
        # Exclude fields already chosen in earlier levels.
        available = [k for k in sort_keys if k not in used_fields or k == st.session_state.get(fk)]
        if not available:
            available = list(sort_keys)
        if st.session_state.get(fk) not in available:
            st.session_state[fk] = available[0]
        cols = st.columns([4, 3, 1] if i > 0 else [4, 4])
        with cols[0]:
            st.selectbox(
                f"Field {i + 1}" if n_levels > 1 else "Field",
                available,
                key=fk,
                format_func=lambda k, m=labels: m.get(k, k),
            )
        with cols[1]:
            st.radio(
                f"Direction {i + 1}" if n_levels > 1 else "Direction",
                ["Ascending", "Descending"],
                key=dk,
                horizontal=True,
            )
        if i > 0:
            with cols[2]:
                if st.button("✕", key=f"{entity}_sort_remove_{i}", help="Remove level"):
                    # Compact levels above i down — defer widget-key writes to
                    # the next run (widgets for lower indexes already exist).
                    remaining = []
                    for j in range(n_levels):
                        if j == i:
                            continue
                        remaining.append(
                            {
                                "key": st.session_state.get(_sort_field_wkey(entity, j)),
                                "desc": st.session_state.get(_sort_dir_wkey(entity, j))
                                == "Descending",
                            }
                        )
                    st.session_state[_sort_pending_key(entity)] = remaining
                    st.rerun()
        used_fields.append(st.session_state.get(fk))
        chain.extend([fk, dk])
        radio_keys.append(dk)

    can_add = (
        n_levels < F.MAX_SORT_LEVELS
        and n_levels < len(sort_keys)
        and any(k not in used_fields for k in sort_keys)
    )
    if can_add:
        if st.button("Add sort level", key=f"{entity}_sort_add_level"):
            # New level keys are not instantiated yet, but still defer via
            # pending so seeding stays consistent with remove.
            remaining = []
            for j in range(n_levels):
                remaining.append(
                    {
                        "key": st.session_state.get(_sort_field_wkey(entity, j)),
                        "desc": st.session_state.get(_sort_dir_wkey(entity, j))
                        == "Descending",
                    }
                )
            unused = [k for k in sort_keys if k not in used_fields]
            nxt = unused[0] if unused else sort_keys[0]
            remaining.append({"key": nxt, "desc": True})
            st.session_state[_sort_pending_key(entity)] = remaining
            st.rerun()

    apply_key = f"{entity}_apply_sort"
    clear_key = f"{entity}_clear_sort"
    btns = st.columns(2)
    clear_clicked = btns[0].button(
        "Clear sort", width="stretch", key=clear_key
    )
    apply_clicked = btns[1].button(
        "Apply sort", type="primary", width="stretch", key=apply_key
    )
    chain.extend([clear_key, apply_key])

    if apply_clicked:
        rows = []
        for i in range(int(st.session_state.get(count_key, 1))):
            rows.append(
                {
                    "key": st.session_state.get(_sort_field_wkey(entity, i)),
                    "desc": st.session_state.get(_sort_dir_wkey(entity, i))
                    == "Descending",
                }
            )
        st.session_state[sort_key(entity)] = F.normalize_sort(schema, rows)
        _close_sort_dialog(entity)
        st.rerun()
    if clear_clicked:
        st.session_state[sort_key(entity)] = F.default_sort(schema)
        _clear_sort_widgets(entity)
        st.session_state.pop(_sort_pending_key(entity), None)
        _close_sort_dialog(entity)
        st.rerun()

    inject_filters_chain_nav(
        chain=chain,
        apply_key=apply_key,
        clear_key=clear_key,
        radio_keys=radio_keys,
        radio_key=radio_keys[-1] if radio_keys else None,
    )
    _inject_linear_focus(
        chain,
        apply_key,
        clear_key=clear_key,
        last_field_key=radio_keys[-1] if radio_keys else None,
        restore_key=_sort_field_wkey(entity, 0),
        component_key=f"focus_sort_{entity}",
        manager_id=f"sort_{entity}",
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
                width="stretch",
            ):
                default = F.default_filters(schema)[fld.key]
                committed[fld.key] = default
                st.session_state.pop(_widget_key(schema.entity_key, fld.key), None)
                st.rerun()


def _chip_label(fld: F.FilterField, value, services) -> str:
    if fld.type == F.DATE_RANGE and isinstance(value, (list, tuple)):
        return f"{fld.label}: {value[0]:%d %b} – {value[1]:%d %b}"
    if fld.type in (F.SELECT, F.ENTITY_SELECT, F.MULTISELECT):
        labels = {v: lbl for v, lbl in _resolve_options(fld, services)}
        chosen = _as_list(value)
        text = ", ".join(str(labels.get(v, v)) for v in chosen)
        return f"{fld.label}: {text}"
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
    primary_action: Optional[str] = None,
) -> dict:
    """Render the header bar; return ``{filters, sort, primary_clicked}``.

    ``primary_action`` — optional extra action id (e.g. ``purchases.orders.create``)
    that also triggers the primary button and supplies its help chord.
    """
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
    filter_help = bindings["actions"].get("list.filters.open", "ctrl+alt+f")
    sort_help = bindings["actions"].get("list.sort.open", "ctrl+shift+s")
    help_action = primary_action or "list.primary"
    primary_help = bindings["actions"].get(
        help_action, bindings["actions"].get("list.primary", "ctrl+shift+n")
    )
    clear_filters_help = bindings["actions"].get("list.filters.clear", "ctrl+1")
    clear_sort_help = bindings["actions"].get("list.sort.clear", "ctrl+2")

    open_filters = consume_action("list.filters.open")
    open_sort = consume_action("list.sort.open")
    clear_filters = consume_action("list.filters.clear")
    clear_sort = consume_action("list.sort.clear")

    wired = [
        "list.filters.open",
        "list.sort.open",
        "list.filters.apply",
        "list.filters.clear",
        "list.sort.clear",
        "list.primary",
    ]
    if primary_action:
        wired.append(primary_action)
    mark_wired(*wired)

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
            width="stretch",
            help=f"{filter_help} · clear {clear_filters_help}",
            key=f"{entity}_filters_open_btn",
        ):
            st.session_state[_filters_flag(entity)] = True
            st.rerun()

    with mid_b:
        if st.button(
            ":material/sort:",
            width="stretch",
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
                width="stretch",
                key=primary_key or f"{entity}_primary",
                help=primary_help,
            )

    if consume_action("list.primary") or (
        primary_action and consume_action(primary_action)
    ):
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
