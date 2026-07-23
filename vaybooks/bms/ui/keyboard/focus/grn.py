"""GRN receive-grid focus strategy."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from vaybooks.bms.ui.keyboard.focus.base import GRN_RECEIVE_RULES, FocusConfig
from vaybooks.bms.ui.keyboard.focus.engine import inject_focus_engine


class GrnFocusStrategy:
    manager_id = "grn_dialog"

    def build_config(
        self,
        *,
        chain: Sequence[str],
        restore_key: str | None = None,
        columns: Mapping[str, Sequence[str]] | None = None,
        above_first: str | None = None,
        below_last: str | None = None,
        component_key: str = "focus_mgr",
        **dialog_extras: Any,
    ) -> FocusConfig:
        _ = dialog_extras
        return FocusConfig(
            manager_id=self.manager_id,
            chain=chain,
            restore_key=restore_key,
            columns=columns,
            above_first=above_first,
            below_last=below_last,
            component_key=component_key,
            rules=dict(GRN_RECEIVE_RULES),
        )

    def inject(self, **kwargs: Any) -> None:
        inject_focus_engine(self.build_config(**kwargs))
