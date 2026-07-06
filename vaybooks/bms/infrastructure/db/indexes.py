from pymongo.errors import OperationFailure


def _normalize_index_key(key):
    if isinstance(key, str):
        return {key: 1}
    return dict(key) if key else {}


def _create_index(collection, keys, **kwargs):
    """Create an index, dropping and recreating on option conflicts."""
    try:
        collection.create_index(keys, **kwargs)
    except OperationFailure as exc:
        if exc.code != 86:  # IndexKeySpecsConflict
            raise
        key_spec = _normalize_index_key(keys)
        for index in collection.list_indexes():
            if _normalize_index_key(index.get("key")) == key_spec:
                collection.drop_index(index["name"])
                break
        collection.create_index(keys, **kwargs)


def ensure_indexes(db):
    _create_index(db.customers, "phone_number", unique=True, sparse=True)
    _create_index(db.vendors, "phone_number", unique=True, sparse=True)
    # One account per customer / vendor. Partial filter on string values excludes
    # the null link shared by all other accounts.
    _create_index(
        db.accounts,
        [("linked_customer_id", 1)],
        unique=True,
        partialFilterExpression={"linked_customer_id": {"$type": "string"}},
    )
    _create_index(
        db.accounts,
        [("linked_vendor_id", 1)],
        unique=True,
        partialFilterExpression={"linked_vendor_id": {"$type": "string"}},
    )

    _create_index(db.customization_orders, "order_number", unique=True)
    _create_index(db.customization_orders, "customer_id")
    _create_index(db.customization_orders, "phone_number")
    _create_index(db.customization_orders, "order_status")
    _create_index(db.customization_orders, "expected_delivery_date")
    _create_index(db.customization_orders, "order_date")
    _create_index(db.customization_orders, "delivery_date")
    _create_index(db.customization_orders, "customization_items.mph_snapshot_at")
    _create_index(db.customization_orders, [("customer_id", 1), ("order_date", -1)])
    _create_index(
        db.customization_orders,
        [("order_status", 1), ("expected_delivery_date", 1)],
    )

    _create_index(db.bill_registry, "bill_number", unique=True)
    _create_index(db.bill_registry, "order_id")

    _create_index(db.activity_config, "activity_name", unique=True)

    _create_index(db.vendor_services, "service_name", unique=True)

    _create_index(db.time_entries, "order_id")
    _create_index(db.time_entries, "bill_number")
    _create_index(db.time_entries, "activity_id")
    _create_index(db.time_entries, "work_date")
    _create_index(db.time_entries, [("work_date", 1), ("activity_id", 1)])

    _create_index(db.expenses, "order_id")
    _create_index(db.expenses, "bill_number")
    _create_index(db.expenses, "activity_id")
    _create_index(db.expenses, "bill_id")
    _create_index(db.expenses, "expense_date")
    _create_index(db.expenses, [("expense_date", 1), ("expense_source", 1)])

    _create_index(db.invoices, "order_id")
    _create_index(db.invoices, "bill_ids")
    _create_index(db.invoices, "invoice_number", unique=True, sparse=True)
    _create_index(db.invoices, "invoice_date")

    _create_index(db.deliveries, "order_id")
    _create_index(db.deliveries, "bill_ids")
    _create_index(db.deliveries, "delivery_date")

    _create_index(db.vouchers, "voucher_number", unique=True)
    _create_index(db.vouchers, "voucher_date")
    _create_index(db.vouchers, "reference_order_id")


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
        ensure_indexes(database)
        print("Indexes created successfully")
