"""Unit tests for keyboard shortcut chords, bindings, and resolve helpers."""

from __future__ import annotations

from vaybooks.bms.ui.keyboard.chords import (
    chord_id,
    normalize_chord,
    parse_chord,
    RESERVED_LIST_CHILDREN,
)
from vaybooks.bms.ui.keyboard.defaults import (
    default_actions,
    default_parents,
    ensure_defaults_loaded,
)
from vaybooks.bms.ui.keyboard.bindings import (
    LOCKED_PARENTS,
    save_parent_binding,
)
from vaybooks.bms.ui.keyboard.resolve import _pick_action


def test_normalize_chord_basic():
    assert normalize_chord("Ctrl+X") == "ctrl+x"
    assert normalize_chord("ctrl + shift + o") == "ctrl+shift+o"
    assert normalize_chord("CTRL+,") == "ctrl+,"
    assert normalize_chord("ctrl+/") == "ctrl+/"
    assert normalize_chord("ctrl+shift+.") == "ctrl+shift+."


def test_chord_id():
    assert chord_id("ctrl+n") == "chord:ctrl+n"


def test_parse_chord_modifiers():
    p = parse_chord("ctrl+shift+o")
    assert p["ctrl"] and p["shift"] and not p["alt"]
    assert p["key"] == "o"
    p2 = parse_chord("alt+left")
    assert p2["alt"] and p2["key"] == "ArrowLeft"


def test_defaults_customers_locked():
    ensure_defaults_loaded(force=True)
    parents = default_parents()
    assert parents["customers_list"] == "ctrl+x"
    assert "customers_list" in LOCKED_PARENTS
    assert "ctrl+shift+n" in RESERVED_LIST_CHILDREN


def test_default_actions_include_list_roles():
    ensure_defaults_loaded(force=True)
    actions = default_actions()
    assert actions["list.primary"] == "ctrl+shift+n"
    assert actions["list.filters.open"] == "ctrl+shift+q"
    assert actions["list.sort.open"] == "ctrl+shift+s"
    assert actions["list.filters.clear"] == "ctrl+1"
    assert actions["list.sort.clear"] == "ctrl+2"
    assert actions["dialog.save"] == "ctrl+s"


def test_list_chords_do_not_collide_with_parents():
    ensure_defaults_loaded(force=True)
    parent_chords = set(default_parents().values())
    for aid in (
        "list.primary",
        "list.filters.open",
        "list.sort.open",
        "list.filters.clear",
        "list.sort.clear",
    ):
        chord = default_actions()[aid]
        assert chord not in parent_chords, f"{aid}={chord} collides with a parent"


def test_pick_action_export_page_prefers_export():
    chosen = _pick_action(
        "ctrl+alt+1",
        ["export.csv.customers", "something_else"],
        "export_backup",
    )
    assert chosen == "export.csv.customers"


def test_pick_action_po_detail_receive():
    chosen = _pick_action(
        "ctrl+g",
        ["purchases.orders.receive"],
        "purchase_order_detail",
    )
    assert chosen == "purchases.orders.receive"


def test_pick_action_list_clear_filters_on_list_page():
    chosen = _pick_action(
        "ctrl+1",
        ["list.filters.clear", "orders.record_invoice", "dashboard.period.today"],
        "customers_list",
    )
    assert chosen == "list.filters.clear"


def test_pick_action_list_clear_sort_on_list_page():
    chosen = _pick_action(
        "ctrl+2",
        ["list.sort.clear", "orders.record_delivery", "dashboard.period.last_7d"],
        "purchase_orders_list",
    )
    assert chosen == "list.sort.clear"


def test_pick_action_order_detail_keeps_ctrl_1_invoice():
    chosen = _pick_action(
        "ctrl+1",
        ["list.filters.clear", "orders.record_invoice"],
        "order_detail",
    )
    assert chosen == "orders.record_invoice"


def test_pick_action_mtd_keeps_ctrl_1_period():
    chosen = _pick_action(
        "ctrl+1",
        ["list.filters.clear", "dashboard.period.today"],
        "mtd_dashboard",
    )
    assert chosen == "dashboard.period.today"


def test_parents_do_not_use_reserved_list_children():
    ensure_defaults_loaded(force=True)
    for nav, chord in default_parents().items():
        assert chord not in RESERVED_LIST_CHILDREN, f"{nav} uses reserved {chord}"


def test_locked_parent_cannot_be_remapped():
    ok, err = save_parent_binding("customers_list", "ctrl+shift+x")
    assert not ok
    assert "locked" in err.lower()


def test_parent_cannot_use_reserved_list_chord():
    ok, err = save_parent_binding("vendors_list", "ctrl+shift+q")
    assert not ok
    assert "reserved" in err.lower()
