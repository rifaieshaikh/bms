from typing import Optional

from vaybooks.bms.domain.customers.entities import Customer
from vaybooks.bms.domain.customers.repository import CustomerRepository
from vaybooks.bms.domain.customers.value_objects import CustomerAccountName
from vaybooks.bms.domain.shared.exceptions import ValidationError


class CustomerDomainService:
    def __init__(self, customer_repo: CustomerRepository):
        self._customer_repo = customer_repo

    def find_or_create(
        self,
        customer_name: str,
        phone_number: str,
        alternate_phone_number: Optional[str] = None,
        address: str = "",
        notes: str = "",
    ) -> Customer:
        if not customer_name.strip():
            raise ValidationError("Customer name is required")
        if not phone_number.strip():
            raise ValidationError("Phone number is required")

        existing = self._customer_repo.find_by_phone(phone_number.strip())
        if existing:
            return existing

        customer = Customer(
            customer_name=customer_name.strip(),
            phone_number=phone_number.strip(),
            alternate_phone_number=alternate_phone_number,
            address=address,
            notes=notes,
        )
        return self._customer_repo.save(customer)

    @staticmethod
    def build_account_name(customer: Customer) -> str:
        return CustomerAccountName(
            customer_name=customer.customer_name,
            phone_number=customer.phone_number,
        ).formatted
