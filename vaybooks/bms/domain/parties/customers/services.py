from typing import List, Optional

from vaybooks.bms.domain.parties.customers.entities import Customer, CustomerInput
from vaybooks.bms.domain.parties.customers.repository import CustomerRepository
from vaybooks.bms.domain.parties.customers.value_objects import CustomerAccountName
from vaybooks.bms.domain.shared.exceptions import (
    DuplicateCustomerError,
    ValidationError,
)
from vaybooks.bms.domain.shared.party_location import require_location_ids
from vaybooks.bms.domain.shared.party_validation import normalize_party_fields


class CustomerDomainService:
    def __init__(self, customer_repo: CustomerRepository):
        self._customer_repo = customer_repo

    def create(
        self,
        customer_input: CustomerInput,
        *,
        require_name: bool = True,
        require_phone: bool = True,
    ) -> Customer:
        normalized = self._validate_and_normalize(
            customer_input,
            require_name=require_name,
            require_phone=require_phone,
        )
        self._check_duplicates(normalized, exclude_customer_id=None)
        customer = Customer.from_input(normalized)
        return self._customer_repo.save(customer)

    def update(
        self,
        customer_id: str,
        customer_input: CustomerInput,
        *,
        require_name: bool = True,
        require_phone: bool = True,
    ) -> Customer:
        customer = self._customer_repo.find_by_id(customer_id)
        if not customer:
            raise ValidationError("Customer not found")
        normalized = self._validate_and_normalize(
            customer_input,
            require_name=require_name,
            require_phone=require_phone,
        )
        self._check_duplicates(normalized, exclude_customer_id=customer_id)
        customer.apply_input(normalized)
        return self._customer_repo.save(customer)

    def create_without_phone(
        self,
        customer_name: str,
        alternate_phone_number: Optional[str] = None,
        notes: str = "",
    ) -> Customer:
        """Create a customer with name only (phone optional path)."""
        return self.create(
            CustomerInput(
                customer_name=customer_name,
                phone_number="",
                alternate_phone_number=alternate_phone_number,
                notes=notes,
            ),
            require_name=True,
            require_phone=False,
        )

    def find_or_create(
        self,
        customer_name: str,
        phone_number: str,
        *,
        require_name: bool = True,
        require_phone: bool = True,
        **kwargs,
    ) -> Customer:
        phone = (phone_number or "").strip()
        if phone:
            existing = self._customer_repo.find_by_phone(phone)
            if existing:
                return existing

        customer_input = CustomerInput(
            customer_name=customer_name or "",
            phone_number=phone,
            alternate_phone_number=kwargs.get("alternate_phone_number"),
            address_line1=kwargs.get("address", ""),
            notes=kwargs.get("notes", ""),
            location_ids=list(kwargs.get("location_ids") or []),
        )
        return self.create(
            customer_input,
            require_name=require_name,
            require_phone=require_phone,
        )

    def _validate_and_normalize(
        self,
        customer_input: CustomerInput,
        *,
        require_name: bool = True,
        require_phone: bool = True,
    ) -> CustomerInput:
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
            require_name=require_name,
            require_phone=require_phone,
            require_at_least_one_identity=False,
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
            segment_ids=list(customer_input.segment_ids or []),
            location_ids=require_location_ids(customer_input.location_ids),
            is_commission_agent=bool(customer_input.is_commission_agent),
        )

    def _check_duplicates(
        self, customer_input: CustomerInput, exclude_customer_id: Optional[str]
    ) -> None:
        if (customer_input.phone_number or "").strip():
            existing_phone = self._customer_repo.find_by_phone(
                customer_input.phone_number
            )
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
