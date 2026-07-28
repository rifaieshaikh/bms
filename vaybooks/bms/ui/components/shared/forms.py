"""Labeled field wrappers with consistent conventions.

Each function passes straight through to the underlying Streamlit widget —
these exist to give every form the same ``key=``/``help=`` calling
convention, not to change widget behavior. Radio buttons, toggle switches,
tabs, file upload, progress bars, spinners, and accordions are native
Streamlit widgets already applied consistently by the framework itself; they
are themed via ``ui/theme/theme.css`` rather than wrapped here, since a
passthrough wrapper would add indirection with no behavior change.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Sequence

import streamlit as st

__all__ = [
    "checkbox_field",
    "date_field",
    "multiselect_field",
    "number_field",
    "password_field",
    "select_field",
    "text_field",
    "textarea_field",
]


def text_field(
    label: str,
    *,
    value: str = "",
    key: str,
    help: str | None = None,
    placeholder: str | None = None,
    disabled: bool = False,
) -> str:
    return st.text_input(
        label, value=value, key=key, help=help, placeholder=placeholder, disabled=disabled
    )


def textarea_field(
    label: str,
    *,
    value: str = "",
    key: str,
    help: str | None = None,
    placeholder: str | None = None,
    height: int | None = None,
) -> str:
    return st.text_area(
        label, value=value, key=key, help=help, placeholder=placeholder, height=height
    )


def password_field(
    label: str,
    *,
    value: str = "",
    key: str,
    help: str | None = None,
    placeholder: str | None = None,
) -> str:
    return st.text_input(
        label, value=value, key=key, help=help, placeholder=placeholder, type="password"
    )


def number_field(
    label: str,
    *,
    value: float | int | None = None,
    key: str,
    min_value: float | int | None = None,
    max_value: float | int | None = None,
    step: float | int | None = None,
    help: str | None = None,
    format: str | None = None,
) -> float | int:
    return st.number_input(
        label,
        value=value,
        key=key,
        min_value=min_value,
        max_value=max_value,
        step=step,
        help=help,
        format=format,
    )


def select_field(
    label: str,
    options: Sequence[Any],
    *,
    index: int | None = 0,
    key: str,
    help: str | None = None,
    format_func: Any = str,
    placeholder: str | None = None,
) -> Any:
    kwargs: dict[str, Any] = {}
    if placeholder is not None:
        kwargs["placeholder"] = placeholder
    return st.selectbox(
        label, options, index=index, key=key, help=help, format_func=format_func, **kwargs
    )


def multiselect_field(
    label: str,
    options: Sequence[Any],
    *,
    default: Sequence[Any] | None = None,
    key: str,
    help: str | None = None,
    format_func: Any = str,
) -> list:
    return st.multiselect(
        label, options, default=default, key=key, help=help, format_func=format_func
    )


def date_field(
    label: str,
    *,
    value: date | None = None,
    key: str,
    help: str | None = None,
    min_value: date | None = None,
    max_value: date | None = None,
) -> date:
    return st.date_input(
        label, value=value, key=key, help=help, min_value=min_value, max_value=max_value
    )


def checkbox_field(
    label: str,
    *,
    value: bool = False,
    key: str,
    help: str | None = None,
) -> bool:
    return st.checkbox(label, value=value, key=key, help=help)
