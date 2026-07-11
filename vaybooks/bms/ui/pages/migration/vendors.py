from vaybooks.bms.application.migration.schemas import ImportEntityType
from vaybooks.bms.ui.pages.migration.wizard import render_migration_wizard


def render(services: dict):
    render_migration_wizard(services, ImportEntityType.VENDORS)
