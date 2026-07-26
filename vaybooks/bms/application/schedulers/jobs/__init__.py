"""Domain scheduler jobs."""

from vaybooks.bms.application.schedulers.jobs.boutique_jobs import boutique_jobs
from vaybooks.bms.application.schedulers.jobs.crm_jobs import crm_jobs
from vaybooks.bms.application.schedulers.jobs.inventory_jobs import inventory_jobs
from vaybooks.bms.application.schedulers.jobs.project_jobs import project_jobs
from vaybooks.bms.application.schedulers.jobs.purchase_jobs import purchase_jobs
from vaybooks.bms.application.schedulers.jobs.production_jobs import production_jobs
from vaybooks.bms.application.schedulers.jobs.sales_jobs import sales_jobs

__all__ = [
    "boutique_jobs",
    "crm_jobs",
    "inventory_jobs",
    "project_jobs",
    "purchase_jobs",
    "production_jobs",
    "sales_jobs",
    "all_jobs",
]


def all_jobs(deps):
    """Every job in domain order, paired with its seed definition."""
    return (
        crm_jobs(deps)
        + sales_jobs(deps)
        + purchase_jobs(deps)
        + inventory_jobs(deps)
        + production_jobs(deps)
        + boutique_jobs(deps)
        + project_jobs(deps)
    )
