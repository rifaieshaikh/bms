from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.india import format_address, state_name_for_code


@dataclass
class DeliveryPartnerInput:
    partner_name: str
    phone_number: str
    legal_display_name: str = ""
    alternate_phone_number: Optional[str] = None
    email: str = ""
    address_line1: str = ""
    address_line2: str = ""
    city: str = ""
    state_code: str = ""
    pincode: str = ""
    country: str = "India"
    gstin: str = ""
    pan: str = ""
    default_expense_ledger_id: str = ""
    payment_terms: str = ""
    is_active: bool = True
    notes: str = ""
    location_ids: List[str] = field(default_factory=list)


@dataclass
class DeliveryPartner:
    partner_name: str
    phone_number: str
    id: str = field(default_factory=lambda: uuid4().hex)
    legal_display_name: str = ""
    alternate_phone_number: Optional[str] = None
    email: str = ""
    address_line1: str = ""
    address_line2: str = ""
    city: str = ""
    state_code: str = ""
    pincode: str = ""
    country: str = "India"
    gstin: str = ""
    pan: str = ""
    default_expense_ledger_id: str = ""
    payment_terms: str = ""
    is_active: bool = True
    notes: str = ""
    location_ids: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @property
    def display_name(self) -> str:
        return (self.legal_display_name or self.partner_name).strip()

    @property
    def formatted_address(self) -> str:
        return format_address(
            address_line1=self.address_line1,
            address_line2=self.address_line2,
            city=self.city,
            state_code=self.state_code,
            pincode=self.pincode,
            country=self.country,
        )

    @property
    def state_name(self) -> str:
        return state_name_for_code(self.state_code)

    def update(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key) and value is not None:
                setattr(self, key, value)
        self.updated_at = utc_now()

    @classmethod
    def from_input(cls, data: DeliveryPartnerInput) -> "DeliveryPartner":
        return cls(
            partner_name=data.partner_name.strip(),
            phone_number=data.phone_number,
            legal_display_name=(data.legal_display_name or data.partner_name).strip(),
            alternate_phone_number=data.alternate_phone_number,
            email=data.email.strip(),
            address_line1=data.address_line1.strip(),
            address_line2=data.address_line2.strip(),
            city=data.city.strip(),
            state_code=data.state_code,
            pincode=data.pincode,
            country=data.country.strip() or "India",
            gstin=data.gstin,
            pan=data.pan,
            default_expense_ledger_id=data.default_expense_ledger_id.strip(),
            payment_terms=data.payment_terms.strip(),
            is_active=bool(data.is_active),
            notes=data.notes,
            location_ids=list(data.location_ids or []),
        )

    def apply_input(self, data: DeliveryPartnerInput) -> None:
        self.update(
            partner_name=data.partner_name.strip(),
            phone_number=data.phone_number,
            legal_display_name=(data.legal_display_name or data.partner_name).strip(),
            alternate_phone_number=data.alternate_phone_number,
            email=data.email.strip(),
            address_line1=data.address_line1.strip(),
            address_line2=data.address_line2.strip(),
            city=data.city.strip(),
            state_code=data.state_code,
            pincode=data.pincode,
            country=data.country.strip() or "India",
            gstin=data.gstin,
            pan=data.pan,
            default_expense_ledger_id=data.default_expense_ledger_id.strip(),
            payment_terms=data.payment_terms.strip(),
            is_active=bool(data.is_active),
            notes=data.notes,
            location_ids=list(data.location_ids or []),
        )
