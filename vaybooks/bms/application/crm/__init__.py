"""CRM application services package."""

from vaybooks.bms.application.crm.activities import (
    CrmActivityAppService,
    CrmAutoActivityService,
)
from vaybooks.bms.application.crm.dashboard import CrmDashboardAppService
from vaybooks.bms.application.crm.enquiries import CrmEnquiryAppService
from vaybooks.bms.application.crm.leads import CrmLeadAppService
from vaybooks.bms.application.crm.notifications import CrmNotificationAppService
from vaybooks.bms.application.crm.payment_reminder import CrmPaymentReminderService
from vaybooks.bms.application.crm.reports import CrmReportService
from vaybooks.bms.application.crm.settings import CrmSettingsAppService

__all__ = [
    "CrmActivityAppService",
    "CrmAutoActivityService",
    "CrmDashboardAppService",
    "CrmEnquiryAppService",
    "CrmLeadAppService",
    "CrmNotificationAppService",
    "CrmPaymentReminderService",
    "CrmReportService",
    "CrmSettingsAppService",
]
