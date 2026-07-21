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
from vaybooks.bms.application.measurement_app_service import MeasurementAppService
from vaybooks.bms.application.attachment_app_service import AttachmentAppService
from vaybooks.bms.application.project_activity_config_app_service import ProjectActivityConfigAppService
from vaybooks.bms.application.project_app_service import ProjectAppService
from vaybooks.bms.application.project_boq_app_service import ProjectBoqAppService
from vaybooks.bms.application.project_budget_app_service import ProjectBudgetAppService
from vaybooks.bms.application.project_billing_app_service import ProjectBillingAppService
from vaybooks.bms.application.project_document_app_service import ProjectDocumentAppService
from vaybooks.bms.application.project_expense_app_service import ProjectExpenseAppService
from vaybooks.bms.application.project_measurement_app_service import ProjectMeasurementAppService
from vaybooks.bms.application.project_profitability_service import ProjectProfitabilityService
from vaybooks.bms.application.project_quotation_app_service import ProjectQuotationAppService
from vaybooks.bms.application.project_time_app_service import ProjectTimeAppService
from vaybooks.bms.application.reports.project_report_service import ProjectReportService
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
from vaybooks.bms.infrastructure.repositories.mongo_measurement_repository import (
    MongoMeasurementRecordRepository,
    MongoMeasurementSectionRepository,
    MongoMeasurementSpecRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_attachment_repository import (
    MongoAttachmentRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_project_document_repository import (
    MongoProjectDocumentRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_project_expense_repository import (
    MongoProjectExpenseRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_project_quotation_repository import (
    MongoProjectQuotationRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_project_repository import (
    MongoProjectRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_project_template_repository import (
    MongoProjectTemplateRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_project_time_entry_repository import (
    MongoProjectTimeEntryRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_project_work_order_repository import (
    MongoProjectWorkOrderRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_project_ra_repository import (
    MongoProjectRABillRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_project_proforma_repository import (
    MongoProjectProformaRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_project_variation_repository import (
    MongoProjectVariationRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_project_retention_repository import (
    MongoProjectRetentionRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_project_cost_transfer_repository import (
    MongoProjectCostTransferRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_project_write_off_repository import (
    MongoProjectWriteOffRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_project_boq_repository import (
    MongoProjectBoqRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_project_budget_repository import (
    MongoProjectBudgetRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_project_cash_flow_repository import (
    MongoProjectCashFlowRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_project_measurement_repository import (
    MongoProjectMeasurementRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_project_activity_config_repository import (
    MongoProjectActivityConfigRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_project_enquiry_repository import (
    MongoProjectEnquiryRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_project_dpr_repository import (
    MongoProjectDprRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_project_procurement_repository import (
    MongoProjectProcurementRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_project_subcontract_repository import (
    MongoProjectSubcontractRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_project_petty_cash_repository import (
    MongoProjectPettyCashRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_project_recognition_repository import (
    MongoProjectRecognitionRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_app_user_repository import (
    MongoAppUserRepository,
    MongoProjectMembershipRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_project_audit_repository import (
    MongoProjectAuditRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_project_quality_config_repository import (
    MongoProjectQualityConfigRepository,
)
from vaybooks.bms.application.project_enquiry_app_service import ProjectEnquiryAppService
from vaybooks.bms.application.project_dpr_app_service import ProjectDprAppService
from vaybooks.bms.application.project_procurement_app_service import (
    ProjectProcurementAppService,
)
from vaybooks.bms.application.project_subcontract_app_service import (
    ProjectSubcontractAppService,
)
from vaybooks.bms.application.project_petty_cash_app_service import (
    ProjectPettyCashAppService,
)
from vaybooks.bms.application.project_recognition_app_service import (
    ProjectRecognitionAppService,
)
from vaybooks.bms.application.project_offline_app_service import ProjectOfflineAppService
from vaybooks.bms.application.project_portal_app_service import ProjectPortalAppService
from vaybooks.bms.application.project_notification_app_service import (
    ProjectNotificationAppService,
)
from vaybooks.bms.application.project_access_policy import ProjectAccessPolicy
from vaybooks.bms.application.project_audit_app_service import ProjectAuditAppService
from vaybooks.bms.application.project_quality_config_app_service import (
    ProjectQualityConfigAppService,
)
from vaybooks.bms.infrastructure.repositories.mongo_project_offline_draft_repository import (
    MongoProjectOfflineDraftRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_project_portal_token_repository import (
    MongoProjectPortalTokenRepository,
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
        "Bootstrap seed settings: seed_config=%s seed_qa_fixtures=%s purge_business_data=%s "
        "seed_business=%s seed_customers=%s seed_vendors=%s seed_categories=%s seed_products=%s "
        "business_registration=%s db=%s",
        settings.seed_config,
        settings.seed_qa_fixtures,
        settings.purge_business_data,
        settings.seed_business,
        settings.seed_customers,
        settings.seed_vendors,
        settings.seed_categories,
        settings.seed_products,
        settings.seed_business_registration,
        settings.db_name,
    )
    db = get_database()
    run_pending_migrations(db)
    ensure_indexes(db)
    if settings.purge_business_data:
        purge_business_data(db)
    if settings.seed_config:
        run_seed(db)
    if any(
        (
            settings.seed_business,
            settings.seed_customers,
            settings.seed_vendors,
            settings.seed_categories,
            settings.seed_products,
        )
    ):
        from vaybooks.bms.infrastructure.db.demo_seed import run_demo_seed

        run_demo_seed(db, settings)
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
    measurement_spec_repo = MongoMeasurementSpecRepository(db)
    measurement_record_repo = MongoMeasurementRecordRepository(db)
    measurement_section_repo = MongoMeasurementSectionRepository(db)
    attachment_repo = MongoAttachmentRepository(db)
    project_template_repo = MongoProjectTemplateRepository(db)
    project_repo = MongoProjectRepository(db)
    project_document_repo = MongoProjectDocumentRepository(db)
    project_time_repo = MongoProjectTimeEntryRepository(db)
    project_expense_repo = MongoProjectExpenseRepository(db)
    project_quotation_repo = MongoProjectQuotationRepository(db)
    project_work_order_repo = MongoProjectWorkOrderRepository(db)
    project_ra_repo = MongoProjectRABillRepository(db)
    project_proforma_repo = MongoProjectProformaRepository(db)
    project_variation_repo = MongoProjectVariationRepository(db)
    project_retention_repo = MongoProjectRetentionRepository(db)
    project_transfer_repo = MongoProjectCostTransferRepository(db)
    project_write_off_repo = MongoProjectWriteOffRepository(db)
    project_boq_repo = MongoProjectBoqRepository(db)
    project_budget_repo = MongoProjectBudgetRepository(db)
    project_cash_flow_repo = MongoProjectCashFlowRepository(db)
    project_measurement_repo = MongoProjectMeasurementRepository(db)
    project_activity_config_repo = MongoProjectActivityConfigRepository(db)
    project_enquiry_repo = MongoProjectEnquiryRepository(db)
    project_dpr_repo = MongoProjectDprRepository(db)
    project_procurement_repo = MongoProjectProcurementRepository(db)
    project_subcontract_repo = MongoProjectSubcontractRepository(db)
    project_petty_cash_repo = MongoProjectPettyCashRepository(db)
    project_recognition_repo = MongoProjectRecognitionRepository(db)
    project_offline_draft_repo = MongoProjectOfflineDraftRepository(db)
    project_portal_token_repo = MongoProjectPortalTokenRepository(db)
    project_quality_config_repo = MongoProjectQualityConfigRepository(db)
    app_user_repo = MongoAppUserRepository(db)
    project_membership_repo = MongoProjectMembershipRepository(db)
    project_audit_repo = MongoProjectAuditRepository(db)

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

    measurement_service = MeasurementAppService(
        measurement_spec_repo,
        measurement_record_repo,
        counter_repo,
        measurement_section_repo,
    )
    attachment_service = AttachmentAppService(attachment_repo)

    project_service = ProjectAppService(
        project_repo,
        project_template_repo,
        counter_repo,
        customer_repo,
        activity_config_repo=project_activity_config_repo,
    )
    project_document_service = ProjectDocumentAppService(
        project_document_repo,
        project_repo,
    )
    project_time_service = ProjectTimeAppService(
        project_time_repo,
        project_repo,
        worker_repo,
    )
    project_expense_service = ProjectExpenseAppService(
        project_expense_repo,
        project_repo,
    )
    project_boq_service = ProjectBoqAppService(project_boq_repo, project_repo)
    project_budget_service = ProjectBudgetAppService(
        project_budget_repo,
        project_repo,
        expense_repo=project_expense_repo,
        time_repo=project_time_repo,
        purchase_service=purchase_service,
        cash_flow_repo=project_cash_flow_repo,
    )
    project_expense_service._budget_service = project_budget_service
    project_measurement_service = ProjectMeasurementAppService(
        project_measurement_repo,
        project_boq_repo,
        project_repo,
        ra_repo=project_ra_repo,
    )
    projects_profitability = ProjectProfitabilityService(
        project_repo,
        project_time_repo,
        project_expense_repo,
    )
    project_access = ProjectAccessPolicy(
        maker_checker_enabled=True,
        user_repo=app_user_repo,
        membership_repo=project_membership_repo,
    )
    project_audit_service = ProjectAuditAppService(project_audit_repo)
    project_enquiry_service = ProjectEnquiryAppService(
        project_enquiry_repo,
        project_repo,
        counter_repo,
        customer_repo=customer_repo,
    )
    project_quotation_service = ProjectQuotationAppService(
        project_quotation_repo,
        project_repo,
        counter_repo,
        document_service=project_document_service,
        business_service=business_service,
        work_order_repo=project_work_order_repo,
        boq_repo=project_boq_repo,
        boq_service=project_boq_service,
        enquiry_service=project_enquiry_service,
        access_policy=project_access,
        audit_service=project_audit_service,
    )
    project_dpr_service = ProjectDprAppService(project_dpr_repo, project_repo)
    project_procurement_service = ProjectProcurementAppService(
        project_procurement_repo,
        project_repo,
        counter_repo,
        purchase_service=purchase_service,
    )
    project_subcontract_service = ProjectSubcontractAppService(
        project_subcontract_repo, project_repo, counter_repo
    )
    project_petty_cash_service = ProjectPettyCashAppService(
        project_petty_cash_repo, project_repo, counter_repo
    )
    project_recognition_service = ProjectRecognitionAppService(
        project_recognition_repo,
        project_repo,
        accounting_service=accounting_service,
        expense_repo=project_expense_repo,
    )
    project_offline_service = ProjectOfflineAppService(
        project_offline_draft_repo, project_repo
    )
    project_portal_service = ProjectPortalAppService(
        project_portal_token_repo, project_repo
    )
    project_notification_service = ProjectNotificationAppService(
        quotation_repo=project_quotation_repo,
        ra_repo=project_ra_repo,
        project_repo=project_repo,
    )
    project_quality_config_service = ProjectQualityConfigAppService(
        project_quality_config_repo, project_repo, project_service=project_service
    )
    project_billing_service = ProjectBillingAppService(
        project_repo,
        project_work_order_repo,
        counter_repo,
        accounting_service=accounting_service,
        voucher_repo=voucher_repo,
        sales_service=sales_service,
        document_service=project_document_service,
        customer_repo=customer_repo,
        time_repo=project_time_repo,
        expense_repo=project_expense_repo,
        ra_repo=project_ra_repo,
        proforma_repo=project_proforma_repo,
        retention_repo=project_retention_repo,
        variation_repo=project_variation_repo,
        transfer_repo=project_transfer_repo,
        write_off_repo=project_write_off_repo,
        purchase_service=purchase_service,
        boq_repo=project_boq_repo,
        measurement_repo=project_measurement_repo,
        measurement_service=project_measurement_service,
    )
    project_budget_service._billing_service = project_billing_service
    reports_projects = ProjectReportService(
        project_repo,
        project_time_repo,
        project_expense_repo,
        profitability_service=projects_profitability,
        quotation_repo=project_quotation_repo,
        document_repo=project_document_repo,
        voucher_repo=voucher_repo,
        ra_repo=project_ra_repo,
        retention_repo=project_retention_repo,
        transfer_repo=project_transfer_repo,
        write_off_repo=project_write_off_repo,
        variation_repo=project_variation_repo,
        boq_repo=project_boq_repo,
        budget_repo=project_budget_repo,
        measurement_repo=project_measurement_repo,
        billing_service=project_billing_service,
        purchase_service=purchase_service,
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
            measurement_repo=measurement_record_repo,
            attachment_service=attachment_service,
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
        "measurements": measurement_service,
        "attachments": attachment_service,
        "projects": project_service,
        "project_documents": project_document_service,
        "project_time": project_time_service,
        "project_expenses": project_expense_service,
        "project_boq": project_boq_service,
        "project_budget": project_budget_service,
        "project_cash_flow": project_budget_service,
        "project_measurement": project_measurement_service,
        "projects_profitability": projects_profitability,
        "project_quotations": project_quotation_service,
        "project_billing": project_billing_service,
        "project_enquiries": project_enquiry_service,
        "project_dpr": project_dpr_service,
        "project_procurement": project_procurement_service,
        "project_subcontract": project_subcontract_service,
        "project_petty_cash": project_petty_cash_service,
        "project_recognition": project_recognition_service,
        "project_offline": project_offline_service,
        "project_portal": project_portal_service,
        "project_notifications": project_notification_service,
        "project_quality_config": project_quality_config_service,
        "project_activity_configs": ProjectActivityConfigAppService(
            project_activity_config_repo
        ),
        "project_access": project_access,
        "project_audit": project_audit_service,
        "reports_projects": reports_projects,
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
