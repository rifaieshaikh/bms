"""Back-compat redirect: Warehouses now live at Settings -> Locations.

Kept as a thin wrapper so old bookmarks / deep links to ``inventory-warehouses``
keep working. The page is no longer listed under the Inventory sidebar group.
"""

from __future__ import annotations

from vaybooks.bms.ui.pages.settings.locations import list as settings_locations_list


def render(services: dict) -> None:
    settings_locations_list.render(services)
