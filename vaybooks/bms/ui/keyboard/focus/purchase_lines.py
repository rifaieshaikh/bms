"""Purchase-lines focus strategies (PO / bill / return)."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from vaybooks.bms.ui.keyboard.focus.base import (
    PURCHASE_LINES_RULES,
    FocusConfig,
)
from vaybooks.bms.ui.keyboard.focus.engine import inject_focus_engine


class _PurchaseLinesFocusStrategy:
    """Shared rules for product/qty/rate grids; unique manager_id per dialog."""

    def __init__(self, manager_id: str) -> None:
        self.manager_id = manager_id

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
            rules=dict(PURCHASE_LINES_RULES),
        )

    def inject(self, **kwargs: Any) -> None:
        inject_focus_engine(self.build_config(**kwargs))


class PurchaseOrderFocusStrategy(_PurchaseLinesFocusStrategy):
    def __init__(self) -> None:
        super().__init__("purchase_order_dialog")


class PurchaseOrderEditFocusStrategy(_PurchaseLinesFocusStrategy):
    def __init__(self) -> None:
        super().__init__("purchase_order_edit_dialog")


class PurchaseBillFocusStrategy(_PurchaseLinesFocusStrategy):
    def __init__(self) -> None:
        super().__init__("purchase_bill_dialog")


class PurchaseBillEditFocusStrategy(_PurchaseLinesFocusStrategy):
    def __init__(self) -> None:
        super().__init__("purchase_bill_edit_dialog")


class PurchaseReturnFocusStrategy(_PurchaseLinesFocusStrategy):
    def __init__(self) -> None:
        super().__init__("purchase_return_dialog")
