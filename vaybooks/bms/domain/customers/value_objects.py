from dataclasses import dataclass


@dataclass(frozen=True)
class CustomerAccountName:
    customer_name: str
    phone_number: str

    @property
    def formatted(self) -> str:
        return f"Customer - {self.customer_name} - {self.phone_number}"
