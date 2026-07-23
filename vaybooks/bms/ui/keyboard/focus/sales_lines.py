"""Sales-lines and delivery-note focus strategies."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from vaybooks.bms.ui.keyboard.focus.base import (
    GRN_RECEIVE_RULES,
    PURCHASE_LINES_RULES,
    FocusConfig,
)
from vaybooks.bms.ui.keyboard.focus.engine import inject_focus_engine


class _SalesLinesFocusStrategy:
    """Shared product/qty/rate(/discount) grid rules; unique manager_id per dialog."""

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
        grid_roles: Sequence[str] | None = None,
        **dialog_extras: Any,
    ) -> FocusConfig:
        _ = dialog_extras
        rules = dict(PURCHASE_LINES_RULES)
        if grid_roles:
            rules["grid_roles"] = list(grid_roles)
        return FocusConfig(
            manager_id=self.manager_id,
            chain=chain,
            restore_key=restore_key,
            columns=columns,
            above_first=above_first,
            below_last=below_last,
            component_key=component_key,
            rules=rules,
        )

    def inject(self, **kwargs: Any) -> None:
        inject_focus_engine(self.build_config(**kwargs))


class SalesOrderFocusStrategy(_SalesLinesFocusStrategy):
    def __init__(self) -> None:
        super().__init__("sales_order_dialog")


class SalesOrderEditFocusStrategy(_SalesLinesFocusStrategy):
    def __init__(self) -> None:
        super().__init__("sales_order_edit_dialog")


class SalesInvoiceFocusStrategy(_SalesLinesFocusStrategy):
    def __init__(self) -> None:
        super().__init__("sales_invoice_dialog")


class SalesInvoiceEditFocusStrategy(_SalesLinesFocusStrategy):
    def __init__(self) -> None:
        super().__init__("sales_invoice_edit_dialog")


class SalesReturnFocusStrategy(_SalesLinesFocusStrategy):
    def __init__(self) -> None:
        super().__init__("sales_return_dialog")


class SalesReturnEditFocusStrategy(_SalesLinesFocusStrategy):
    def __init__(self) -> None:
        super().__init__("sales_return_edit_dialog")


class PricedDocumentFocusStrategy(_SalesLinesFocusStrategy):
    def __init__(self) -> None:
        super().__init__("priced_document_dialog")


class _DeliveryQtyFocusStrategy:
    """Qty-only grid (mirrors GRN receive)."""

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
            rules=dict(GRN_RECEIVE_RULES),
        )

    def inject(self, **kwargs: Any) -> None:
        inject_focus_engine(self.build_config(**kwargs))


class DeliveryNoteFocusStrategy(_DeliveryQtyFocusStrategy):
    def __init__(self) -> None:
        super().__init__("delivery_note_dialog")


class DeliveryNoteEditFocusStrategy(_DeliveryQtyFocusStrategy):
    def __init__(self) -> None:
        super().__init__("delivery_note_edit_dialog")
