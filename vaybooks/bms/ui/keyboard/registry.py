"""Catalog metadata for keyboard shortcut actions and parents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ParentShortcut:
    nav_key: str
    label: str
    group: str
    default_chord: str
    locked: bool = False


@dataclass(frozen=True)
class ActionShortcut:
    action_id: str
    label: str
    group: str
    default_chord: str
    destructive: bool = False
    mouse_only: bool = False
    unbound_stub: bool = False


# Populated by defaults.py
PARENTS: dict[str, ParentShortcut] = {}
ACTIONS: dict[str, ActionShortcut] = {}


def register_parent(p: ParentShortcut) -> None:
    PARENTS[p.nav_key] = p


def register_action(a: ActionShortcut) -> None:
    ACTIONS[a.action_id] = a


def all_parents() -> list[ParentShortcut]:
    return list(PARENTS.values())


def all_actions() -> list[ActionShortcut]:
    return list(ACTIONS.values())


def parent_by_nav(nav_key: str) -> Optional[ParentShortcut]:
    return PARENTS.get(nav_key)


def action_by_id(action_id: str) -> Optional[ActionShortcut]:
    return ACTIONS.get(action_id)
