from __future__ import annotations

from typing import List, Optional

from pymongo.database import Database

from vaybooks.bms.domain.crm.entities import (
    CrmAuditEntry,
    CrmImportBatch,
    CrmNotification,
    CrmNotificationPreferences,
    CrmSettings,
)
from vaybooks.bms.domain.crm.enums import CRM_SETTINGS_ID
from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.infrastructure.repositories.crm._serialize import (
    audit_from_doc,
    audit_to_doc,
    batch_from_doc,
    batch_to_doc,
    notification_from_doc,
    notification_to_doc,
    prefs_from_doc,
    prefs_to_doc,
    settings_from_doc,
    settings_to_doc,
)


class MongoCrmAuditRepository:
    def __init__(self, db: Database):
        self._collection = db.crm_audit_entries

    def save(self, entry: CrmAuditEntry) -> CrmAuditEntry:
        self._collection.replace_one(
            {"_id": entry.id}, audit_to_doc(entry), upsert=True
        )
        return entry

    def list_for_entity(
        self, entity_type: str, entity_id: str, *, limit: int = 200
    ) -> List[CrmAuditEntry]:
        docs = (
            self._collection.find(
                {"entity_type": entity_type, "entity_id": entity_id}
            )
            .sort("created_at", -1)
            .limit(limit)
        )
        return [audit_from_doc(d) for d in docs]


class MongoCrmNotificationRepository:
    def __init__(self, db: Database):
        self._collection = db.crm_notifications

    def save(self, notification: CrmNotification) -> CrmNotification:
        self._collection.replace_one(
            {"_id": notification.id}, notification_to_doc(notification), upsert=True
        )
        return notification

    def find_by_id(self, notification_id: str) -> Optional[CrmNotification]:
        doc = self._collection.find_one({"_id": notification_id})
        return notification_from_doc(doc) if doc else None

    def find_by_dedupe_key(self, dedupe_key: str) -> Optional[CrmNotification]:
        if not dedupe_key:
            return None
        doc = self._collection.find_one({"dedupe_key": dedupe_key})
        return notification_from_doc(doc) if doc else None

    def list_for_recipient(
        self, recipient_id: str, *, unread_only: bool = False, limit: int = 100
    ) -> List[CrmNotification]:
        query: dict = {"recipient_id": recipient_id}
        if unread_only:
            query["read_at"] = None
        docs = self._collection.find(query).sort("created_at", -1).limit(limit)
        return [notification_from_doc(d) for d in docs]


class MongoCrmNotificationPreferencesRepository:
    def __init__(self, db: Database):
        self._collection = db.crm_notification_preferences

    def save(
        self, prefs: CrmNotificationPreferences
    ) -> CrmNotificationPreferences:
        prefs.updated_at = utc_now()
        self._collection.replace_one(
            {"user_id": prefs.user_id}, prefs_to_doc(prefs), upsert=True
        )
        return prefs

    def find_by_user_id(self, user_id: str) -> Optional[CrmNotificationPreferences]:
        doc = self._collection.find_one({"user_id": user_id})
        return prefs_from_doc(doc) if doc else None


class MongoCrmImportBatchRepository:
    def __init__(self, db: Database):
        self._collection = db.crm_import_batches

    def save(self, batch: CrmImportBatch) -> CrmImportBatch:
        self._collection.replace_one(
            {"_id": batch.id}, batch_to_doc(batch), upsert=True
        )
        return batch

    def find_by_id(self, batch_id: str) -> Optional[CrmImportBatch]:
        doc = self._collection.find_one({"_id": batch_id})
        return batch_from_doc(doc) if doc else None

    def find_by_file_hash(self, file_hash: str) -> Optional[CrmImportBatch]:
        if not file_hash:
            return None
        doc = self._collection.find_one({"file_hash": file_hash})
        return batch_from_doc(doc) if doc else None

    def list_recent(self, *, limit: int = 50) -> List[CrmImportBatch]:
        docs = self._collection.find().sort("created_at", -1).limit(limit)
        return [batch_from_doc(d) for d in docs]


class MongoCrmSettingsRepository:
    def __init__(self, db: Database):
        self._collection = db.crm_settings

    def get(self) -> CrmSettings:
        doc = self._collection.find_one({"_id": CRM_SETTINGS_ID})
        return settings_from_doc(doc)

    def save(self, settings: CrmSettings) -> CrmSettings:
        settings.id = CRM_SETTINGS_ID
        settings.updated_at = utc_now()
        self._collection.replace_one(
            {"_id": CRM_SETTINGS_ID}, settings_to_doc(settings), upsert=True
        )
        return settings
