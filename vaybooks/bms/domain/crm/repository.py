"""CRM repository protocols."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Protocol

from vaybooks.bms.domain.crm.entities import (
    CrmActivity,
    CrmAuditEntry,
    CrmEnquiry,
    CrmImportBatch,
    CrmLead,
    CrmNotification,
    CrmNotificationPreferences,
    CrmSettings,
)


class CrmLeadRepository(Protocol):
    def save(self, lead: CrmLead) -> CrmLead: ...

    def find_by_id(self, lead_id: str) -> Optional[CrmLead]: ...

    def find_by_phone_normalized(self, phone: str) -> Optional[CrmLead]: ...

    def find_by_email_normalized(self, email: str) -> Optional[CrmLead]: ...

    def find_by_gstin_normalized(self, gstin: str) -> Optional[CrmLead]: ...

    def find_by_import_fingerprint(
        self, batch_id: str, fingerprint: str
    ) -> Optional[CrmLead]: ...

    def list(
        self,
        *,
        status: Optional[str] = None,
        assigned_user_id: Optional[str] = None,
        source: Optional[str] = None,
        branch: Optional[str] = None,
        include_deleted: bool = False,
        search: str = "",
        limit: int = 500,
    ) -> List[CrmLead]: ...

    def list_duplicates_candidates(self) -> List[CrmLead]: ...


class CrmEnquiryRepository(Protocol):
    def save(self, enquiry: CrmEnquiry) -> CrmEnquiry: ...

    def find_by_id(self, enquiry_id: str) -> Optional[CrmEnquiry]: ...

    def list(
        self,
        *,
        status: Optional[str] = None,
        lead_id: Optional[str] = None,
        customer_id: Optional[str] = None,
        assigned_user_id: Optional[str] = None,
        branch: Optional[str] = None,
        include_deleted: bool = False,
        search: str = "",
        limit: int = 500,
    ) -> List[CrmEnquiry]: ...


class CrmActivityRepository(Protocol):
    def save(self, activity: CrmActivity) -> CrmActivity: ...

    def find_by_id(self, activity_id: str) -> Optional[CrmActivity]: ...

    def find_by_source(
        self,
        source_module: str,
        source_txn_type: str,
        source_txn_id: str,
        activity_type_key: str,
    ) -> Optional[CrmActivity]: ...

    def list(
        self,
        *,
        lead_id: Optional[str] = None,
        enquiry_id: Optional[str] = None,
        customer_id: Optional[str] = None,
        assigned_user_id: Optional[str] = None,
        status: Optional[str] = None,
        activity_type: Optional[str] = None,
        branch: Optional[str] = None,
        scheduled_from: Optional[datetime] = None,
        scheduled_to: Optional[datetime] = None,
        include_deleted: bool = False,
        limit: int = 500,
    ) -> List[CrmActivity]: ...

    def list_timeline(
        self,
        *,
        lead_id: str = "",
        enquiry_id: str = "",
        customer_id: str = "",
        limit: int = 200,
    ) -> List[CrmActivity]: ...


class CrmAuditRepository(Protocol):
    def save(self, entry: CrmAuditEntry) -> CrmAuditEntry: ...

    def list_for_entity(
        self, entity_type: str, entity_id: str, *, limit: int = 200
    ) -> List[CrmAuditEntry]: ...


class CrmNotificationRepository(Protocol):
    def save(self, notification: CrmNotification) -> CrmNotification: ...

    def find_by_id(self, notification_id: str) -> Optional[CrmNotification]: ...

    def find_by_dedupe_key(self, dedupe_key: str) -> Optional[CrmNotification]: ...

    def list_for_recipient(
        self, recipient_id: str, *, unread_only: bool = False, limit: int = 100
    ) -> List[CrmNotification]: ...


class CrmNotificationPreferencesRepository(Protocol):
    def save(
        self, prefs: CrmNotificationPreferences
    ) -> CrmNotificationPreferences: ...

    def find_by_user_id(self, user_id: str) -> Optional[CrmNotificationPreferences]: ...


class CrmImportBatchRepository(Protocol):
    def save(self, batch: CrmImportBatch) -> CrmImportBatch: ...

    def find_by_id(self, batch_id: str) -> Optional[CrmImportBatch]: ...

    def find_by_file_hash(self, file_hash: str) -> Optional[CrmImportBatch]: ...

    def list_recent(self, *, limit: int = 50) -> List[CrmImportBatch]: ...


class CrmSettingsRepository(Protocol):
    def get(self) -> CrmSettings: ...

    def save(self, settings: CrmSettings) -> CrmSettings: ...
