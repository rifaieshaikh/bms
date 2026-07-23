"""Compatibility shim: prefer ``focus.get_strategy(...).inject(...)``.

``inject_focus_manager`` remains for transitional call sites and maps onto the
shared engine with an explicit ``manager_id`` (required for isolation).
"""

from __future__ import annotations

from typing import Mapping, Sequence

from vaybooks.bms.ui.keyboard.focus.base import (
    LINEAR_APPLY_RULES,
    PURCHASE_LINES_RULES,
    FocusConfig,
)
from vaybooks.bms.ui.keyboard.focus.engine import inject_focus_engine


def inject_focus_manager(
    chain: Sequence[str],
    *,
    initial_key: str | None = None,
    restore_key: str | None = None,
    add_line_key: str | None = None,
    data_editor_key: str | None = None,
    columns: Mapping[str, Sequence[str]] | None = None,
    above_first: str | None = None,
    below_last: str | None = None,
    component_key: str = "focus_mgr",
    mode: str = "form",
    apply_key: str | None = None,
    manager_id: str | None = None,
) -> None:
    """Legacy wrapper — new code should use ``get_strategy(id).inject(...)``."""
    _ = initial_key
    mid = manager_id or component_key or "legacy_focus"
    if mode == "linear_apply":
        rules = dict(LINEAR_APPLY_RULES)
        rules["apply_key"] = str(apply_key or "")
    else:
        rules = dict(PURCHASE_LINES_RULES)
        if mode not in ("form", "purchase_lines"):
            rules["mode"] = mode
    inject_focus_engine(
        FocusConfig(
            manager_id=str(mid),
            chain=chain,
            restore_key=restore_key,
            columns=columns,
            above_first=above_first,
            below_last=below_last,
            component_key=component_key,
            rules=rules,
            add_line_key=add_line_key,
            data_editor_key=data_editor_key,
        )
    )
