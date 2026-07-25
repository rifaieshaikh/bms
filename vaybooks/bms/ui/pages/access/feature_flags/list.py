"""Access — Feature flags: card list with enable/disable."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.domain.entitlements.catalog import MODULE_LABELS, permission_module
from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.ui.auth.guard import require_page_access
from vaybooks.bms.ui.components.common.list_view import render_list
from vaybooks.bms.ui.filtering import FilterField, ListSchema, SortOption
from vaybooks.bms.ui import filtering as F
from vaybooks.bms.ui.pagination import CARD_PAGE_SIZE
from vaybooks.bms.ui.styles import render_card_grid, status_badge


def _match_enabled(flag, _value) -> bool:
    return bool(getattr(flag, "enabled", False))


def _match_module(flag, value) -> bool:
    return permission_module(getattr(flag, "key", "")) == value


def _module_options():
    return [(m, MODULE_LABELS.get(m, m)) for m in sorted(MODULE_LABELS)]


FLAGS = ListSchema(
    entity_key="access_feature_flags",
    title="Feature flags",
    filter_fields=[
        FilterField("key", "Key", F.REGEX),
        FilterField(
            "module",
            "Module",
            F.SELECT,
            options=_module_options(),
            match=_match_module,
        ),
        FilterField(
            "enabled_only",
            "Enabled only",
            F.CHECKBOX,
            match=_match_enabled,
        ),
    ],
    sort_options=[
        SortOption("key", "Key"),
        SortOption("updated_at", "Updated"),
    ],
    default_sort="key",
    default_desc=False,
    page_size=CARD_PAGE_SIZE,
)


def _flag_card(flag, index: int, flags_svc) -> None:
    with st.container(border=True):
        st.markdown(f"**{flag.key}**")
        module = permission_module(flag.key)
        st.caption(MODULE_LABELS.get(module, module))
        badge = status_badge(
            "On" if flag.enabled else "Off",
            "green" if flag.enabled else "gray",
            compact=True,
        )
        st.markdown(badge, unsafe_allow_html=True)
        if flag.description and flag.description != flag.key:
            st.caption(flag.description)

        label = "Disable" if flag.enabled else "Enable"
        if st.button(
            label,
            key=f"access_flag_toggle_{index}_{flag.key}",
            use_container_width=True,
            type="primary" if not flag.enabled else "secondary",
        ):
            try:
                flags_svc.set_enabled(flag.key, not flag.enabled)
                st.rerun()
            except ValidationError as exc:
                st.error(str(exc))


def _load_flags(services, filters, sort):
    try:
        return services["feature_flags"].list_flags()
    except Exception:
        return []


def _render_cards(page_flags, services):
    flags_svc = services["feature_flags"]
    render_card_grid(
        page_flags,
        lambda flag, i: _flag_card(flag, i, flags_svc),
        suffix="access_feature_flags",
        card_min_width=240,
    )


def render(services: dict):
    if not require_page_access(services, "feature-flags-settings"):
        return

    render_list(
        FLAGS,
        services=services,
        load_fn=_load_flags,
        card_renderer=_render_cards,
        count_label="flags",
        empty_text="No feature flags found.",
        page_key_nav="feature_flags_settings",
    )
