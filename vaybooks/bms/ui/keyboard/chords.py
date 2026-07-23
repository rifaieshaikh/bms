"""Normalize and parse shortcut chord strings (e.g. ``ctrl+shift+o``)."""

from __future__ import annotations

from typing import Optional

_MOD_ORDER = ("ctrl", "alt", "shift", "meta")

_KEY_ALIASES = {
    "left": "ArrowLeft",
    "right": "ArrowRight",
    "up": "ArrowUp",
    "down": "ArrowDown",
    "enter": "Enter",
    "backspace": "Backspace",
    "delete": "Delete",
    "esc": "Escape",
    "escape": "Escape",
    "space": " ",
    ",": ",",
    "/": "/",
    ".": ".",
    "period": ".",
}


def normalize_chord(chord: str | None) -> str:
    """Return canonical lowercase chord like ``ctrl+shift+o``."""
    if not chord:
        return ""
    text = str(chord).strip().lower().replace(" ", "")
    trailing_key = ""
    if text.endswith("+,"):
        text, trailing_key = text[:-2], ","
    elif text.endswith("+/"):
        text, trailing_key = text[:-2], "/"
    elif text.endswith("+."):
        text, trailing_key = text[:-2], "."
    parts = [p for p in text.split("+") if p]
    if trailing_key:
        parts.append(trailing_key)
    if not parts:
        return ""
    mods = [p for p in _MOD_ORDER if p in parts]
    keys = [p for p in parts if p not in _MOD_ORDER]
    if not keys:
        return "+".join(mods)
    return "+".join(mods + [keys[-1]])


def chord_id(chord: str) -> str:
    """Hotkey manager id: one per physical chord."""
    return f"chord:{normalize_chord(chord)}"


def parse_chord(chord: str) -> dict:
    """Parse into modifiers + key for ``streamlit_hotkeys.hk``."""
    norm = normalize_chord(chord)
    parts = norm.split("+") if norm else []
    mods = {m: m in parts for m in _MOD_ORDER}
    keys = [p for p in parts if p not in _MOD_ORDER]
    raw_key = keys[-1] if keys else ""
    key = _KEY_ALIASES.get(raw_key, raw_key)
    # Single letter / digit keys stay as-is for KeyboardEvent.key
    if len(raw_key) == 1 and raw_key.isalnum():
        key = raw_key
    return {
        "key": key,
        "ctrl": mods["ctrl"] or None,
        "alt": mods["alt"] or None,
        "shift": mods["shift"] or None,
        "meta": mods["meta"] or None,
    }


def needs_prevent_default(chord: str) -> bool:
    """Chords that fight the browser should preventDefault."""
    norm = normalize_chord(chord)
    return norm in {
        "ctrl+s",
        "ctrl+f",
        "ctrl+n",
        "ctrl+p",
        "ctrl+o",
        "ctrl+a",
        "ctrl+h",
        "ctrl+t",
        "ctrl+r",
        "ctrl+w",
        "ctrl+l",
        "ctrl+alt+n",
        "ctrl+alt+f",
        "ctrl+alt+s",
        "meta+s",
        "meta+f",
        "meta+n",
    } or norm.startswith("ctrl+") or norm.startswith("meta+")


RESERVED_LIST_CHILDREN = frozenset(
    {"ctrl+shift+n", "ctrl+shift+q", "ctrl+shift+s", "ctrl+1", "ctrl+2"}
)
