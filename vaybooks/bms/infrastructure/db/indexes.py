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
    _create_index(db.customers, "gstin", unique=True, sparse=True)
    _create_index(db.vendors, "phone_number", unique=True, sparse=True)
    _create_index(db.vendors, "gstin", unique=True, sparse=True)
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
    _create_index(
        db.accounts,
        [("linked_worker_id", 1)],
        unique=True,
        partialFilterExpression={"linked_worker_id": {"$type": "string"}},
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

    _create_index(db.workers, "worker_name")
    _create_index(db.workers, "is_active")
    _create_index(db.workers, "activity_ids")

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

    _create_index(db.product_categories, [("parent_id", 1), ("name", 1)], unique=True)
    _create_index(db.product_categories, "name")
    _create_index(db.product_units, "code", unique=True)
    _create_index(db.product_units, "label")
    _create_index(db.product_field_definitions, "key", unique=True)
    _create_index(db.inventory_products, "sku", unique=True)
    _create_index(db.inventory_products, "category_id")
    _create_index(db.inventory_products, "category_ids")
    _create_index(db.inventory_products, "unit_id")
    _create_index(db.stock_movements, "product_id")
    _create_index(db.stock_movements, "movement_date")
    _create_index(db.stock_movements, "movement_type")
    _create_index(db.stock_movements, "reference_id")

    _create_index(db.purchase_orders, "po_number", unique=True)
    _create_index(db.purchase_orders, "vendor_id")
    _create_index(db.purchase_orders, "order_date")
    _create_index(db.purchase_orders, "status")

    _create_index(db.goods_receipts, "grn_number", unique=True)
    _create_index(db.goods_receipts, "purchase_order_id")
    _create_index(db.goods_receipts, "vendor_id")
    _create_index(db.goods_receipts, "receipt_date")

    _create_index(db.purchase_returns, "return_number", unique=True)
    _create_index(db.purchase_returns, "vendor_id")
    _create_index(db.purchase_returns, "return_date")

    _create_index(db.sales_orders, "so_number", unique=True)
    _create_index(db.sales_orders, "customer_id")
    _create_index(db.sales_orders, "order_date")
    _create_index(db.sales_orders, "status")

    _create_index(db.delivery_notes, "dn_number", unique=True)
    _create_index(db.delivery_notes, "sales_order_id")
    _create_index(db.delivery_notes, "customer_id")
    _create_index(db.delivery_notes, "delivery_date")

    _create_index(db.sales_returns, "return_number", unique=True)
    _create_index(db.sales_returns, "customer_id")
    _create_index(db.sales_returns, "return_date")

    _create_index(
        db.purchase_price_history,
        [("item_id", 1), ("item_type", 1), ("vendor_id", 1), ("purchase_date", -1)],
    )
    _create_index(db.product_selling_rate_history, [("product_id", 1), ("start_date", -1)])
    _create_index(db.product_mrp_history, [("product_id", 1), ("start_date", -1)])
    _create_index(db.product_gst_rate_history, [("product_id", 1), ("start_date", -1)])


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    from tests.qa.sync_execution_overrides import sync_execution_overrides

    sync_execution_overrides()

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
