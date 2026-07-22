"""One-off backfill of per-item MPH snapshots.

Freezes `margin_per_hour` / `margin_amount` on every customization item that is
both invoiced and delivered but has no snapshot yet. Safe to re-run: items that
are already snapshotted are simply recomputed with the same inputs.

Usage:
    python -m vaybooks.bms.infrastructure.db.backfill_item_mph
"""

from pymongo.database import Database

from vaybooks.bms.domain.boutique.invoices.services import InvoiceDomainService
from vaybooks.bms.infrastructure.repositories.boutique.mongo_delivery_repository import (
    MongoDeliveryRepository,
)
from vaybooks.bms.infrastructure.repositories.boutique.mongo_expense_repository import (
    MongoExpenseRepository,
)
from vaybooks.bms.infrastructure.repositories.boutique.mongo_invoice_repository import (
    MongoInvoiceRepository,
)
from vaybooks.bms.infrastructure.repositories.boutique.mongo_order_repository import (
    MongoOrderRepository,
)


def backfill_item_mph(db: Database) -> dict:
    order_repo = MongoOrderRepository(db)
    invoice_repo = MongoInvoiceRepository(db)
    delivery_repo = MongoDeliveryRepository(db)
    expense_repo = MongoExpenseRepository(db)

    orders_updated = 0
    items_snapshotted = 0

    for order in order_repo.list_all():
        invoices = invoice_repo.list_by_order(order.id)
        deliveries = delivery_repo.list_by_order(order.id)
        expenses = expense_repo.find_by_order(order.id)
        before = sum(1 for i in order.customization_items if i.mph_snapshot_at)
        changed = InvoiceDomainService.snapshot_order_items(
            order, invoices, deliveries, expenses
        )
        if changed:
            order_repo.save(order)
            orders_updated += 1
            after = sum(1 for i in order.customization_items if i.mph_snapshot_at)
            items_snapshotted += max(after - before, 0)

    return {"orders_updated": orders_updated, "items_snapshotted": items_snapshotted}


if __name__ == "__main__":
    import os

    from dotenv import load_dotenv

    load_dotenv()
    uri = os.getenv("MONGODB_URI")
    db_name = os.getenv("MONGODB_DATABASE", "zahcci_customization")
    if not uri:
        print("Set MONGODB_URI environment variable or use Streamlit secrets")
    else:
        from vaybooks.bms.infrastructure.db.connection import get_database_from_uri

        database = get_database_from_uri(uri, db_name)
        result = backfill_item_mph(database)
        print(
            f"Backfill complete: {result['orders_updated']} orders updated, "
            f"{result['items_snapshotted']} items snapshotted"
        )
