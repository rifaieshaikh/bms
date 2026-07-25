"""List schemas for Finance module pages."""

from vaybooks.bms.ui.list_schemas import (
    F,
    FilterField,
    ListSchema,
    SortOption,
)


def _mtd():
    from datetime import date

    today = date.today()
    return today.replace(day=1), today


FINANCE_OVERVIEW = ListSchema(
    entity_key="finance_overview",
    title="Finance Overview",
    filter_fields=[
        FilterField(
            "date_range",
            "Period",
            F.DATE_RANGE,
            default=_mtd,
            help="Applies to invoiced, receipts, expenses, margin, and cash KPIs.",
        ),
    ],
    sort_options=[
        SortOption("date_range", "Period"),
    ],
    default_sort="date_range",
    page_size=12,
)
