"""CRM domain package."""

from vaybooks.bms.domain.crm.access import CrmAccessPolicy
from vaybooks.bms.domain.crm.entities import (
    CrmActivity,
    CrmAuditEntry,
    CrmEnquiry,
    CrmImportBatch,
    CrmLead,
    CrmNotification,
    CrmNotificationPreferences,
    CrmSettings,
    LeadDuplicateMatch,
)
from vaybooks.bms.domain.crm.enums import (
    CRM_REPORT_DEFINITIONS,
    CrmRole,
    LeadStatus,
)

__all__ = [
    "CRM_REPORT_DEFINITIONS",
    "CrmAccessPolicy",
    "CrmActivity",
    "CrmAuditEntry",
    "CrmEnquiry",
    "CrmImportBatch",
    "CrmLead",
    "CrmNotification",
    "CrmNotificationPreferences",
    "CrmRole",
    "CrmSettings",
    "LeadDuplicateMatch",
    "LeadStatus",
]
