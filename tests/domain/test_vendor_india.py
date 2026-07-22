"""Tests for India-standard vendor validation and creation."""

from typing import Dict, List, Optional

import pytest

from vaybooks.bms.domain.shared.enums import VendorRegistrationType
from vaybooks.bms.domain.shared.exceptions import (
    DuplicateVendorError,
    ValidationError,
)
from vaybooks.bms.domain.shared.india import (
    format_address,
    normalize_indian_phone,
    validate_gstin,
    validate_pan,
    validate_pincode,
)
from vaybooks.bms.domain.parties.vendors.entities import Vendor, VendorInput
from vaybooks.bms.domain.parties.vendors.services import VendorDomainService


class InMemoryVendorRepository:
    def __init__(self):
        self._store: Dict[str, Vendor] = {}

    def save(self, vendor: Vendor) -> Vendor:
        self._store[vendor.id] = vendor
        return vendor

    def find_by_id(self, vendor_id: str) -> Optional[Vendor]:
        return self._store.get(vendor_id)

    def find_by_phone(self, phone: str) -> Optional[Vendor]:
        for vendor in self._store.values():
            if vendor.phone_number == phone:
                return vendor
        return None

    def find_by_gstin(self, gstin: str) -> Optional[Vendor]:
        if not gstin:
            return None
        upper = gstin.upper()
        for vendor in self._store.values():
            if vendor.gstin == upper:
                return vendor
        return None

    def search(self, query: str) -> List[Vendor]:
        return list(self._store.values())

    def list_all(self) -> List[Vendor]:
        return list(self._store.values())


def _vendor_input(**kwargs) -> VendorInput:
    defaults = {
        "vendor_name": "Acme Supplies",
        "phone_number": "9876543210",
        "address_line1": "12 MG Road",
        "city": "Mumbai",
        "state_code": "27",
        "pincode": "400001",
    }
    defaults.update(kwargs)
    return VendorInput(**defaults)


def test_normalize_indian_phone_strips_country_code():
    assert normalize_indian_phone("+91 98765 43210") == "9876543210"


def test_normalize_indian_phone_rejects_invalid():
    with pytest.raises(ValidationError):
        normalize_indian_phone("12345")


def test_validate_pincode_requires_six_digits():
    assert validate_pincode("400001") == "400001"
    with pytest.raises(ValidationError):
        validate_pincode("40001")


def test_validate_pan_format():
    assert validate_pan("ABCDE1234F") == "ABCDE1234F"
    with pytest.raises(ValidationError):
        validate_pan("INVALID")


def test_validate_gstin_state_mismatch():
    with pytest.raises(ValidationError):
        validate_gstin("27AAAAA0000A1Z5", state_code="09")


def test_format_address_joins_structured_fields():
    result = format_address(
        address_line1="12 MG Road",
        city="Mumbai",
        state_code="27",
        pincode="400001",
        country="India",
    )
    assert "12 MG Road" in result
    assert "Mumbai" in result
    assert "Maharashtra" in result
    assert "400001" in result


def test_create_vendor_success():
    repo = InMemoryVendorRepository()
    service = VendorDomainService(repo)
    vendor = service.create(_vendor_input())
    assert vendor.vendor_name == "Acme Supplies"
    assert vendor.phone_number == "9876543210"
    assert vendor.formatted_address


def test_registered_vendor_requires_gstin():
    repo = InMemoryVendorRepository()
    service = VendorDomainService(repo)
    with pytest.raises(ValidationError, match="GSTIN is required"):
        service.create(
            _vendor_input(
                registration_type=VendorRegistrationType.REGISTERED,
                gstin="",
            )
        )


def test_create_vendor_with_valid_gstin():
    repo = InMemoryVendorRepository()
    service = VendorDomainService(repo)
    vendor = service.create(
        _vendor_input(
            registration_type=VendorRegistrationType.REGISTERED,
            gstin="27AAAAA0000A1Z5",
            pan="AAAAA0000A",
        )
    )
    assert vendor.gstin == "27AAAAA0000A1Z5"


def test_minimal_vendor_name_phone_only_succeeds():
    repo = InMemoryVendorRepository()
    service = VendorDomainService(repo)
    vendor = service.create(
        VendorInput(vendor_name="Quick Vendor", phone_number="9876543210")
    )
    assert vendor.vendor_name == "Quick Vendor"
    assert vendor.phone_number == "9876543210"
    assert not vendor.address_line1


def test_duplicate_phone_raises_with_existing_id():
    repo = InMemoryVendorRepository()
    service = VendorDomainService(repo)
    first = service.create(_vendor_input())
    with pytest.raises(DuplicateVendorError) as exc:
        service.create(_vendor_input(vendor_name="Other Vendor"))
    assert exc.value.existing_vendor_id == first.id


def test_duplicate_gstin_raises():
    repo = InMemoryVendorRepository()
    service = VendorDomainService(repo)
    first = service.create(
        _vendor_input(
            phone_number="9876543210",
            registration_type=VendorRegistrationType.REGISTERED,
            gstin="27AAAAA0000A1Z5",
            pan="AAAAA0000A",
        )
    )
    with pytest.raises(DuplicateVendorError) as exc:
        service.create(
            _vendor_input(
                phone_number="9123456780",
                registration_type=VendorRegistrationType.REGISTERED,
                gstin="27AAAAA0000A1Z5",
                pan="AAAAA0000A",
            )
        )
    assert exc.value.existing_vendor_id == first.id


def test_update_allows_same_vendor_phone():
    repo = InMemoryVendorRepository()
    service = VendorDomainService(repo)
    vendor = service.create(_vendor_input())
    updated = service.update(
        vendor.id,
        _vendor_input(vendor_name="Acme Supplies Pvt Ltd"),
    )
    assert updated.vendor_name == "Acme Supplies Pvt Ltd"
