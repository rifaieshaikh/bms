"""Linear-apply focus strategy (filters / sort dialogs)."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from vaybooks.bms.ui.keyboard.focus.base import LINEAR_APPLY_RULES, FocusConfig
from vaybooks.bms.ui.keyboard.focus.engine import inject_focus_engine


class LinearApplyFocusStrategy:
    """Reusable strategy; ``manager_id`` is supplied per inject call."""

    manager_id = "linear_apply"

    def build_config(
        self,
        *,
        chain: Sequence[str],
        restore_key: str | None = None,
        columns: Mapping[str, Sequence[str]] | None = None,
        above_first: str | None = None,
        below_last: str | None = None,
        component_key: str = "focus_mgr",
        manager_id: str | None = None,
        apply_key: str | None = None,
        clear_key: str | None = None,
        last_field_key: str | None = None,
        **dialog_extras: Any,
    ) -> FocusConfig:
        _ = columns, above_first, below_last, dialog_extras
        mid = str(manager_id or self.manager_id)
        rules = dict(LINEAR_APPLY_RULES)
        rules["apply_key"] = str(apply_key or "")
        rules["clear_key"] = str(clear_key or "")
        rules["last_field_key"] = str(last_field_key or "")
        return FocusConfig(
            manager_id=mid,
            chain=chain,
            restore_key=restore_key,
            columns=None,
            above_first=None,
            below_last=None,
            component_key=component_key,
            rules=rules,
        )

    def inject(self, **kwargs: Any) -> None:
        inject_focus_engine(self.build_config(**kwargs))
