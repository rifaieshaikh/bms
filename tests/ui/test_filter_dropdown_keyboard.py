"""Filters dialog contracts: dropdown-only widgets + keyboard navigation."""

from __future__ import annotations

import inspect
from types import SimpleNamespace

from vaybooks.bms.domain.shared.enums import PartyRegistrationType
from vaybooks.bms.ui import filtering as F
from vaybooks.bms.ui import list_schemas as ls
from vaybooks.bms.ui import report_schemas as rs
from vaybooks.bms.ui.components.common import filter_focus_nav as nav
from vaybooks.bms.ui.components.common import filter_sort_bar as fsb
from vaybooks.bms.ui.keyboard.focus import engine as focus_engine

ALLOWED_FILTER_TYPES = {
    F.EXACT,
    F.REGEX,
    F.SELECT,
    F.ENTITY_SELECT,
    F.MULTISELECT,
    F.DATE,
    F.DATE_RANGE,
    F.NUMBER_MIN,
    F.CHECKBOX,
}


def _inject(monkeypatch) -> str:
    captured: dict = {}

    def _html(html, **kwargs):
        captured["html"] = html

    monkeypatch.setattr("vaybooks.bms.ui.components.common.filter_focus_nav.inject_html", _html)
    nav.inject_filters_chain_nav(
        chain=[
            "customers_flt_customer_name",
            "customers_flt_registration_type",
            "customers_flt_has_orders",
            "customers_clear_filters",
            "customers_apply_filters",
        ],
        apply_key="customers_apply_filters",
        clear_key="customers_clear_filters",
    )
    return captured["html"]


def _render_schema_filters(entity_key: str) -> None:
    from vaybooks.bms.ui import list_schemas as schemas
    from vaybooks.bms.ui.components.common import filter_sort_bar as bar

    bar._render_filter_widgets(schemas.SCHEMAS[entity_key], {}, None)


# --- widget kinds -----------------------------------------------------------
def test_filter_widgets_render_without_radios():
    from streamlit.testing.v1 import AppTest

    for entity_key in ("customers", "vendors", "items", "accounts", "orders"):
        at = AppTest.from_function(_render_schema_filters, args=(entity_key,))
        at.run(timeout=20)
        assert not at.exception, entity_key
        assert len(at.radio) == 0, entity_key
        assert len(at.multiselect) > 0, entity_key


def test_filter_widgets_never_render_radios():
    source = inspect.getsource(fsb._render_filter_widgets)
    assert "st.radio" not in source
    assert "st.multiselect" in source
    assert "st.selectbox" in source


def test_all_schemas_use_supported_filter_types():
    schemas = {**ls.SCHEMAS, **rs.SCHEMA_BY_REPORT_TYPE}
    for schema in schemas.values():
        for fld in schema.filter_fields:
            assert fld.type in ALLOWED_FILTER_TYPES, (schema.entity_key, fld.key)


def test_list_dropdowns_are_multi_select():
    schema = ls.SCHEMAS["customers"]
    for key in ("registration_type", "segment_id", "has_orders"):
        assert F.is_multi_select(schema.field(key))


def test_report_dropdowns_feeding_single_value_services_stay_single():
    schema = rs.SCHEMA_BY_REPORT_TYPE["Stock on Hand"]
    assert not F.is_multi_select(schema.field("category_id"))


def test_multi_select_defaults_to_empty_list():
    defaults = F.default_filters(ls.SCHEMAS["customers"])
    assert defaults["registration_type"] == []
    assert defaults["has_orders"] == []


# --- matching ---------------------------------------------------------------
def _customers():
    return [
        SimpleNamespace(
            customer_name="Alpha",
            registration_type=PartyRegistrationType.REGISTERED,
            order_count=2,
            segment_ids=["s1"],
        ),
        SimpleNamespace(
            customer_name="Beta",
            registration_type=PartyRegistrationType.UNREGISTERED,
            order_count=0,
            segment_ids=["s2"],
        ),
        SimpleNamespace(
            customer_name="Gamma",
            registration_type=PartyRegistrationType.COMPOSITION,
            order_count=1,
            segment_ids=[],
        ),
    ]


def test_multi_select_is_or_within_one_dropdown():
    schema = ls.SCHEMAS["customers"]
    filters = F.default_filters(schema)
    filters["registration_type"] = [
        PartyRegistrationType.REGISTERED.value,
        PartyRegistrationType.COMPOSITION.value,
    ]
    result = F.apply_filters(_customers(), schema, filters)
    assert [r.customer_name for r in result] == ["Alpha", "Gamma"]


def test_multi_select_fans_out_custom_match_predicates():
    schema = ls.SCHEMAS["customers"]
    filters = F.default_filters(schema)
    filters["has_orders"] = ["with", "without"]
    result = F.apply_filters(_customers(), schema, filters)
    assert len(result) == 3


def test_empty_multi_select_does_not_filter():
    schema = ls.SCHEMAS["customers"]
    filters = F.default_filters(schema)
    filters["registration_type"] = []
    assert len(F.apply_filters(_customers(), schema, filters)) == 3


def test_scalar_value_still_matches_for_deep_links():
    schema = ls.SCHEMAS["customers"]
    filters = F.default_filters(schema)
    filters["registration_type"] = PartyRegistrationType.REGISTERED.value
    result = F.apply_filters(_customers(), schema, filters)
    assert [r.customer_name for r in result] == ["Alpha"]


# --- keyboard nav -----------------------------------------------------------
def test_tab_never_intercepted(monkeypatch):
    html = _inject(monkeypatch)
    assert "if (ev.key === 'Tab') return;" in html


def test_space_never_intercepted(monkeypatch):
    html = _inject(monkeypatch)
    assert "if (ev.key === ' ') return;" in html


def test_open_dropdown_keeps_native_arrows_and_enter(monkeypatch):
    html = _inject(monkeypatch)
    assert "if (selectOpen(active)) return;" in html
    assert '[role="listbox"]' in html


def test_up_down_move_between_chain_fields(monkeypatch):
    html = _inject(monkeypatch)
    assert "moveChain(isDown ? 1 : -1)" in html


def test_enter_on_closed_dropdown_applies(monkeypatch):
    html = _inject(monkeypatch)
    assert "Closed dropdown: Enter applies" in html
    assert "clickApply" in html


def test_focus_styles_do_not_outline_dropdown_inputs(monkeypatch):
    html = _inject(monkeypatch)
    assert '[data-baseweb="select"] *:focus-visible' not in html
    assert "input:focus-visible" not in html
    assert 'data-testid="stRadio"' in html


def test_engine_defers_to_chain_nav_when_present():
    source = open(focus_engine.__file__, encoding="utf-8").read()
    assert "win.__vayFiltersChainNav" in source
    assert "never block Tab or Shift+Tab" in source


def test_filters_form_disables_enter_to_submit():
    source = open(fsb.__file__, encoding="utf-8").read()
    assert "enter_to_submit=False" in source
    assert "inject_filters_chain_nav" in source


def test_sort_dialog_keeps_multi_level_wiring():
    source = open(fsb.__file__, encoding="utf-8").read()
    assert "_sort_field_wkey" in source
    assert "Add sort level" in source
    assert "F.MAX_SORT_LEVELS" in source
