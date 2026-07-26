"""List schemas for Production pages."""

from vaybooks.bms.domain.shared.enums import ProductionBatchStatus
from vaybooks.bms.ui import filtering as F
from vaybooks.bms.ui.filtering import FilterField, ListSchema, SortOption
from vaybooks.bms.ui.pagination import CARD_PAGE_SIZE


PRODUCTION_RECIPES = ListSchema(
    entity_key="production_recipes",
    title="Production Recipes",
    filter_fields=[
        FilterField("name", "Recipe name", F.REGEX),
        FilterField("code", "Code", F.REGEX),
    ],
    sort_options=[
        SortOption("name", "Recipe name"),
        SortOption("updated_at", "Updated"),
    ],
    default_sort="name",
    page_size=CARD_PAGE_SIZE,
)

PRODUCTION_BATCHES = ListSchema(
    entity_key="production_batches",
    title="Production Batches",
    filter_fields=[
        FilterField("batch_number", "Batch number", F.REGEX),
        FilterField(
            "status",
            "Status",
            F.MULTISELECT,
            options=[(item.value, item.value) for item in ProductionBatchStatus],
        ),
        FilterField("batch_date", "Batch date", F.DATE_RANGE),
    ],
    sort_options=[
        SortOption("batch_date", "Batch date"),
        SortOption("batch_number", "Batch number"),
        SortOption("total_cost", "Total cost"),
        SortOption("batch_margin", "Margin"),
    ],
    default_sort="batch_date",
    page_size=CARD_PAGE_SIZE,
)
