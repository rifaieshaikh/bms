"""Deep-link helpers: open a CRM list page with filters pre-applied."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.ui import filtering as F
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.filtering import ListSchema
from vaybooks.bms.ui.session_keys import clear_list_state, filters_key


def seed_filters(schema: ListSchema, overrides: dict) -> dict:
    """Replace the committed filters for ``schema`` with defaults + overrides.

    Widget state is cleared first so the filter dialog re-seeds from the new
    committed values on the next render.
    """
    clear_list_state(schema.entity_key)
    filters = F.default_filters(schema)
    filters.update(overrides)
    st.session_state[filters_key(schema.entity_key)] = filters
    return filters


def open_filtered_list(schema: ListSchema, page_key: str, overrides: dict) -> None:
    seed_filters(schema, overrides)
    navigation.go_to_list(page_key)
