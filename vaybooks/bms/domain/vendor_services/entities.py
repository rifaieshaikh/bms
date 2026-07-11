from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.item_tax import ItemTaxProfile


@dataclass
class VendorService:
    """A material or service that can be purchased from a vendor.

    Each service maps to the expense account that should be debited when a
    vendor is paid for it (e.g. Stitching -> Stitching Expense).
    """

    service_name: str
    expense_account_id: str
    tax_profile: ItemTaxProfile = field(default_factory=ItemTaxProfile)
    is_active: bool = True
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def update(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key) and value is not None:
                setattr(self, key, value)
        self.updated_at = utc_now()
