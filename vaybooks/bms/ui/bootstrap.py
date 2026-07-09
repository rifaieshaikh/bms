import streamlit as st

from vaybooks.bms.application.customer_app_service import CustomerAppService
from vaybooks.bms.application.vendor_app_service import VendorAppService
from vaybooks.bms.application.delivery_app_service import DeliveryAppService
from vaybooks.bms.application.expense_app_service import ExpenseAppService
from vaybooks.bms.application.export_app_service import ExportAppService
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
from vaybooks.bms.application.time_tracking_app_service import TimeTrackingAppService
from vaybooks.bms.application.accounting_app_service import AccountingAppService
from vaybooks.bms.application.activity_app_service import ActivityAppService
from vaybooks.bms.application.vendor_service_app_service import VendorServiceAppService
from vaybooks.bms.application.worker_app_service import WorkerAppService
from vaybooks.bms.infrastructure.db.connection import get_database
from vaybooks.bms.infrastructure.db.indexes import ensure_indexes
from vaybooks.bms.infrastructure.db.migrations.runner import run_pending_migrations
from vaybooks.bms.infrastructure.db.seed import run_seed
from vaybooks.bms.infrastructure.logging.setup import setup_logging
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
from vaybooks.bms.infrastructure.repositories.mongo_time_tracking_repository import (
    MongoTimeTrackingRepository,
)


@st.cache_resource
def _bootstrap_db():
    """Create indexes and seed defaults exactly once per process.

    Previously this ran on every rerun/page render, firing ~40 create_index
    round-trips plus several seed queries to Atlas each time — the dominant
    cause of slow page loads. Caching the resource makes it run only once.
    """
    setup_logging()
    db = get_database()
    run_pending_migrations(db)
    ensure_indexes(db)
    run_seed(db)
    from vaybooks.bms.infrastructure.db.qa_fixtures import ensure_cash_drawer_account

    ensure_cash_drawer_account(db)
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

    accounting_service = AccountingAppService(account_repo, voucher_repo, counter_repo)
    customer_service = CustomerAppService(customer_repo, account_repo)
    vendor_service = VendorAppService(vendor_repo, account_repo)

    reports_business = BusinessInsightsReportService(
        report_repo, accounting_service, vendor_service, customer_service
    )
    reports_profitability = ProfitabilityReportService(report_repo)
    reports_operations = OperationsReportService(report_repo)
    reports_labor = LaborReportService(report_repo)
    reports_customers = CustomerReportService(report_repo)
    report_facade = ReportAppService(
        report_repo,
        reports_business,
        reports_profitability,
        reports_operations,
        reports_labor,
        reports_customers,
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
        "vendor_services": VendorServiceAppService(vendor_service_repo),
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
        ),
        "activities": ActivityAppService(activity_repo, order_repo),
        "workers": WorkerAppService(worker_repo),
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
        "reports": report_facade,
        "export": ExportAppService(report_repo),
        "activity_repo": activity_repo,
        "order_repo": order_repo,
        "invoice_repo": invoice_repo,
        "delivery_repo": delivery_repo,
    }
