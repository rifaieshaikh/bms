from typing import List, Optional

from vaybooks.bms.domain.shared.enums import PartyRegistrationType
from vaybooks.bms.domain.shared.exceptions import (
    DuplicateVendorError,
    ValidationError,
)
from vaybooks.bms.domain.shared.party_validation import (
    normalize_banking_fields,
    normalize_party_fields,
)
from vaybooks.bms.domain.vendors.entities import Vendor, VendorInput
from vaybooks.bms.domain.vendors.repository import VendorRepository
from vaybooks.bms.domain.vendors.value_objects import VendorAccountName


class VendorDomainService:
    def __init__(self, vendor_repo: VendorRepository):
        self._vendor_repo = vendor_repo

    def create(self, vendor_input: VendorInput) -> Vendor:
        normalized = self._validate_and_normalize(vendor_input)
        self._check_duplicates(normalized, exclude_vendor_id=None)
        vendor = Vendor.from_input(normalized)
        return self._vendor_repo.save(vendor)

    def update(self, vendor_id: str, vendor_input: VendorInput) -> Vendor:
        vendor = self._vendor_repo.find_by_id(vendor_id)
        if not vendor:
            raise ValidationError("Vendor not found")
        normalized = self._validate_and_normalize(vendor_input)
        self._check_duplicates(normalized, exclude_vendor_id=vendor_id)
        vendor.apply_input(normalized)
        return self._vendor_repo.save(vendor)

    def _validate_and_normalize(self, vendor_input: VendorInput) -> VendorInput:
        party = normalize_party_fields(
            name=vendor_input.vendor_name,
            phone_number=vendor_input.phone_number,
            alternate_phone_number=vendor_input.alternate_phone_number,
            email=vendor_input.email,
            contact_person=vendor_input.contact_person,
            address_line1=vendor_input.address_line1,
            address_line2=vendor_input.address_line2,
            city=vendor_input.city,
            state_code=vendor_input.state_code,
            pincode=vendor_input.pincode,
            country=vendor_input.country,
            gstin=vendor_input.gstin,
            pan=vendor_input.pan,
            registration_type=vendor_input.registration_type,
            msme_number=vendor_input.msme_number,
        )
        banking = normalize_banking_fields(
            bank_account_holder=vendor_input.bank_account_holder,
            bank_account_number=vendor_input.bank_account_number,
            bank_ifsc=vendor_input.bank_ifsc,
            bank_name=vendor_input.bank_name,
        )

        return VendorInput(
            vendor_name=party.name,
            phone_number=party.phone_number,
            alternate_phone_number=party.alternate_phone_number,
            email=party.email,
            contact_person=party.contact_person,
            address_line1=party.address_line1,
            address_line2=party.address_line2,
            city=party.city,
            state_code=party.state_code,
            pincode=party.pincode,
            country=party.country,
            gstin=party.gstin,
            pan=party.pan,
            registration_type=party.registration_type,
            msme_number=party.msme_number,
            bank_account_holder=banking.bank_account_holder,
            bank_account_number=banking.bank_account_number,
            bank_ifsc=banking.bank_ifsc,
            bank_name=banking.bank_name,
            notes=vendor_input.notes,
        )

    def _check_duplicates(
        self, vendor_input: VendorInput, exclude_vendor_id: Optional[str]
    ) -> None:
        existing_phone = self._vendor_repo.find_by_phone(vendor_input.phone_number)
        if existing_phone and existing_phone.id != exclude_vendor_id:
            raise DuplicateVendorError(
                f"A vendor with phone {vendor_input.phone_number} already exists.",
                existing_phone.id,
            )
        if vendor_input.gstin:
            existing_gstin = self._vendor_repo.find_by_gstin(vendor_input.gstin)
            if existing_gstin and existing_gstin.id != exclude_vendor_id:
                raise DuplicateVendorError(
                    f"A vendor with GSTIN {vendor_input.gstin} already exists.",
                    existing_gstin.id,
                )

    @staticmethod
    def build_account_name(vendor: Vendor) -> str:
        return VendorAccountName(
            vendor_name=vendor.vendor_name,
            phone_number=vendor.phone_number,
        ).formatted
