"""Keyboard shortcuts: capture, resolve, dialog submit helpers, Settings catalog."""

from vaybooks.bms.ui.keyboard.bindings import (
    get_bindings,
    save_action_binding,
    save_parent_binding,
    reset_bindings,
    BROWSER_WARN_CHORDS,
    LOCKED_PARENTS,
)
from vaybooks.bms.ui.keyboard.capture import activate_shortcuts
from vaybooks.bms.ui.keyboard.context import (
    set_current_page,
    get_current_page,
    set_form_editing,
    is_form_editing,
    is_dialog_armed,
    is_filters_ui_open,
    set_filters_ui_open,
    is_sort_ui_open,
    set_sort_ui_open,
    clear_list_panel_ui,
)
from vaybooks.bms.ui.keyboard.dialog_actions import (
    open_dialog,
    request_submit,
    consume_submit,
    armed_submit_key,
)
from vaybooks.bms.ui.keyboard.resolve import resolve_pressed_shortcuts
from vaybooks.bms.ui.keyboard.wired import mark_wired, get_wired, clear_wired, is_wired
from vaybooks.bms.ui.keyboard.actions import consume_action, queue_action, peek_action

__all__ = [
    "activate_shortcuts",
    "resolve_pressed_shortcuts",
    "get_bindings",
    "save_action_binding",
    "save_parent_binding",
    "reset_bindings",
    "BROWSER_WARN_CHORDS",
    "LOCKED_PARENTS",
    "set_current_page",
    "get_current_page",
    "set_form_editing",
    "is_form_editing",
    "is_dialog_armed",
    "is_filters_ui_open",
    "set_filters_ui_open",
    "is_sort_ui_open",
    "set_sort_ui_open",
    "clear_list_panel_ui",
    "open_dialog",
    "request_submit",
    "consume_submit",
    "armed_submit_key",
    "mark_wired",
    "get_wired",
    "clear_wired",
    "is_wired",
    "consume_action",
    "queue_action",
    "peek_action",
]
