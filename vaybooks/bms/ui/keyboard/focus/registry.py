"""Registry of focus strategies by manager_id."""

from __future__ import annotations

from vaybooks.bms.ui.keyboard.focus.base import FocusStrategy
from vaybooks.bms.ui.keyboard.focus.grn import GrnFocusStrategy
from vaybooks.bms.ui.keyboard.focus.linear_apply import LinearApplyFocusStrategy
from vaybooks.bms.ui.keyboard.focus.purchase_lines import (
    PurchaseBillEditFocusStrategy,
    PurchaseBillFocusStrategy,
    PurchaseOrderEditFocusStrategy,
    PurchaseOrderFocusStrategy,
    PurchaseReturnFocusStrategy,
)
from vaybooks.bms.ui.keyboard.focus.sales_lines import (
    DeliveryNoteEditFocusStrategy,
    DeliveryNoteFocusStrategy,
    PricedDocumentFocusStrategy,
    SalesInvoiceEditFocusStrategy,
    SalesInvoiceFocusStrategy,
    SalesOrderEditFocusStrategy,
    SalesOrderFocusStrategy,
    SalesReturnEditFocusStrategy,
    SalesReturnFocusStrategy,
)

_STRATEGIES: dict[str, FocusStrategy] = {
    "purchase_order_dialog": PurchaseOrderFocusStrategy(),
    "purchase_order_edit_dialog": PurchaseOrderEditFocusStrategy(),
    "purchase_bill_dialog": PurchaseBillFocusStrategy(),
    "purchase_bill_edit_dialog": PurchaseBillEditFocusStrategy(),
    "purchase_return_dialog": PurchaseReturnFocusStrategy(),
    "grn_dialog": GrnFocusStrategy(),
    "linear_apply": LinearApplyFocusStrategy(),
    "sales_order_dialog": SalesOrderFocusStrategy(),
    "sales_order_edit_dialog": SalesOrderEditFocusStrategy(),
    "sales_invoice_dialog": SalesInvoiceFocusStrategy(),
    "sales_invoice_edit_dialog": SalesInvoiceEditFocusStrategy(),
    "sales_return_dialog": SalesReturnFocusStrategy(),
    "sales_return_edit_dialog": SalesReturnEditFocusStrategy(),
    "priced_document_dialog": PricedDocumentFocusStrategy(),
    "delivery_note_dialog": DeliveryNoteFocusStrategy(),
    "delivery_note_edit_dialog": DeliveryNoteEditFocusStrategy(),
}


def get_strategy(manager_id: str) -> FocusStrategy:
    strategy = _STRATEGIES.get(manager_id)
    if strategy is None:
        raise KeyError(f"No focus strategy registered for manager_id={manager_id!r}")
    return strategy


def register_strategy(manager_id: str, strategy: FocusStrategy) -> None:
    """Test/extension hook to replace or add a strategy."""
    _STRATEGIES[manager_id] = strategy
