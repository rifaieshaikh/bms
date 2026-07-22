from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import PartyRegistrationType
from vaybooks.bms.domain.shared.india import format_address, state_name_for_code


@dataclass
class VendorInput:
    vendor_name: str
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
    bank_account_holder: str = ""
    bank_account_number: str = ""
    bank_ifsc: str = ""
    bank_name: str = ""
    notes: str = ""


@dataclass
class Vendor:
    vendor_name: str
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
    bank_account_holder: str = ""
    bank_account_number: str = ""
    bank_ifsc: str = ""
    bank_name: str = ""
    notes: str = ""
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

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
    def from_input(cls, vendor_input: VendorInput) -> "Vendor":
        return cls(
            vendor_name=vendor_input.vendor_name.strip(),
            phone_number=vendor_input.phone_number,
            alternate_phone_number=vendor_input.alternate_phone_number,
            email=vendor_input.email.strip(),
            contact_person=vendor_input.contact_person.strip(),
            address_line1=vendor_input.address_line1.strip(),
            address_line2=vendor_input.address_line2.strip(),
            city=vendor_input.city.strip(),
            state_code=vendor_input.state_code,
            pincode=vendor_input.pincode,
            country=vendor_input.country.strip() or "India",
            gstin=vendor_input.gstin,
            pan=vendor_input.pan,
            registration_type=vendor_input.registration_type,
            msme_number=vendor_input.msme_number.strip(),
            bank_account_holder=vendor_input.bank_account_holder.strip(),
            bank_account_number=vendor_input.bank_account_number,
            bank_ifsc=vendor_input.bank_ifsc,
            bank_name=vendor_input.bank_name.strip(),
            notes=vendor_input.notes,
        )

    def apply_input(self, vendor_input: VendorInput) -> None:
        self.update(
            vendor_name=vendor_input.vendor_name.strip(),
            phone_number=vendor_input.phone_number,
            alternate_phone_number=vendor_input.alternate_phone_number,
            email=vendor_input.email.strip(),
            contact_person=vendor_input.contact_person.strip(),
            address_line1=vendor_input.address_line1.strip(),
            address_line2=vendor_input.address_line2.strip(),
            city=vendor_input.city.strip(),
            state_code=vendor_input.state_code,
            pincode=vendor_input.pincode,
            country=vendor_input.country.strip() or "India",
            gstin=vendor_input.gstin,
            pan=vendor_input.pan,
            registration_type=vendor_input.registration_type,
            msme_number=vendor_input.msme_number.strip(),
            bank_account_holder=vendor_input.bank_account_holder.strip(),
            bank_account_number=vendor_input.bank_account_number,
            bank_ifsc=vendor_input.bank_ifsc,
            bank_name=vendor_input.bank_name.strip(),
            notes=vendor_input.notes,
        )
