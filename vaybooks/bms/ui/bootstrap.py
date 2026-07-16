import logging
import streamlit as st

from vaybooks.bms.application.business_app_service import BusinessAppService
from vaybooks.bms.application.customer_app_service import CustomerAppService
from vaybooks.bms.application.vendor_app_service import VendorAppService
from vaybooks.bms.application.delivery_app_service import DeliveryAppService
from vaybooks.bms.application.expense_app_service import ExpenseAppService
from vaybooks.bms.application.export_app_service import ExportAppService
from vaybooks.bms.application.migration_app_service import MigrationAppService
from vaybooks.bms.application.invoice_app_service import InvoiceAppService
from vaybooks.bms.application.order_app_service import OrderAppService
from vaybooks.bms.application.report_app_service import ReportAppService
from vaybooks.bms.application.reports import (
    BusinessInsightsReportService,
    CustomerReportService,
    LaborReportService,
    OperationsReportService,
    ProfitabilityReportService,
)
from vaybooks.bms.application.reports.inventory_report_service import (
    InventoryReportService,
)
from vaybooks.bms.application.reports.purchase_report_service import (
    PurchaseReportService,
)
from vaybooks.bms.application.reports.sales_report_service import SalesReportService
from vaybooks.bms.application.time_tracking_app_service import TimeTrackingAppService
from vaybooks.bms.application.accounting_app_service import AccountingAppService
from vaybooks.bms.application.activity_app_service import ActivityAppService
from vaybooks.bms.application.vendor_service_app_service import VendorServiceAppService
from vaybooks.bms.application.inventory_app_service import InventoryAppService
from vaybooks.bms.application.purchase_app_service import PurchaseAppService
from vaybooks.bms.application.sales_app_service import SalesAppService
from vaybooks.bms.application.worker_app_service import WorkerAppService
from vaybooks.bms.domain.inventory.rate_history_service import ProductRateHistoryService
from vaybooks.bms.infrastructure.db.connection import get_database
from vaybooks.bms.infrastructure.db.indexes import ensure_indexes
from vaybooks.bms.infrastructure.db.migrations.runner import run_pending_migrations
from vaybooks.bms.infrastructure.config.settings import get_settings, reload_settings
from vaybooks.bms.infrastructure.db.purge import purge_business_data
from vaybooks.bms.infrastructure.db.seed import run_seed
from vaybooks.bms.infrastructure.logging.setup import setup_logging
from vaybooks.bms.infrastructure.repositories.mongo_business_profile_repository import (
    MongoBusinessProfileRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_product_rate_history_repository import (
    MongoProductRateHistoryRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_purchase_price_history_repository import (
    MongoPurchasePriceHistoryRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_customer_price_repository import (
    MongoCustomerPriceRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_accounting_repository import (
    MongoAccountRepository,
    MongoVoucherRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_activity_repository import MongoActivityRepository
from vaybooks.bms.infrastructure.repositories.mongo_counter_repository import MongoCounterRepository
from vaybooks.bms.infrastructure.repositories.mongo_customer_repository import MongoCustomerRepository
from vaybooks.bms.infrastructure.repositories.mongo_vendor_repository import MongoVendorRepository
from vaybooks.bms.infrastructure.repositories.mongo_vendor_service_repository import (
    MongoVendorServiceRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_worker_repository import (
    MongoWorkerRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_delivery_repository import MongoDeliveryRepository
from vaybooks.bms.infrastructure.repositories.mongo_expense_repository import MongoExpenseRepository
from vaybooks.bms.infrastructure.repositories.mongo_invoice_repository import MongoInvoiceRepository
from vaybooks.bms.infrastructure.repositories.mongo_order_repository import (
    MongoBillRegistryRepository,
    MongoOrderRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_report_repository import MongoReportRepository
from vaybooks.bms.infrastructure.repositories.mongo_inventory_repository import (
    MongoInventoryProductRepository,
    MongoProductCategoryRepository,
    MongoProductFieldDefinitionRepository,
    MongoProductUnitRepository,
    MongoStockMovementRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_import_mapping_profile_repository import (
    MongoImportMappingProfileRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_purchase_repository import (
    MongoGoodsReceiptRepository,
    MongoPurchaseOrderRepository,
    MongoPurchaseReturnRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_sales_repository import (
    MongoDeliveryNoteRepository,
    MongoEstimateRepository,
    MongoQuotationRepository,
    MongoSalesOrderRepository,
    MongoSalesReturnRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_time_tracking_repository import (
    MongoTimeTrackingRepository,
)


logger = logging.getLogger("vaybooks.bms.bootstrap")


@st.cache_resource
def _bootstrap_db():
    """Create indexes and seed defaults exactly once per process.

    Previously this ran on every rerun/page render, firing ~40 create_index
    round-trips plus several seed queries to Atlas each time — the dominant
    cause of slow page loads. Caching the resource makes it run only once.
    """
    setup_logging()
    reload_settings()
    settings = get_settings()
    logger.info(
        "Bootstrap seed settings: seed_config=%s seed_qa_fixtures=%s purge_business_data=%s db=%s",
        settings.seed_config,
        settings.seed_qa_fixtures,
        settings.purge_business_data,
        settings.db_name,
    )
    db = get_database()
    run_pending_migrations(db)
    ensure_indexes(db)
    if settings.purge_business_data:
        purge_business_data(db)
    if settings.seed_config:
        run_seed(db)
    if settings.seed_qa_fixtures:
        from vaybooks.bms.infrastructure.db.qa_fixtures import run_qa_fixtures

        run_qa_fixtures(db)
    return db


@st.cache_resource
def get_services():
    db = _bootstrap_db()

    customer_repo = MongoCustomerRepository(db)
    vendor_repo = MongoVendorRepository(db)
    vendor_service_repo = MongoVendorServiceRepository(db)
    account_repo = MongoAccountRepository(db)
    voucher_repo = MongoVoucherRepository(db)
    order_repo = MongoOrderRepository(db)
    bill_registry_repo = MongoBillRegistryRepository(db)
    activity_repo = MongoActivityRepository(db)
    worker_repo = MongoWorkerRepository(db)
    time_repo = MongoTimeTrackingRepository(db)
    expense_repo = MongoExpenseRepository(db)
    invoice_repo = MongoInvoiceRepository(db)
    delivery_repo = MongoDeliveryRepository(db)
    counter_repo = MongoCounterRepository(db)
    report_repo = MongoReportRepository(db)
    category_repo = MongoProductCategoryRepository(db)
    unit_repo = MongoProductUnitRepository(db)
    field_def_repo = MongoProductFieldDefinitionRepository(db)
    inventory_product_repo = MongoInventoryProductRepository(db)
    stock_movement_repo = MongoStockMovementRepository(db)
    po_repo = MongoPurchaseOrderRepository(db)
    grn_repo = MongoGoodsReceiptRepository(db)
    purchase_return_repo = MongoPurchaseReturnRepository(db)
    so_repo = MongoSalesOrderRepository(db)
    dn_repo = MongoDeliveryNoteRepository(db)
    sales_return_repo = MongoSalesReturnRepository(db)
    estimate_repo = MongoEstimateRepository(db)
    quotation_repo = MongoQuotationRepository(db)
    business_profile_repo = MongoBusinessProfileRepository(db)
    price_history_repo = MongoPurchasePriceHistoryRepository(db)
    customer_price_repo = MongoCustomerPriceRepository(db)
    selling_rate_history_repo = MongoProductRateHistoryRepository(
        db, "product_selling_rate_history"
    )
    mrp_history_repo = MongoProductRateHistoryRepository(db, "product_mrp_history")
    gst_rate_history_repo = MongoProductRateHistoryRepository(db, "product_gst_rate_history")
    rate_history = ProductRateHistoryService(
        selling_rate_history_repo,
        mrp_history_repo,
        gst_rate_history_repo,
    )
    mapping_profile_repo = MongoImportMappingProfileRepository(db)

    accounting_service = AccountingAppService(account_repo, voucher_repo, counter_repo)
    customer_service = CustomerAppService(customer_repo, account_repo)
    vendor_service = VendorAppService(vendor_repo, account_repo)
    business_service = BusinessAppService(business_profile_repo)
    vendor_services_config = VendorServiceAppService(vendor_service_repo)

    reports_business = BusinessInsightsReportService(
        report_repo, accounting_service, vendor_service, customer_service
    )
    reports_profitability = ProfitabilityReportService(report_repo)
    reports_operations = OperationsReportService(report_repo)
    reports_labor = LaborReportService(report_repo)
    reports_customers = CustomerReportService(report_repo)
    reports_sales = SalesReportService(report_repo)
    inventory_service = InventoryAppService(
        category_repo,
        inventory_product_repo,
        stock_movement_repo,
        unit_repo,
        field_def_repo,
        rate_history,
    )
    migration_service = MigrationAppService(
        mapping_profile_repo,
        customer_service,
        vendor_service,
        inventory_service,
        accounting_service,
    )
    purchase_service = PurchaseAppService(
        po_repo,
        grn_repo,
        purchase_return_repo,
        counter_repo,
        accounting_service,
        inventory_service,
        vendor_service=vendor_service,
        vendor_services_config=vendor_services_config,
        business_service=business_service,
        price_history_repo=price_history_repo,
    )
    reports_inventory = InventoryReportService(inventory_service)
    reports_purchases = PurchaseReportService(purchase_service)
    sales_service = SalesAppService(
        so_repo,
        dn_repo,
        sales_return_repo,
        counter_repo,
        accounting_service,
        inventory_service,
        customer_service=customer_service,
        business_service=business_service,
        estimate_repo=estimate_repo,
        quotation_repo=quotation_repo,
        customer_price_repo=customer_price_repo,
    )
    report_facade = ReportAppService(
        report_repo,
        reports_business,
        reports_profitability,
        reports_operations,
        reports_labor,
        reports_customers,
        reports_sales,
        inventory_reports=reports_inventory,
    )

    invoice_service = InvoiceAppService(
        invoice_repo,
        order_repo,
        expense_repo,
        counter_repo,
        delivery_repo,
        accounting_service=accounting_service,
    )

    expense_service = ExpenseAppService(
        expense_repo,
        order_repo,
        invoice_service=invoice_service,
        invoice_repo=invoice_repo,
        delivery_repo=delivery_repo,
        time_repo=time_repo,
    )

    return {
        "customers": customer_service,
        "vendors": vendor_service,
        "vendor_services": vendor_services_config,
        "business": business_service,
        "orders": OrderAppService(
            order_repo,
            bill_registry_repo,
            customer_repo,
            account_repo,
            activity_repo,
            time_repo,
            expense_repo,
            voucher_repo,
            counter_repo,
            invoice_repo=invoice_repo,
            delivery_repo=delivery_repo,
            accounting_service=accounting_service,
        ),
        "activities": ActivityAppService(activity_repo, order_repo),
        "workers": WorkerAppService(worker_repo, account_repo),
        "time_tracking": TimeTrackingAppService(time_repo, order_repo),
        "expenses": expense_service,
        "invoices": invoice_service,
        "deliveries": DeliveryAppService(
            delivery_repo, order_repo, invoice_repo, expense_repo
        ),
        "accounting": accounting_service,
        "reports_business": reports_business,
        "reports_profitability": reports_profitability,
        "reports_operations": reports_operations,
        "reports_labor": reports_labor,
        "reports_customers": reports_customers,
        "reports_inventory": reports_inventory,
        "reports": report_facade,
        "export": ExportAppService(report_repo),
        "migration": migration_service,
        "inventory": inventory_service,
        "purchases": purchase_service,
        "sales": sales_service,
        "reports_purchases": reports_purchases,
        "activity_repo": activity_repo,
        "order_repo": order_repo,
        "invoice_repo": invoice_repo,
        "delivery_repo": delivery_repo,
    }
