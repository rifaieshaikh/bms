"""List schemas for Boutique module pages (Overview)."""

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


BOUTIQUE_OVERVIEW = ListSchema(
    entity_key="boutique_overview",
    title="Boutique Overview",
    filter_fields=[
        FilterField(
            "date_range",
            "Period",
            F.DATE_RANGE,
            default=_mtd,
            help="Applies to invoiced revenue, logged hours, and dated charts.",
        ),
    ],
    sort_options=[
        SortOption("date_range", "Period"),
    ],
    default_sort="date_range",
    page_size=12,
)
