"""Load/save shortcut bindings via AppSettings.extra."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from vaybooks.bms.ui.keyboard.chords import RESERVED_LIST_CHILDREN, normalize_chord
from vaybooks.bms.ui.keyboard.defaults import (
    default_actions,
    default_parents,
    ensure_defaults_loaded,
)

SETTINGS_KEY = "keyboard_shortcuts"

LOCKED_PARENTS = frozenset({"customers_list"})

BROWSER_WARN_CHORDS = frozenset(
    {
        "ctrl+t",
        "ctrl+w",
        "ctrl+r",
        "ctrl+h",
        "ctrl+l",
        "ctrl+p",
        "ctrl+shift+n",
        "ctrl+shift+t",
    }
)


def _load_raw() -> dict[str, Any]:
    try:
        from vaybooks.bms.infrastructure.config.settings import get_settings

        extra = get_settings().extra or {}
        raw = extra.get(SETTINGS_KEY) or {}
        if isinstance(raw, dict):
            return raw
    except Exception:
        pass
    return {}


def get_bindings() -> dict[str, dict[str, str]]:
    """Return merged ``{parents, actions}`` chord maps."""
    ensure_defaults_loaded()
    parents = default_parents()
    actions = default_actions()
    raw = _load_raw()
    stored_parents = raw.get("parents") or {}
    stored_actions = raw.get("actions") or {}
    if isinstance(stored_parents, dict):
        for k, v in stored_parents.items():
            if k in LOCKED_PARENTS:
                continue
            if v:
                parents[k] = normalize_chord(str(v))
    if isinstance(stored_actions, dict):
        for k, v in stored_actions.items():
            if v:
                actions[k] = normalize_chord(str(v))
    # Enforce locked
    locked_defaults = default_parents()
    for k in LOCKED_PARENTS:
        if k in locked_defaults:
            parents[k] = locked_defaults[k]
    return {"parents": parents, "actions": actions}


def _persist(parents: dict[str, str], actions: dict[str, str]) -> None:
    from vaybooks.bms.infrastructure.config.settings import get_settings, save_settings

    settings = get_settings()
    extra = dict(settings.extra or {})
    extra[SETTINGS_KEY] = {"parents": parents, "actions": actions}
    settings.extra = extra
    try:
        save_settings(settings, encrypt_uri=True)
    except Exception:
        # Non-desktop / no config path: keep in-memory only for this process.
        pass


def save_parent_binding(nav_key: str, chord: str) -> tuple[bool, str]:
    if nav_key in LOCKED_PARENTS:
        return False, "This page shortcut is locked and cannot be remapped."
    chord = normalize_chord(chord)
    if not chord:
        return False, "Chord is required."
    if chord in RESERVED_LIST_CHILDREN:
        return False, f"{chord} is reserved for list actions (Add / Filter / Sort / Clear)."
    bindings = get_bindings()
    parents = dict(bindings["parents"])
    # Parent uniqueness
    for other, other_chord in parents.items():
        if other != nav_key and other_chord == chord:
            return False, f"Chord already used by another page ({other})."
    parents[nav_key] = chord
    # Store only overrides vs defaults to keep file smaller? Plan says store maps —
    # store full current maps under extras for simplicity.
    _persist(parents, dict(bindings["actions"]))
    return True, ""


def save_action_binding(action_id: str, chord: str) -> tuple[bool, str]:
    chord = normalize_chord(chord)
    if not chord:
        return False, "Chord is required."
    bindings = get_bindings()
    actions = dict(bindings["actions"])
    actions[action_id] = chord
    _persist(dict(bindings["parents"]), actions)
    return True, ""


def reset_bindings() -> None:
    from vaybooks.bms.ui.keyboard.defaults import ensure_defaults_loaded

    ensure_defaults_loaded(force=True)
    _persist(default_parents(), default_actions())


def warn_for_chord(chord: str) -> str | None:
    n = normalize_chord(chord)
    if n in BROWSER_WARN_CHORDS:
        return f"{n} may conflict with the browser; prefer desktop app usage."
    return None


def all_unique_chords(bindings: dict[str, dict[str, str]] | None = None) -> list[str]:
    bindings = bindings or get_bindings()
    seen: set[str] = set()
    out: list[str] = []
    for chord in list(bindings["parents"].values()) + list(bindings["actions"].values()):
        n = normalize_chord(chord)
        if n and n not in seen and n != "escape":
            seen.add(n)
            out.append(n)
    return out
