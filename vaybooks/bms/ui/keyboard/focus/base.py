"""Focus strategy contract and config payload for the shared focus engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence


PURCHASE_LINES_RULES: dict[str, Any] = {
    "mode": "purchase_lines",
    "grid_roles": ["product", "qty", "rate"],
    "delete_removes_line": True,
    "enter_empty_product_to_below_last": True,
    "enter_product_with_selection_to_qty": True,
    "enter_rate_to_next_row_product": True,
    "arrows_left_right_grid_only": True,
    "arrows_up_down_same_column": True,
    "arrow_up_first_row_to_above_first": True,
    "arrow_down_last_row_to_below_last": True,
    "above_first_is_date": True,
    "enter_on_action_button_clicks": True,
    "save_cancel_horizontal": True,
    "apply_key": "",
}

GRN_RECEIVE_RULES: dict[str, Any] = {
    "mode": "grn_receive",
    "grid_roles": ["qty"],
    "delete_removes_line": False,
    "enter_empty_product_to_below_last": False,
    "enter_product_with_selection_to_qty": False,
    "enter_rate_to_next_row_product": False,
    "arrows_left_right_grid_only": False,
    "arrows_up_down_same_column": True,
    "arrow_up_first_row_to_above_first": True,
    "arrow_down_last_row_to_below_last": True,
    "above_first_is_date": True,
    "enter_on_action_button_clicks": True,
    "save_cancel_horizontal": False,
    "apply_key": "",
}

LINEAR_APPLY_RULES: dict[str, Any] = {
    "mode": "linear_apply",
    "grid_roles": [],
    "delete_removes_line": False,
    "enter_empty_product_to_below_last": False,
    "enter_product_with_selection_to_qty": False,
    "enter_rate_to_next_row_product": False,
    "arrows_left_right_grid_only": False,
    "arrows_up_down_same_column": False,
    "arrow_up_first_row_to_above_first": False,
    "arrow_down_last_row_to_below_last": False,
    "above_first_is_date": False,
    "enter_on_action_button_clicks": False,
    "save_cancel_horizontal": False,
    "apply_key": "",
    "clear_key": "",
    "last_field_key": "",
}


@dataclass
class FocusConfig:
    """Payload handed to the thin JS focus engine."""

    manager_id: str
    chain: Sequence[str]
    component_key: str
    restore_key: str | None = None
    columns: Mapping[str, Sequence[str]] | None = None
    above_first: str | None = None
    below_last: str | None = None
    rules: dict[str, Any] = field(default_factory=dict)
    add_line_key: str | None = None
    data_editor_key: str | None = None


class FocusStrategy(Protocol):
    """Per-dialog focus strategy: fixed rules + inject into the shared engine."""

    manager_id: str

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
    ) -> FocusConfig: ...

    def inject(self, **kwargs: Any) -> None: ...
