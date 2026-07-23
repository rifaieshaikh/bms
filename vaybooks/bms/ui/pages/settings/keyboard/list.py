"""Keyboard shortcut settings — parents + actions with wired status."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.ui.keyboard.bindings import (
    BROWSER_WARN_CHORDS,
    LOCKED_PARENTS,
    get_bindings,
    reset_bindings,
    save_action_binding,
    save_parent_binding,
    warn_for_chord,
)
from vaybooks.bms.ui.keyboard.chords import normalize_chord
from vaybooks.bms.ui.keyboard.context import set_current_page
from vaybooks.bms.ui.keyboard.defaults import ensure_defaults_loaded
from vaybooks.bms.ui.keyboard.registry import all_actions, all_parents
from vaybooks.bms.ui.keyboard.wired import is_wired, mark_wired


def render(services: dict):
    set_current_page("keyboard_shortcuts")
    mark_wired("keyboard_shortcuts")
    ensure_defaults_loaded()
    st.title("Keyboard Shortcuts")
    st.caption(
        "Parents jump to a page from anywhere. Actions run in context "
        "(Add / Filter / Sort / Clear on lists; Save when a dialog is open)."
    )

    bindings = get_bindings()
    query = st.text_input("Search", placeholder="Filter by name or chord…").strip().lower()

    tab_pages, tab_actions = st.tabs(["Page shortcuts", "Action shortcuts"])

    with tab_pages:
        st.subheader("Page shortcuts (Parent)")
        if st.button("Reset all to defaults", key="kb_reset_all"):
            reset_bindings()
            st.success("Shortcuts reset to defaults.")
            st.rerun()

        parents = all_parents()
        groups: dict[str, list] = {}
        for p in parents:
            groups.setdefault(p.group, []).append(p)

        for group, items in groups.items():
            st.markdown(f"**{group}**")
            for p in items:
                chord = bindings["parents"].get(p.nav_key, p.default_chord)
                if query and query not in p.label.lower() and query not in chord:
                    continue
                c1, c2, c3 = st.columns([3, 2, 1])
                locked = p.nav_key in LOCKED_PARENTS or p.locked
                c1.write(p.label + (" (locked)" if locked else ""))
                new_chord = c2.text_input(
                    "Chord",
                    value=chord,
                    key=f"kb_parent_{p.nav_key}",
                    disabled=locked,
                    label_visibility="collapsed",
                )
                if locked:
                    c3.caption("Locked")
                elif c3.button("Save", key=f"kb_parent_save_{p.nav_key}"):
                    ok, err = save_parent_binding(p.nav_key, new_chord)
                    if ok:
                        warn = warn_for_chord(new_chord)
                        st.success("Saved." + (f" Note: {warn}" if warn else ""))
                        st.rerun()
                    else:
                        st.error(err)
                warn = warn_for_chord(chord)
                if warn and chord in BROWSER_WARN_CHORDS:
                    st.caption(f":orange[{warn}]")

    with tab_actions:
        st.subheader("Action shortcuts")
        actions = all_actions()
        groups_a: dict[str, list] = {}
        for a in actions:
            groups_a.setdefault(a.group, []).append(a)

        for group, items in groups_a.items():
            st.markdown(f"**{group}**")
            for a in items:
                chord = bindings["actions"].get(a.action_id, a.default_chord)
                if query and query not in a.label.lower() and query not in (chord or "") and query not in a.action_id:
                    continue
                wired = is_wired(a.action_id)
                status = (
                    "Mouse only"
                    if a.mouse_only
                    else ("Stub" if a.unbound_stub else ("Wired" if wired else "Not wired"))
                )
                c1, c2, c3, c4 = st.columns([3, 2, 1.2, 1])
                c1.write(a.label)
                if a.mouse_only or not a.default_chord:
                    c2.caption("—")
                    c3.caption(status)
                    c4.write("")
                    continue
                new_chord = c2.text_input(
                    "Chord",
                    value=chord,
                    key=f"kb_action_{a.action_id}",
                    label_visibility="collapsed",
                )
                c3.caption(status)
                if c4.button("Save", key=f"kb_action_save_{a.action_id}"):
                    ok, err = save_action_binding(a.action_id, new_chord)
                    if ok:
                        st.success("Saved.")
                        st.rerun()
                    else:
                        st.error(err)
