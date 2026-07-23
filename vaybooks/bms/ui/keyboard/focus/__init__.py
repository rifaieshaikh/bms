"""Per-dialog focus strategies and thin shared engine."""

from vaybooks.bms.ui.keyboard.focus.engine import inject_focus_engine
from vaybooks.bms.ui.keyboard.focus.registry import get_strategy, register_strategy

__all__ = [
    "get_strategy",
    "register_strategy",
    "inject_focus_engine",
]
