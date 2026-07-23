"""Map pressed physical chord → parent navigate or queued action flags."""

from __future__ import annotations

from vaybooks.bms.ui.keyboard.actions import queue_action
from vaybooks.bms.ui.keyboard.bindings import get_bindings
from vaybooks.bms.ui.keyboard.capture import activate_shortcuts, pressed_chord
from vaybooks.bms.ui.keyboard.chords import normalize_chord
from vaybooks.bms.ui.keyboard.context import (
    get_current_page,
    is_dialog_armed,
    is_filters_ui_open,
    is_form_editing,
    is_sort_ui_open,
)
from vaybooks.bms.ui.keyboard.dialog_actions import armed_submit_key, request_submit
from vaybooks.bms.ui.keyboard.wired import clear_wired


# Pages that own export CSV shortcuts (not migration parents).
_EXPORT_PAGE = "export_backup"
_PO_DETAIL = "purchase_order_detail"
_MTD_PAGE = "mtd_dashboard"
_ORDER_DETAIL = "order_detail"


def _invert(mapping: dict[str, str]) -> dict[str, list[str]]:
    inv: dict[str, list[str]] = {}
    for key, chord in mapping.items():
        n = normalize_chord(chord)
        if not n:
            continue
        inv.setdefault(n, []).append(key)
    return inv


def _pick_action(chord: str, action_ids: list[str], page: str | None) -> str | None:
    """Choose one action_id for a shared chord given context."""
    if not action_ids:
        return None

    # dialog.save / create wins when dialog armed and chord is ctrl+s
    if is_dialog_armed() and chord == "ctrl+s":
        if "dialog.save" in action_ids:
            return "dialog.save"
        for aid in action_ids:
            if aid.endswith(".save") or aid.endswith(".create") or aid.endswith(".confirm"):
                return aid

    # Form line editing
    if is_form_editing():
        if chord == "ctrl+shift+backspace" and "form.remove_line" in action_ids:
            return "form.remove_line"
        if chord == "ctrl+shift+." and "form.add_line" in action_ids:
            return "form.add_line"

    # Filters dialog open
    if is_filters_ui_open():
        if chord == "ctrl+enter" and "list.filters.apply" in action_ids:
            return "list.filters.apply"

    # Page-specific context
    if page == _EXPORT_PAGE:
        for aid in action_ids:
            if aid.startswith("export."):
                return aid
    if page == _PO_DETAIL:
        if chord == "ctrl+p" and "purchases.orders.print" in action_ids:
            return "purchases.orders.print"
        if "purchases.orders.receive" in action_ids:
            return "purchases.orders.receive"
    if page == _MTD_PAGE:
        for aid in action_ids:
            if aid.startswith("dashboard.period."):
                return aid
    if page == _ORDER_DETAIL:
        for aid in (
            "orders.record_invoice",
            "orders.record_delivery",
            "orders.record_receipt",
            "orders.record_payment",
            "orders.record_refund",
            "orders.mark_complete",
            "orders.cancel",
        ):
            if aid in action_ids:
                # Prefer the one that matches this chord uniquely among order actions
                pass
        matching = [a for a in action_ids if a.startswith("orders.")]
        if len(matching) == 1:
            return matching[0]
        if matching:
            # Prefer record_* over others when multiple match same chord (shouldn't)
            return matching[0]

    # List clear actions (ctrl+1 / ctrl+2) — only when panels closed and not
    # claimed by order-detail / MTD above.
    if not is_filters_ui_open() and not is_sort_ui_open():
        if chord == "ctrl+1" and "list.filters.clear" in action_ids:
            return "list.filters.clear"
        if chord == "ctrl+2" and "list.sort.clear" in action_ids:
            return "list.sort.clear"

    # Prefer shared list roles when on any list
    for preferred in (
        "list.primary",
        "list.filters.open",
        "list.sort.open",
        "list.prev_page",
        "list.next_page",
        "nav.back",
        "dialog.open_existing",
    ):
        if preferred in action_ids:
            return preferred

    # Nth card
    for aid in action_ids:
        if aid.startswith("list.view_nth.") or aid.startswith("list.edit_nth."):
            return aid

    # Do not fall through to clear-filter/sort while a panel is open.
    filtered = [
        aid
        for aid in action_ids
        if aid not in ("list.filters.clear", "list.sort.clear")
        or (not is_filters_ui_open() and not is_sort_ui_open())
    ]
    if filtered:
        return filtered[0]
    return None


def _navigate_parent(nav_key: str) -> bool:
    from vaybooks.bms.ui import navigation
    import streamlit as st

    target = navigation.page(nav_key)
    if target is None:
        return False
    st.switch_page(target)
    return True


def resolve_pressed_shortcuts() -> None:
    """Activate hotkeys, clear wired set, apply parent or queue actions.

    Call early in ``app.py`` before ``nav.run()``. Parents navigate immediately.
    Actions only set session flags for page render to consume.
    """
    clear_wired()
    activate_shortcuts()

    chord = pressed_chord()
    if not chord or chord == "escape":
        return

    bindings = get_bindings()
    parents_by_chord = _invert(bindings["parents"])
    actions_by_chord = _invert(bindings["actions"])
    page = get_current_page()

    # Precedence: dialog submit
    if is_dialog_armed() and chord == normalize_chord(
        bindings["actions"].get("dialog.save", "ctrl+s")
    ):
        submit = armed_submit_key()
        if submit:
            request_submit(submit)
            queue_action("dialog.save")
            return

    action_ids = actions_by_chord.get(chord) or []
    parent_keys = parents_by_chord.get(chord) or []

    # Context actions beat parents when both claim the chord
    chosen = _pick_action(chord, action_ids, page)
    if chosen:
        # list.sort.open only when NOT dialog-armed (already handled above for save)
        if chosen == "list.sort.open" and is_dialog_armed():
            submit = armed_submit_key()
            if submit:
                request_submit(submit)
                queue_action("dialog.save")
                return
        if chosen == "dialog.save":
            submit = armed_submit_key()
            if submit:
                request_submit(submit)
            queue_action(chosen)
            return
        queue_action(chosen)
        # Also queue list.primary aliases when primary fires
        if chosen == "list.primary":
            pass
        return

    if parent_keys:
        _navigate_parent(parent_keys[0])
