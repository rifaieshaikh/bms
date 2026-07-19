from typing import List, Optional, Protocol

from vaybooks.bms.domain.attachments.entities import Attachment
from vaybooks.bms.domain.shared.enums import AttachmentCategory


class AttachmentRepository(Protocol):
    def save(self, attachment: Attachment) -> Attachment: ...

    def find_by_id(self, attachment_id: str) -> Optional[Attachment]: ...

    def list_by_item(
        self,
        item_id: str,
        category: Optional[AttachmentCategory] = None,
    ) -> List[Attachment]: ...

    def list_by_order(self, order_id: str) -> List[Attachment]: ...

    def delete(self, attachment_id: str) -> None: ...

    def count_by_item_category(
        self, item_id: str, category: AttachmentCategory
    ) -> int: ...
