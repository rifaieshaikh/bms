from __future__ import annotations

from typing import List, Optional

from vaybooks.bms.domain.attachments.entities import Attachment
from vaybooks.bms.domain.attachments.repository import AttachmentRepository
from vaybooks.bms.domain.attachments.services import AttachmentDomainService
from vaybooks.bms.domain.shared.enums import AttachmentCategory
from vaybooks.bms.domain.shared.exceptions import ValidationError


class AttachmentAppService:
    def __init__(self, attachment_repo: AttachmentRepository):
        self._repo = attachment_repo
        self._domain = AttachmentDomainService(attachment_repo)

    def list_by_item(
        self,
        item_id: str,
        category: Optional[str] = None,
    ) -> List[Attachment]:
        cat = AttachmentCategory(category) if category else None
        return self._repo.list_by_item(item_id, cat)

    def list_by_order(self, order_id: str) -> List[Attachment]:
        return self._repo.list_by_order(order_id)

    def get(self, attachment_id: str) -> Optional[Attachment]:
        return self._repo.find_by_id(attachment_id)

    def upload(
        self,
        order_id: str,
        item_id: str,
        category: str,
        name: str,
        content_type: str,
        data: bytes,
        uploaded_by: str = "",
    ) -> Attachment:
        attachment = Attachment(
            order_id=order_id,
            item_id=item_id,
            category=AttachmentCategory(category),
            name=name,
            content_type=content_type or "application/octet-stream",
            data=data,
            uploaded_by=uploaded_by,
        )
        self._domain.validate_upload(attachment)
        return self._repo.save(attachment)

    def delete(self, attachment_id: str) -> None:
        if not self._repo.find_by_id(attachment_id):
            raise ValidationError("Attachment not found")
        self._repo.delete(attachment_id)
