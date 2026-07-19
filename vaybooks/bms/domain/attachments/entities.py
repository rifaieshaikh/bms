"""Item attachment metadata and binary payload."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import AttachmentCategory


IMAGE_CATEGORIES = {
    AttachmentCategory.REFERENCE,
    AttachmentCategory.DESIGN,
    AttachmentCategory.PATTERN,
}

IMAGE_MAX_BYTES = 5 * 1024 * 1024
FILE_OUT_MAX_BYTES = 20 * 1024 * 1024
MAX_FILES_PER_IMAGE_CATEGORY = 5


@dataclass
class Attachment:
    order_id: str
    item_id: str
    category: AttachmentCategory
    name: str
    content_type: str
    data: bytes
    size_bytes: int = 0
    uploaded_by: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)
    uploaded_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if not self.size_bytes:
            self.size_bytes = len(self.data or b"")
