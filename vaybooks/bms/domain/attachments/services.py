from vaybooks.bms.domain.attachments.entities import (
    FILE_OUT_MAX_BYTES,
    IMAGE_CATEGORIES,
    IMAGE_MAX_BYTES,
    MAX_FILES_PER_IMAGE_CATEGORY,
    Attachment,
)
from vaybooks.bms.domain.attachments.repository import AttachmentRepository
from vaybooks.bms.domain.shared.enums import AttachmentCategory
from vaybooks.bms.domain.shared.exceptions import ValidationError


class AttachmentDomainService:
    def __init__(self, repo: AttachmentRepository):
        self._repo = repo

    def validate_upload(self, attachment: Attachment) -> None:
        if not attachment.order_id or not attachment.item_id:
            raise ValidationError("Attachment must belong to an order item")
        if not attachment.name:
            raise ValidationError("Attachment name is required")
        if not attachment.data:
            raise ValidationError("Attachment data is required")

        if attachment.category in IMAGE_CATEGORIES:
            if attachment.size_bytes > IMAGE_MAX_BYTES:
                raise ValidationError(
                    f"{attachment.name} exceeds the 5 MB image limit"
                )
            count = self._repo.count_by_item_category(
                attachment.item_id, attachment.category
            )
            if count >= MAX_FILES_PER_IMAGE_CATEGORY:
                raise ValidationError(
                    f"At most {MAX_FILES_PER_IMAGE_CATEGORY} "
                    f"{attachment.category.value} files are allowed"
                )
        elif attachment.category == AttachmentCategory.FILE_OUT:
            if attachment.size_bytes > FILE_OUT_MAX_BYTES:
                raise ValidationError(
                    f"{attachment.name} exceeds the 20 MB file-out limit"
                )
        else:
            raise ValidationError("Unknown attachment category")
