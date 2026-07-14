from dataclasses import dataclass, field
from datetime import datetime

from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import VendorRegistrationType

BUSINESS_PROFILE_ID = "default"


@dataclass
class BusinessProfile:
    legal_name: str = ""
    trade_name: str = ""
    address_line1: str = ""
    address_line2: str = ""
    city: str = ""
    state_code: str = ""
    pincode: str = ""
    country: str = "India"
    phone: str = ""
    email: str = ""
    gstin: str = ""
    pan: str = ""
    registration_type: VendorRegistrationType = VendorRegistrationType.UNREGISTERED
    id: str = BUSINESS_PROFILE_ID
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def update(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key) and value is not None:
                setattr(self, key, value)
        self.updated_at = utc_now()
