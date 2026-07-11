from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import PartyRegistrationType
from vaybooks.bms.domain.shared.india import format_address, state_name_for_code


@dataclass
class CustomerInput:
    customer_name: str
    phone_number: str
    alternate_phone_number: Optional[str] = None
    email: str = ""
    contact_person: str = ""
    address_line1: str = ""
    address_line2: str = ""
    city: str = ""
    state_code: str = ""
    pincode: str = ""
    country: str = "India"
    gstin: str = ""
    pan: str = ""
    registration_type: PartyRegistrationType = PartyRegistrationType.UNREGISTERED
    msme_number: str = ""
    notes: str = ""


@dataclass
class Customer:
    customer_name: str
    phone_number: str
    id: str = field(default_factory=lambda: uuid4().hex)
    alternate_phone_number: Optional[str] = None
    email: str = ""
    contact_person: str = ""
    address_line1: str = ""
    address_line2: str = ""
    city: str = ""
    state_code: str = ""
    pincode: str = ""
    country: str = "India"
    gstin: str = ""
    pan: str = ""
    registration_type: PartyRegistrationType = PartyRegistrationType.UNREGISTERED
    msme_number: str = ""
    legacy_address: str = ""
    notes: str = ""
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @property
    def formatted_address(self) -> str:
        structured = format_address(
            address_line1=self.address_line1,
            address_line2=self.address_line2,
            city=self.city,
            state_code=self.state_code,
            pincode=self.pincode,
            country=self.country,
        )
        return structured or self.legacy_address

    @property
    def address(self) -> str:
        return self.formatted_address

    @property
    def state_name(self) -> str:
        return state_name_for_code(self.state_code)

    def update(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key) and value is not None:
                setattr(self, key, value)
        self.updated_at = utc_now()

    @classmethod
    def from_input(cls, customer_input: CustomerInput) -> "Customer":
        return cls(
            customer_name=customer_input.customer_name.strip(),
            phone_number=customer_input.phone_number,
            alternate_phone_number=customer_input.alternate_phone_number,
            email=customer_input.email.strip(),
            contact_person=customer_input.contact_person.strip(),
            address_line1=customer_input.address_line1.strip(),
            address_line2=customer_input.address_line2.strip(),
            city=customer_input.city.strip(),
            state_code=customer_input.state_code,
            pincode=customer_input.pincode,
            country=customer_input.country.strip() or "India",
            gstin=customer_input.gstin,
            pan=customer_input.pan,
            registration_type=customer_input.registration_type,
            msme_number=customer_input.msme_number.strip(),
            notes=customer_input.notes,
        )

    def apply_input(self, customer_input: CustomerInput) -> None:
        self.update(
            customer_name=customer_input.customer_name.strip(),
            phone_number=customer_input.phone_number,
            alternate_phone_number=customer_input.alternate_phone_number,
            email=customer_input.email.strip(),
            contact_person=customer_input.contact_person.strip(),
            address_line1=customer_input.address_line1.strip(),
            address_line2=customer_input.address_line2.strip(),
            city=customer_input.city.strip(),
            state_code=customer_input.state_code,
            pincode=customer_input.pincode,
            country=customer_input.country.strip() or "India",
            gstin=customer_input.gstin,
            pan=customer_input.pan,
            registration_type=customer_input.registration_type,
            msme_number=customer_input.msme_number.strip(),
            notes=customer_input.notes,
        )
