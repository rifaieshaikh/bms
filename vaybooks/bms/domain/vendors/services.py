from typing import Optional

from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.domain.vendors.entities import Vendor
from vaybooks.bms.domain.vendors.repository import VendorRepository
from vaybooks.bms.domain.vendors.value_objects import VendorAccountName


class VendorDomainService:
    def __init__(self, vendor_repo: VendorRepository):
        self._vendor_repo = vendor_repo

    def find_or_create(
        self,
        vendor_name: str,
        phone_number: str,
        alternate_phone_number: Optional[str] = None,
        address: str = "",
        notes: str = "",
    ) -> Vendor:
        if not vendor_name.strip():
            raise ValidationError("Vendor name is required")
        if not phone_number.strip():
            raise ValidationError("Phone number is required")
        self.validate_phone_number(phone_number)

        existing = self._vendor_repo.find_by_phone(phone_number.strip())
        if existing:
            return existing

        vendor = Vendor(
            vendor_name=vendor_name.strip(),
            phone_number=phone_number.strip(),
            alternate_phone_number=alternate_phone_number,
            address=address,
            notes=notes,
        )
        return self._vendor_repo.save(vendor)

    @staticmethod
    def validate_phone_number(phone_number: str) -> None:
        if not phone_number.strip().isdigit():
            raise ValidationError(
                "System rejects vendor submission when phone_number contains "
                "non-numeric characters."
            )

    @staticmethod
    def build_account_name(vendor: Vendor) -> str:
        return VendorAccountName(
            vendor_name=vendor.vendor_name,
            phone_number=vendor.phone_number,
        ).formatted
