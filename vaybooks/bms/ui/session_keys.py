import streamlit as st

PENDING_EDIT_ITEM = "pending_edit_customization_item"
ACTIVITY_SKIP_NOTICE = "activity_skip_notice"


def filters_key(entity: str) -> str:
    return f"filters.{entity}"


def sort_key(entity: str) -> str:
    return f"sort.{entity}"


def page_state_key(entity: str) -> str:
    return f"{entity}_page"


def clear_list_state(entity: str) -> None:
    """Reset filters, sort, and pagination for a list entity (Back button)."""
    keys = [
        filters_key(entity),
        sort_key(entity),
        page_state_key(entity),
        f"{page_state_key(entity)}_last_filter",
    ]
    # Widget-bound filter/sort keys used by the popovers.
    prefix = f"{entity}_flt_"
    keys.extend([k for k in list(st.session_state.keys()) if k.startswith(prefix)])
    keys.append(f"{entity}_sort_field")
    keys.append(f"{entity}_sort_dir")
    for key in keys:
        st.session_state.pop(key, None)
