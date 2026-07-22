from typing import List, Optional

from vaybooks.bms.domain.parties.customers.entities import Customer, CustomerInput
from vaybooks.bms.domain.parties.customers.repository import CustomerRepository
from vaybooks.bms.domain.parties.customers.value_objects import CustomerAccountName
from vaybooks.bms.domain.shared.exceptions import (
    DuplicateCustomerError,
    ValidationError,
)
from vaybooks.bms.domain.shared.party_validation import normalize_party_fields


class CustomerDomainService:
    def __init__(self, customer_repo: CustomerRepository):
        self._customer_repo = customer_repo

    def create(self, customer_input: CustomerInput) -> Customer:
        normalized = self._validate_and_normalize(customer_input)
        self._check_duplicates(normalized, exclude_customer_id=None)
        customer = Customer.from_input(normalized)
        return self._customer_repo.save(customer)

    def update(self, customer_id: str, customer_input: CustomerInput) -> Customer:
        customer = self._customer_repo.find_by_id(customer_id)
        if not customer:
            raise ValidationError("Customer not found")
        normalized = self._validate_and_normalize(customer_input)
        self._check_duplicates(normalized, exclude_customer_id=customer_id)
        customer.apply_input(normalized)
        return self._customer_repo.save(customer)

    def create_without_phone(
        self,
        customer_name: str,
        alternate_phone_number: Optional[str] = None,
        notes: str = "",
    ) -> Customer:
        if not customer_name.strip():
            raise ValidationError("Customer name is required")
        customer = Customer(
            customer_name=customer_name.strip(),
            phone_number="",
            alternate_phone_number=alternate_phone_number,
            notes=notes,
        )
        return self._customer_repo.save(customer)

    def find_or_create(
        self,
        customer_name: str,
        phone_number: str,
        **kwargs,
    ) -> Customer:
        if not customer_name.strip():
            raise ValidationError("Customer name is required")
        if not phone_number.strip():
            raise ValidationError("Phone number is required")

        existing = self._customer_repo.find_by_phone(phone_number.strip())
        if existing:
            return existing

        customer_input = CustomerInput(
            customer_name=customer_name,
            phone_number=phone_number,
            alternate_phone_number=kwargs.get("alternate_phone_number"),
            address_line1=kwargs.get("address", ""),
            notes=kwargs.get("notes", ""),
        )
        return self.create(customer_input)

    def _validate_and_normalize(self, customer_input: CustomerInput) -> CustomerInput:
        normalized = normalize_party_fields(
            name=customer_input.customer_name,
            phone_number=customer_input.phone_number,
            alternate_phone_number=customer_input.alternate_phone_number,
            email=customer_input.email,
            contact_person=customer_input.contact_person,
            address_line1=customer_input.address_line1,
            address_line2=customer_input.address_line2,
            city=customer_input.city,
            state_code=customer_input.state_code,
            pincode=customer_input.pincode,
            country=customer_input.country,
            gstin=customer_input.gstin,
            pan=customer_input.pan,
            registration_type=customer_input.registration_type,
            msme_number=customer_input.msme_number,
        )
        return CustomerInput(
            customer_name=normalized.name,
            phone_number=normalized.phone_number,
            alternate_phone_number=normalized.alternate_phone_number,
            email=normalized.email,
            contact_person=normalized.contact_person,
            address_line1=normalized.address_line1,
            address_line2=normalized.address_line2,
            city=normalized.city,
            state_code=normalized.state_code,
            pincode=normalized.pincode,
            country=normalized.country,
            gstin=normalized.gstin,
            pan=normalized.pan,
            registration_type=normalized.registration_type,
            msme_number=normalized.msme_number,
            notes=customer_input.notes,
        )

    def _check_duplicates(
        self, customer_input: CustomerInput, exclude_customer_id: Optional[str]
    ) -> None:
        existing_phone = self._customer_repo.find_by_phone(customer_input.phone_number)
        if existing_phone and existing_phone.id != exclude_customer_id:
            raise DuplicateCustomerError(
                f"A customer with phone {customer_input.phone_number} already exists.",
                existing_phone.id,
            )
        if customer_input.gstin:
            existing_gstin = self._customer_repo.find_by_gstin(customer_input.gstin)
            if existing_gstin and existing_gstin.id != exclude_customer_id:
                raise DuplicateCustomerError(
                    f"A customer with GSTIN {customer_input.gstin} already exists.",
                    existing_gstin.id,
                )

    @staticmethod
    def build_account_name(customer: Customer) -> str:
        return CustomerAccountName(
            customer_name=customer.customer_name,
            phone_number=customer.phone_number,
        ).formatted
