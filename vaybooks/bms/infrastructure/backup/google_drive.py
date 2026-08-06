"""Google Drive backup upload for desktop deployments."""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from typing import Any

from vaybooks.bms.infrastructure.backup.service import RetentionMode, normalize_retention
from vaybooks.bms.infrastructure.config.settings import get_settings

logger = logging.getLogger("vaybooks.bms.backup.drive")

DRIVE_BACKUP_NAME_PREFIX = "vaybooks_backup_"
SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def _drive_service():
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError(
            "Google Drive libraries are not installed. "
            "Install google-api-python-client and google-auth "
            "(see requirements-desktop.txt)."
        ) from exc

    settings = get_settings()
    client_id = (settings.google_oauth_client_id or "").strip()
    client_secret = (settings.google_oauth_client_secret or "").strip()
    refresh_token = (settings.google_oauth_refresh_token or "").strip()
    if not client_id or not client_secret or not refresh_token:
        raise RuntimeError(
            "Google Drive OAuth is not configured. Set GOOGLE_OAUTH_CLIENT_ID, "
            "GOOGLE_OAUTH_CLIENT_SECRET, and GOOGLE_OAUTH_REFRESH_TOKEN in System Settings."
        )
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def upload_backup_file(path: Path, *, folder_id: str | None = None) -> str:
    """Upload a local ZIP to Drive. Returns the Drive file id."""
    from googleapiclient.http import MediaFileUpload

    settings = get_settings()
    target_folder = (folder_id or settings.backup_google_drive_folder_id or "").strip()
    service = _drive_service()
    file_name = f"{DRIVE_BACKUP_NAME_PREFIX}{path.name}"
    metadata: dict[str, Any] = {"name": file_name}
    if target_folder:
        metadata["parents"] = [target_folder]
    media = MediaFileUpload(
        str(path),
        mimetype=mimetypes.guess_type(path.name)[0] or "application/zip",
        resumable=True,
    )
    created = (
        service.files()
        .create(body=metadata, media_body=media, fields="id,name")
        .execute()
    )
    file_id = created.get("id") or ""
    logger.info("Uploaded backup to Google Drive id=%s name=%s", file_id, file_name)
    return file_id


def list_app_backup_files(*, folder_id: str | None = None) -> list[dict[str, Any]]:
    settings = get_settings()
    target_folder = (folder_id or settings.backup_google_drive_folder_id or "").strip()
    service = _drive_service()
    query_parts = [
        f"name contains '{DRIVE_BACKUP_NAME_PREFIX}'",
        "trashed = false",
    ]
    if target_folder:
        query_parts.append(f"'{target_folder}' in parents")
    response = (
        service.files()
        .list(
            q=" and ".join(query_parts),
            fields="files(id, name, createdTime)",
            orderBy="createdTime desc",
            pageSize=100,
        )
        .execute()
    )
    return list(response.get("files") or [])


def prune_drive_backups(
    retention: RetentionMode = "keep_one",
    *,
    folder_id: str | None = None,
    keep_file_id: str | None = None,
) -> int:
    retention = normalize_retention(retention)
    if retention == "keep_all":
        return 0
    files = list_app_backup_files(folder_id=folder_id)
    if not files:
        return 0
    keep_id = keep_file_id or files[0].get("id")
    service = _drive_service()
    removed = 0
    for item in files:
        file_id = item.get("id")
        if not file_id or file_id == keep_id:
            continue
        service.files().delete(fileId=file_id).execute()
        removed += 1
    if removed:
        logger.info("Google Drive keep_one removed %s older backup(s)", removed)
    return removed


def upload_backup_and_prune(
    path: Path,
    *,
    retention: RetentionMode = "keep_one",
    folder_id: str | None = None,
) -> str:
    file_id = upload_backup_file(path, folder_id=folder_id)
    prune_drive_backups(retention, folder_id=folder_id, keep_file_id=file_id)
    return file_id
