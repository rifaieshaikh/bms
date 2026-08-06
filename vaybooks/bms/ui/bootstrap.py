import logging
import streamlit as st

from vaybooks.bms.application.settings.business.service import BusinessAppService
from vaybooks.bms.application.parties.customers.service import CustomerAppService
from vaybooks.bms.application.parties.vendors.service import VendorAppService
from vaybooks.bms.application.parties.delivery_partners.service import (
    DeliveryPartnerAppService,
)
from vaybooks.bms.application.parties.commission_agents.service import (
    CommissionAgentAppService,
)
from vaybooks.bms.application.parties.segments.service import PartySegmentAppService
from vaybooks.bms.application.boutique.deliveries.service import DeliveryAppService
from vaybooks.bms.application.boutique.expenses.service import ExpenseAppService
from vaybooks.bms.application.finance.export.service import ExportAppService
from vaybooks.bms.application.migration.service import MigrationAppService
from vaybooks.bms.application.boutique.invoices.service import InvoiceAppService
from vaybooks.bms.application.boutique.orders.service import OrderAppService
from vaybooks.bms.application.finance.reports.service import ReportAppService
from vaybooks.bms.application.finance.reports.services import (
    BusinessInsightsReportService,
    CustomerReportService,
    LaborReportService,
    OperationsReportService,
    ProfitabilityReportService,
)
from vaybooks.bms.application.finance.reports.services.inventory_report_service import (
    InventoryReportService,
)
from vaybooks.bms.application.finance.reports.services.purchase_report_service import (
    PurchaseReportService,
)
from vaybooks.bms.application.finance.reports.services.sales_module_report_service import (
    SalesModuleReportService,
)
from vaybooks.bms.application.finance.reports.services.production_report_service import (
    ProductionReportService,
)
from vaybooks.bms.application.finance.reports.services.sales_report_service import SalesReportService
from vaybooks.bms.application.boutique.reports.service import BoutiqueModuleReportService
from vaybooks.bms.application.boutique.time_tracking.service import TimeTrackingAppService
from vaybooks.bms.application.finance.accounting.service import AccountingAppService
from vaybooks.bms.application.boutique.activities.service import ActivityAppService
from vaybooks.bms.application.settings.services.service import VendorServiceAppService
from vaybooks.bms.application.inventory.service import InventoryAppService
from vaybooks.bms.application.purchases.service import PurchaseAppService
from vaybooks.bms.application.sales.service import SalesAppService
from vaybooks.bms.application.production.service import ProductionAppService
from vaybooks.bms.application.crm import (
    CrmActivityAppService,
    CrmAutoActivityService,
    CrmDashboardAppService,
    CrmEnquiryAppService,
    CrmLeadAppService,
    CrmNotificationAppService,
    CrmPaymentReminderService,
    CrmReportService,
    CrmSettingsAppService,
)
from vaybooks.bms.application.parties.workers.service import WorkerAppService
from vaybooks.bms.application.parties.workers.activity_options import (
    EmployeeActivityOptionsService,
)
from vaybooks.bms.application.store.activities.service import StoreActivityAppService
from vaybooks.bms.application.store.time_tracking.service import (
    StoreTimeTrackingAppService,
)
from vaybooks.bms.application.boutique.measurements.service import MeasurementAppService
from vaybooks.bms.application.attachment_app_service import AttachmentAppService
from vaybooks.bms.application.projects.activity_config.service import ProjectActivityConfigAppService
from vaybooks.bms.application.projects.core.service import ProjectAppService
from vaybooks.bms.application.projects.boq.service import ProjectBoqAppService
from vaybooks.bms.application.projects.budget.service import ProjectBudgetAppService
from vaybooks.bms.application.projects.billing.service import ProjectBillingAppService
from vaybooks.bms.application.projects.documents.service import ProjectDocumentAppService
from vaybooks.bms.application.projects.expenses.service import ProjectExpenseAppService
from vaybooks.bms.application.projects.measurements.service import ProjectMeasurementAppService
from vaybooks.bms.application.projects.profitability.service import ProjectProfitabilityService
from vaybooks.bms.application.projects.quotations.service import ProjectQuotationAppService
from vaybooks.bms.application.projects.time.service import ProjectTimeAppService
from vaybooks.bms.application.finance.reports.services.project_report_service import ProjectReportService
from vaybooks.bms.domain.inventory.rate_history_service import ProductRateHistoryService
from vaybooks.bms.infrastructure.db.connection import get_database
from vaybooks.bms.infrastructure.db.indexes import ensure_indexes
from vaybooks.bms.infrastructure.db.migrations.runner import run_pending_migrations
from vaybooks.bms.infrastructure.config.settings import get_settings, reload_settings
from vaybooks.bms.infrastructure.db.purge import purge_business_data
from vaybooks.bms.infrastructure.db.seed import run_seed
from vaybooks.bms.infrastructure.logging.setup import setup_logging
from vaybooks.bms.infrastructure.repositories.shared.mongo_business_profile_repository import (
    MongoBusinessProfileRepository,
)
from vaybooks.bms.infrastructure.repositories.inventory.mongo_product_rate_history_repository import (
    MongoProductRateHistoryRepository,
)
from vaybooks.bms.infrastructure.repositories.purchases.mongo_purchase_price_history_repository import (
    MongoPurchasePriceHistoryRepository,
)
from vaybooks.bms.infrastructure.repositories.sales.mongo_customer_price_repository import (
    MongoCustomerPriceRepository,
)
from vaybooks.bms.infrastructure.repositories.crm import (
    MongoCrmActivityRepository,
    MongoCrmAuditRepository,
    MongoCrmEnquiryRepository,
    MongoCrmImportBatchRepository,
    MongoCrmLeadRepository,
    MongoCrmNotificationPreferencesRepository,
    MongoCrmNotificationRepository,
    MongoCrmSettingsRepository,
)
from vaybooks.bms.infrastructure.repositories.finance.mongo_accounting_repository import (
    MongoAccountRepository,
    MongoVoucherRepository,
)
from vaybooks.bms.infrastructure.repositories.production import (
    MongoProductionBatchRepository,
    MongoProductionSettingsRepository,
    MongoRecipeRepository,
)
from vaybooks.bms.infrastructure.repositories.boutique.mongo_activity_repository import MongoActivityRepository
from vaybooks.bms.infrastructure.repositories.finance.mongo_counter_repository import MongoCounterRepository
from vaybooks.bms.infrastructure.repositories.parties.mongo_customer_repository import MongoCustomerRepository
from vaybooks.bms.infrastructure.repositories.parties.mongo_vendor_repository import MongoVendorRepository
from vaybooks.bms.infrastructure.repositories.parties.mongo_delivery_partner_repository import (
    MongoDeliveryPartnerRepository,
)
from vaybooks.bms.infrastructure.repositories.parties.mongo_commission_agent_repository import (
    MongoCommissionAgentRepository,
)
from vaybooks.bms.infrastructure.repositories.parties.mongo_party_segment_repository import (
    MongoPartySegmentRepository,
)
from vaybooks.bms.infrastructure.repositories.shared.mongo_vendor_service_repository import (
    MongoVendorServiceRepository,
)
from vaybooks.bms.infrastructure.repositories.parties.mongo_worker_repository import (
    MongoWorkerRepository,
)
from vaybooks.bms.infrastructure.repositories.boutique.mongo_delivery_repository import MongoDeliveryRepository
from vaybooks.bms.infrastructure.repositories.boutique.mongo_expense_repository import MongoExpenseRepository
from vaybooks.bms.infrastructure.repositories.boutique.mongo_invoice_repository import MongoInvoiceRepository
from vaybooks.bms.infrastructure.repositories.boutique.mongo_order_repository import (
    MongoBillRegistryRepository,
    MongoOrderRepository,
)
from vaybooks.bms.infrastructure.repositories.finance.mongo_report_repository import MongoReportRepository
from vaybooks.bms.infrastructure.repositories.inventory.mongo_inventory_repository import (
    MongoInventoryProductRepository,
    MongoLocationRepository,
    MongoProductCategoryRepository,
    MongoProductFieldDefinitionRepository,
    MongoProductUnitRepository,
    MongoStockBalanceRepository,
    MongoStockMovementRepository,
    MongoStockTransferRepository,
    MongoWarehouseRepository,
)
from vaybooks.bms.infrastructure.repositories.migration.mongo_import_mapping_profile_repository import (
    MongoImportMappingProfileRepository,
)
from vaybooks.bms.infrastructure.repositories.purchases.mongo_purchase_repository import (
    MongoGoodsReceiptRepository,
    MongoPurchaseOrderRepository,
    MongoPurchaseReturnRepository,
)
from vaybooks.bms.infrastructure.repositories.sales.mongo_sales_repository import (
    MongoDeliveryNoteRepository,
    MongoEstimateRepository,
    MongoQuotationRepository,
    MongoSalesOrderRepository,
    MongoSalesReturnRepository,
)
from vaybooks.bms.infrastructure.repositories.sales.mongo_commission_accrual_repository import (
    MongoCommissionAccrualRepository,
)
from vaybooks.bms.application.sales.commission_service import CommissionAppService
from vaybooks.bms.infrastructure.repositories.boutique.mongo_time_tracking_repository import (
    MongoTimeTrackingRepository,
)
from vaybooks.bms.infrastructure.repositories.boutique.mongo_measurement_repository import (
    MongoMeasurementRecordRepository,
    MongoMeasurementSectionRepository,
    MongoMeasurementSpecRepository,
)
from vaybooks.bms.infrastructure.repositories.mongo_attachment_repository import (
    MongoAttachmentRepository,
)
from vaybooks.bms.infrastructure.repositories.projects.mongo_project_document_repository import (
    MongoProjectDocumentRepository,
)
from vaybooks.bms.infrastructure.repositories.projects.mongo_project_expense_repository import (
    MongoProjectExpenseRepository,
)
from vaybooks.bms.infrastructure.repositories.projects.mongo_project_quotation_repository import (
    MongoProjectQuotationRepository,
)
from vaybooks.bms.infrastructure.repositories.projects.mongo_project_repository import (
    MongoProjectRepository,
)
from vaybooks.bms.infrastructure.repositories.projects.mongo_project_template_repository import (
    MongoProjectTemplateRepository,
)
from vaybooks.bms.infrastructure.repositories.projects.mongo_project_time_entry_repository import (
    MongoProjectTimeEntryRepository,
)
from vaybooks.bms.infrastructure.repositories.projects.mongo_project_work_order_repository import (
    MongoProjectWorkOrderRepository,
)
from vaybooks.bms.infrastructure.repositories.projects.mongo_project_ra_repository import (
    MongoProjectRABillRepository,
)
from vaybooks.bms.infrastructure.repositories.projects.mongo_project_proforma_repository import (
    MongoProjectProformaRepository,
)
from vaybooks.bms.infrastructure.repositories.projects.mongo_project_variation_repository import (
    MongoProjectVariationRepository,
)
from vaybooks.bms.infrastructure.repositories.projects.mongo_project_retention_repository import (
    MongoProjectRetentionRepository,
)
from vaybooks.bms.infrastructure.repositories.projects.mongo_project_cost_transfer_repository import (
    MongoProjectCostTransferRepository,
)
from vaybooks.bms.infrastructure.repositories.projects.mongo_project_write_off_repository import (
    MongoProjectWriteOffRepository,
)
from vaybooks.bms.infrastructure.repositories.projects.mongo_project_boq_repository import (
    MongoProjectBoqRepository,
)
from vaybooks.bms.infrastructure.repositories.projects.mongo_project_budget_repository import (
    MongoProjectBudgetRepository,
)
from vaybooks.bms.infrastructure.repositories.projects.mongo_project_cash_flow_repository import (
    MongoProjectCashFlowRepository,
)
from vaybooks.bms.infrastructure.repositories.projects.mongo_project_measurement_repository import (
    MongoProjectMeasurementRepository,
)
from vaybooks.bms.infrastructure.repositories.projects.mongo_project_activity_config_repository import (
    MongoProjectActivityConfigRepository,
)
from vaybooks.bms.infrastructure.repositories.store.mongo_store_activity_repository import (
    MongoStoreActivityRepository,
)
from vaybooks.bms.infrastructure.repositories.store.mongo_store_time_tracking_repository import (
    MongoStoreTimeTrackingRepository,
)
from vaybooks.bms.infrastructure.repositories.projects.mongo_project_enquiry_repository import (
    MongoProjectEnquiryRepository,
)
from vaybooks.bms.infrastructure.repositories.projects.mongo_project_dpr_repository import (
    MongoProjectDprRepository,
)
from vaybooks.bms.infrastructure.repositories.projects.mongo_project_procurement_repository import (
    MongoProjectProcurementRepository,
)
from vaybooks.bms.infrastructure.repositories.projects.mongo_project_subcontract_repository import (
    MongoProjectSubcontractRepository,
)
from vaybooks.bms.infrastructure.repositories.projects.mongo_project_petty_cash_repository import (
    MongoProjectPettyCashRepository,
)
from vaybooks.bms.infrastructure.repositories.projects.mongo_project_recognition_repository import (
    MongoProjectRecognitionRepository,
)
from vaybooks.bms.infrastructure.repositories.projects.mongo_app_user_repository import (
    MongoProjectMembershipRepository,
)
from vaybooks.bms.infrastructure.repositories.identity.mongo_user_repository import (
    MongoRoleRepository,
    MongoUserRepository,
)
from vaybooks.bms.infrastructure.repositories.identity.mongo_access_audit_repository import (
    MongoAccessAuditRepository,
)
from vaybooks.bms.infrastructure.repositories.entitlements.mongo_entitlement_repository import (
    MongoFeatureFlagRepository,
    MongoOrgEntitlementRepository,
    MongoPlanRepository,
)
from vaybooks.bms.infrastructure.repositories.projects.mongo_project_audit_repository import (
    MongoProjectAuditRepository,
)
from vaybooks.bms.infrastructure.repositories.projects.mongo_project_quality_config_repository import (
    MongoProjectQualityConfigRepository,
)
from vaybooks.bms.application.projects.enquiries.service import ProjectEnquiryAppService
from vaybooks.bms.application.projects.dpr.service import ProjectDprAppService
from vaybooks.bms.application.projects.procurement.service import (
    ProjectProcurementAppService,
)
from vaybooks.bms.application.projects.subcontract.service import (
    ProjectSubcontractAppService,
)
from vaybooks.bms.application.projects.petty_cash.service import (
    ProjectPettyCashAppService,
)
from vaybooks.bms.application.projects.recognition.service import (
    ProjectRecognitionAppService,
)
from vaybooks.bms.application.projects.offline.service import ProjectOfflineAppService
from vaybooks.bms.application.projects.portal.service import ProjectPortalAppService
from vaybooks.bms.application.projects.notifications.service import (
    ProjectNotificationAppService,
)
from vaybooks.bms.application.projects.access.service import ProjectAccessPolicy
from vaybooks.bms.application.projects.audit.service import ProjectAuditAppService
from vaybooks.bms.application.identity.service import RoleAppService, UserAppService
from vaybooks.bms.application.identity.audit import AccessAuditAppService
from vaybooks.bms.application.entitlements.authorization import AuthorizationService
from vaybooks.bms.application.entitlements.service import (
    FeatureFlagAppService,
    PlanAppService,
)
from vaybooks.bms.application.projects.quality.service import (
    ProjectQualityConfigAppService,
)
from vaybooks.bms.infrastructure.repositories.projects.mongo_project_offline_draft_repository import (
    MongoProjectOfflineDraftRepository,
)
from vaybooks.bms.infrastructure.repositories.projects.mongo_project_portal_token_repository import (
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
    from vaybooks.bms.infrastructure.db.demo_seed_profiles import profiles_to_run

    logger.info(
        "Bootstrap seed settings: seed_config=%s seed_qa_fixtures=%s purge_business_data=%s "
        "seed_profile=%s counts=(c=%s,v=%s,cat=%s,p=%s) db=%s",
        settings.seed_config,
        settings.seed_qa_fixtures,
        settings.purge_business_data,
        settings.seed_profile,
        settings.seed_customer_count,
        settings.seed_vendor_count,
        settings.seed_category_count,
        settings.seed_product_count,
        settings.db_name,
    )
    db = get_database()
    run_pending_migrations(db)
    ensure_indexes(db)
    if settings.purge_business_data:
        purge_business_data(db)
    if settings.seed_config:
        run_seed(db)
    if profiles_to_run(settings.seed_profile):
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
    delivery_partner_repo = MongoDeliveryPartnerRepository(db)
    commission_agent_repo = MongoCommissionAgentRepository(db)
    party_segment_repo = MongoPartySegmentRepository(db)
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
    warehouse_repo = MongoWarehouseRepository(db)
    location_repo = MongoLocationRepository(db)
    stock_balance_repo = MongoStockBalanceRepository(db)
    stock_transfer_repo = MongoStockTransferRepository(db)
    production_recipe_repo = MongoRecipeRepository(db)
    production_batch_repo = MongoProductionBatchRepository(db)
    production_settings_repo = MongoProductionSettingsRepository(db)
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
    store_activity_repo = MongoStoreActivityRepository(db)
    store_time_repo = MongoStoreTimeTrackingRepository(db)
    project_enquiry_repo = MongoProjectEnquiryRepository(db)
    project_dpr_repo = MongoProjectDprRepository(db)
    project_procurement_repo = MongoProjectProcurementRepository(db)
    project_subcontract_repo = MongoProjectSubcontractRepository(db)
    project_petty_cash_repo = MongoProjectPettyCashRepository(db)
    project_recognition_repo = MongoProjectRecognitionRepository(db)
    project_offline_draft_repo = MongoProjectOfflineDraftRepository(db)
    project_portal_token_repo = MongoProjectPortalTokenRepository(db)
    project_quality_config_repo = MongoProjectQualityConfigRepository(db)
    project_membership_repo = MongoProjectMembershipRepository(db)
    project_audit_repo = MongoProjectAuditRepository(db)
    user_repo = MongoUserRepository(db)
    role_repo = MongoRoleRepository(db)
    feature_flag_repo = MongoFeatureFlagRepository(db)
    plan_repo = MongoPlanRepository(db)
    org_entitlement_repo = MongoOrgEntitlementRepository(db)
    crm_lead_repo = MongoCrmLeadRepository(db)
    crm_enquiry_repo = MongoCrmEnquiryRepository(db)
    crm_activity_repo = MongoCrmActivityRepository(db)
    crm_settings_repo = MongoCrmSettingsRepository(db)
    crm_import_batch_repo = MongoCrmImportBatchRepository(db)
    crm_audit_repo = MongoCrmAuditRepository(db)
    crm_notification_repo = MongoCrmNotificationRepository(db)
    crm_notification_preferences_repo = MongoCrmNotificationPreferencesRepository(db)

    authorization = AuthorizationService(
        user_repo=user_repo,
        role_repo=role_repo,
        plan_repo=plan_repo,
        flag_repo=feature_flag_repo,
        org_entitlement_repo=org_entitlement_repo,
        membership_repo=project_membership_repo,
    )

    def _session_actor() -> tuple[str, str]:
        from vaybooks.bms.ui.auth.session import current_user_id, current_user_name

        return current_user_id(), current_user_name()

    access_audit_repo = MongoAccessAuditRepository(db)
    access_audit_service = AccessAuditAppService(
        access_audit_repo,
        actor_resolver=_session_actor,
        async_write=True,
    )
    user_service = UserAppService(
        user_repo,
        role_repo=role_repo,
        authorization=authorization,
        audit=access_audit_service,
    )
    role_service = RoleAppService(
        role_repo, authorization=authorization, audit=access_audit_service
    )
    feature_flag_service = FeatureFlagAppService(
        feature_flag_repo, authorization=authorization, audit=access_audit_service
    )
    plan_service = PlanAppService(
        plan_repo,
        org_entitlement_repo,
        authorization=authorization,
        audit=access_audit_service,
    )

    crm_auto_activity_service = CrmAutoActivityService(
        crm_activity_repo,
        settings_repo=crm_settings_repo,
        lead_repo=crm_lead_repo,
    )
    accounting_service = AccountingAppService(
        account_repo,
        voucher_repo,
        counter_repo,
        crm_event_sink=crm_auto_activity_service,
    )
    party_segment_service = PartySegmentAppService(party_segment_repo)
    business_service = BusinessAppService(business_profile_repo)
    accounting_service.set_business_service(business_service)
    commission_agent_service = CommissionAgentAppService(
        commission_agent_repo, account_repo, segment_service=party_segment_service
    )
    customer_service = CustomerAppService(
        customer_repo,
        account_repo,
        segment_service=party_segment_service,
        business_service=business_service,
        commission_agent_service=commission_agent_service,
    )
    vendor_service = VendorAppService(
        vendor_repo, account_repo, segment_service=party_segment_service
    )
    delivery_partner_service = DeliveryPartnerAppService(
        delivery_partner_repo, account_repo
    )
    vendor_services_config = VendorServiceAppService(vendor_service_repo)
    crm_notification_service = CrmNotificationAppService(
        crm_notification_repo,
        preferences_repo=crm_notification_preferences_repo,
        activity_repo=crm_activity_repo,
        lead_repo=crm_lead_repo,
        settings_repo=crm_settings_repo,
    )
    crm_settings_service = CrmSettingsAppService(
        crm_settings_repo, audit_repo=crm_audit_repo
    )
    crm_lead_service = CrmLeadAppService(
        crm_lead_repo,
        audit_repo=crm_audit_repo,
        activity_repo=crm_activity_repo,
        notification_repo=crm_notification_repo,
        notification_service=crm_notification_service,
        customer_service=customer_service,
        counter_repo=counter_repo,
        settings_repo=crm_settings_repo,
        user_service=user_service,
        enquiry_repo=crm_enquiry_repo,
    )
    crm_enquiry_service = CrmEnquiryAppService(
        crm_enquiry_repo,
        audit_repo=crm_audit_repo,
        activity_repo=crm_activity_repo,
        lead_repo=crm_lead_repo,
        counter_repo=counter_repo,
        settings_repo=crm_settings_repo,
        user_service=user_service,
        notification_service=crm_notification_service,
    )
    crm_activity_service = CrmActivityAppService(
        crm_activity_repo,
        settings_repo=crm_settings_repo,
        audit_repo=crm_audit_repo,
        lead_repo=crm_lead_repo,
        user_service=user_service,
    )
    crm_payment_reminder_service = CrmPaymentReminderService(
        crm_settings_repo,
        activity_repo=crm_activity_repo,
        notification_service=crm_notification_service,
        audit_repo=crm_audit_repo,
        customer_service=customer_service,
        accounting_service=accounting_service,
    )

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
        warehouse_repo,
        location_repo=location_repo,
        balance_repo=stock_balance_repo,
        transfer_repo=stock_transfer_repo,
    )
    production_service = ProductionAppService(
        production_recipe_repo,
        production_batch_repo,
        production_settings_repo,
        inventory_service,
        accounting_service,
    )
    reports_production = ProductionReportService(production_service)
    migration_service = MigrationAppService(
        mapping_profile_repo,
        customer_service,
        vendor_service,
        inventory_service,
        accounting_service,
        party_segment_service=party_segment_service,
        lead_service=crm_lead_service,
        import_batch_repo=crm_import_batch_repo,
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
    worker_service = WorkerAppService(
        worker_repo, account_repo, user_service=user_service
    )
    commission_accrual_repo = MongoCommissionAccrualRepository(db)
    commission_service = CommissionAppService(
        commission_accrual_repo,
        accounting_service,
        agent_service=commission_agent_service,
        worker_service=worker_service,
        inventory=inventory_service,
    )
    accounting_service.set_commission_service(commission_service)
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
        crm_event_sink=crm_auto_activity_service,
        commission_service=commission_service,
    )
    crm_enquiry_service.set_sales_service(sales_service)
    crm_dashboard_service = CrmDashboardAppService(
        crm_lead_repo,
        enquiry_repo=crm_enquiry_repo,
        activity_repo=crm_activity_repo,
        customer_service=customer_service,
        sales_service=sales_service,
        accounting_service=accounting_service,
        settings_repo=crm_settings_repo,
    )
    crm_report_service = CrmReportService(
        crm_lead_repo,
        enquiry_repo=crm_enquiry_repo,
        activity_repo=crm_activity_repo,
        customer_service=customer_service,
        settings_repo=crm_settings_repo,
        sales_service=sales_service,
        accounting_service=accounting_service,
    )
    reports_inventory = InventoryReportService(inventory_service, sales=sales_service)
    reports_purchases = PurchaseReportService(purchase_service)
    reports_sales_module = SalesModuleReportService(sales_service)
    reports_boutique_module = BoutiqueModuleReportService(
        reports_operations,
        reports_labor,
        order_repo,
        invoice_repo,
        delivery_repo,
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
        user_repo=user_repo,
        membership_repo=project_membership_repo,
        authorization=authorization,
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

    boutique_activity_service = ActivityAppService(activity_repo, order_repo)
    store_activity_service = StoreActivityAppService(store_activity_repo)
    project_activity_config_service = ProjectActivityConfigAppService(
        project_activity_config_repo
    )
    employee_activity_options = EmployeeActivityOptionsService(
        plan_service,
        store_activity_service,
        boutique_activity_service,
        project_activity_config_service,
    )

    services = {
        "customers": customer_service,
        "vendors": vendor_service,
        "delivery_partners": delivery_partner_service,
        "commission_agents": commission_agent_service,
        "party_segments": party_segment_service,
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
        "activities": boutique_activity_service,
        "store_activities": store_activity_service,
        "employee_activity_options": employee_activity_options,
        "workers": worker_service,
        "commission": commission_service,
        "time_tracking": TimeTrackingAppService(time_repo, order_repo),
        "store_time_tracking": StoreTimeTrackingAppService(
            store_time_repo, store_activity_repo, worker_repo
        ),
        "expenses": expense_service,
        "invoices": invoice_service,
        "deliveries": DeliveryAppService(
            delivery_repo, order_repo, invoice_repo, expense_repo, time_repo
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
        "project_activity_configs": project_activity_config_service,
        "project_access": project_access,
        "project_audit": project_audit_service,
        "authorization": authorization,
        "users": user_service,
        "roles": role_service,
        "feature_flags": feature_flag_service,
        "plans": plan_service,
        "access_audit": access_audit_service,
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
        "production": production_service,
        "reports_production": reports_production,
        "purchases": purchase_service,
        "sales": sales_service,
        "reports_purchases": reports_purchases,
        "reports_sales_module": reports_sales_module,
        "reports_boutique_module": reports_boutique_module,
        "crm_leads": crm_lead_service,
        "crm_enquiries": crm_enquiry_service,
        "crm_activities": crm_activity_service,
        "crm_auto_activities": crm_auto_activity_service,
        "crm_dashboard": crm_dashboard_service,
        "crm_reports": crm_report_service,
        "crm_settings": crm_settings_service,
        "crm_notifications": crm_notification_service,
        "crm_payment_reminders": crm_payment_reminder_service,
        "crm_access": authorization,
        "activity_repo": activity_repo,
        "order_repo": order_repo,
        "invoice_repo": invoice_repo,
        "delivery_repo": delivery_repo,
    }

    scheduler_service = _build_scheduler_service(
        db,
        services,
        repos={
            "customers": customer_repo,
            "vendors": vendor_repo,
            "crm_activities": crm_activity_repo,
            "crm_leads": crm_lead_repo,
            "crm_enquiries": crm_enquiry_repo,
            "accounts": account_repo,
            "vouchers": voucher_repo,
            "quotations": quotation_repo,
            "estimates": estimate_repo,
            "sales_orders": so_repo,
            "delivery_notes": dn_repo,
            "sales_returns": sales_return_repo,
            "purchase_orders": po_repo,
            "goods_receipts": grn_repo,
            "inventory_products": inventory_product_repo,
            "stock_transfers": stock_transfer_repo,
            "production_recipes": production_recipe_repo,
            "production_batches": production_batch_repo,
            "boutique_orders": order_repo,
            "boutique_invoices": invoice_repo,
            "boutique_deliveries": delivery_repo,
            "projects": project_repo,
            "project_memberships": project_membership_repo,
            "project_quotations": project_quotation_repo,
            "project_procurement": project_procurement_repo,
        },
        audit=access_audit_service,
    )
    services["schedulers"] = scheduler_service
    services["scheduler_notifications"] = scheduler_service
    return services


def _build_scheduler_service(db, services: dict, *, repos: dict, audit=None):
    """Assemble the shared scheduler with every domain job and report runner."""
    from vaybooks.bms.application.schedulers.jobs import all_jobs
    from vaybooks.bms.application.schedulers.jobs._base import Deps
    from vaybooks.bms.application.schedulers.registry import JobRegistry
    from vaybooks.bms.application.schedulers.reports_registry import build_report_registry
    from vaybooks.bms.application.schedulers.service import SchedulerAppService
    from vaybooks.bms.infrastructure.repositories.schedulers import (
        MongoSchedulerJobConfigRepository,
        MongoSchedulerLeaseRepository,
        MongoSchedulerNotificationRepository,
        MongoSchedulerQueries,
        MongoSchedulerReportArtifactRepository,
        MongoSchedulerReportConfigRepository,
        MongoSchedulerReportRunLogRepository,
        MongoSchedulerRunLogRepository,
    )

    deps = Deps(queries=MongoSchedulerQueries(db), services=services, repos=repos)
    registry = JobRegistry()
    for job, definition in all_jobs(deps):
        registry.register(job, definition)

    return SchedulerAppService(
        MongoSchedulerJobConfigRepository(db),
        MongoSchedulerRunLogRepository(db),
        MongoSchedulerLeaseRepository(db),
        MongoSchedulerNotificationRepository(db),
        registry=registry,
        report_registry=build_report_registry(services),
        report_config_repo=MongoSchedulerReportConfigRepository(db),
        report_run_log_repo=MongoSchedulerReportRunLogRepository(db),
        report_artifact_repo=MongoSchedulerReportArtifactRepository(db),
        audit=audit,
    )
