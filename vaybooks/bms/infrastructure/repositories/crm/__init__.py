"""CRM Mongo repositories."""

from vaybooks.bms.infrastructure.repositories.crm.mongo_crm_activity_repository import (
    MongoCrmActivityRepository,
)
from vaybooks.bms.infrastructure.repositories.crm.mongo_crm_enquiry_repository import (
    MongoCrmEnquiryRepository,
)
from vaybooks.bms.infrastructure.repositories.crm.mongo_crm_lead_repository import (
    MongoCrmLeadRepository,
)
from vaybooks.bms.infrastructure.repositories.crm.mongo_crm_support_repositories import (
    MongoCrmAuditRepository,
    MongoCrmImportBatchRepository,
    MongoCrmNotificationPreferencesRepository,
    MongoCrmNotificationRepository,
    MongoCrmSettingsRepository,
)

__all__ = [
    "MongoCrmActivityRepository",
    "MongoCrmAuditRepository",
    "MongoCrmEnquiryRepository",
    "MongoCrmImportBatchRepository",
    "MongoCrmLeadRepository",
    "MongoCrmNotificationPreferencesRepository",
    "MongoCrmNotificationRepository",
    "MongoCrmSettingsRepository",
]
