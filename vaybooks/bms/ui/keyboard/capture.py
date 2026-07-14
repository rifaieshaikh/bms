"""Activate streamlit-hotkeys: one binding id per physical chord."""

from __future__ import annotations

from vaybooks.bms.ui.keyboard.bindings import all_unique_chords, get_bindings
from vaybooks.bms.ui.keyboard.chords import (
    chord_id,
    needs_prevent_default,
    normalize_chord,
    parse_chord,
)


def _build_hk_list(chords: list[str]):
    import streamlit_hotkeys as hotkeys

    bindings = []
    for chord in chords:
        parsed = parse_chord(chord)
        if not parsed.get("key"):
            continue
        cid = chord_id(chord)
        pd = needs_prevent_default(chord)
        # Ctrl binding
        bindings.append(
            hotkeys.hk(
                cid,
                parsed["key"],
                ctrl=True if parsed["ctrl"] else False,
                alt=True if parsed["alt"] else False,
                shift=True if parsed["shift"] else False,
                meta=False,
                prevent_default=pd,
                ignore_repeat=True,
            )
        )
        # Mac: meta ≡ ctrl when chord uses ctrl
        if parsed["ctrl"]:
            bindings.append(
                hotkeys.hk(
                    cid,
                    parsed["key"],
                    ctrl=False,
                    alt=True if parsed["alt"] else False,
                    shift=True if parsed["shift"] else False,
                    meta=True,
                    prevent_default=pd,
                    ignore_repeat=True,
                )
            )
    return bindings


def activate_shortcuts() -> None:
    """Inject CSS + activate all unique chords from current bindings."""
    try:
        import streamlit_hotkeys as hotkeys
    except Exception:
        return

    try:
        hotkeys.preload_css(key="global")
        chords = all_unique_chords(get_bindings())
        # Always include common list/dialog chords even if somehow missing
        for required in (
            "ctrl+shift+n",
            "ctrl+shift+q",
            "ctrl+shift+s",
            "ctrl+s",
            "ctrl+x",
            "alt+backspace",
        ):
            n = normalize_chord(required)
            if n not in chords:
                chords.append(n)
        hk_list = _build_hk_list(chords)
        if hk_list:
            hotkeys.activate(hk_list, key="global")
    except Exception:
        # Soft-fail so a missing component never bricks the app
        return


def pressed_chord() -> str | None:
    """Return the normalized chord pressed this run, if any."""
    try:
        import streamlit_hotkeys as hotkeys
    except Exception:
        return None

    bindings = get_bindings()
    chords = all_unique_chords(bindings)
    for required in (
        "ctrl+shift+n",
        "ctrl+shift+q",
        "ctrl+shift+s",
        "ctrl+s",
        "ctrl+x",
    ):
        n = normalize_chord(required)
        if n not in chords:
            chords.append(n)
    for chord in chords:
        cid = chord_id(chord)
        try:
            if hotkeys.pressed(cid):
                return normalize_chord(chord)
        except Exception:
            continue
    return None
