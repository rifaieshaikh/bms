"""Centralized, reusable UI primitives built on the design-token system.

See ``vaybooks/bms/ui/theme/`` for the token/CSS layer and
``vaybooks/bms/ui/styles.py`` for the lower-level grid/badge primitives these
compose (``render_card_grid``, ``status_badge``, etc. stay there since ~40
existing files already import them directly).
"""

from vaybooks.bms.ui.components.shared.alerts import alert, empty_state, toast
from vaybooks.bms.ui.components.shared.badges import badge, badge_row
from vaybooks.bms.ui.components.shared.card import CardAction, card
from vaybooks.bms.ui.components.shared.dialog import dialog_footer, dialog_header
from vaybooks.bms.ui.components.shared.forms import (
    checkbox_field,
    date_field,
    multiselect_field,
    number_field,
    password_field,
    select_field,
    text_field,
    textarea_field,
)
from vaybooks.bms.ui.components.shared.nav import avatar, breadcrumb, chip
from vaybooks.bms.ui.components.shared.page_loader import page_loader
from vaybooks.bms.ui.components.shared.topbar import render_topbar
from vaybooks.bms.ui.theme.icons import icon_caption, icon_html

__all__ = [
    "alert",
    "avatar",
    "badge",
    "badge_row",
    "breadcrumb",
    "card",
    "CardAction",
    "checkbox_field",
    "chip",
    "date_field",
    "dialog_footer",
    "dialog_header",
    "empty_state",
    "icon_caption",
    "icon_html",
    "multiselect_field",
    "number_field",
    "page_loader",
    "password_field",
    "render_topbar",
    "select_field",
    "text_field",
    "textarea_field",
    "toast",
]
