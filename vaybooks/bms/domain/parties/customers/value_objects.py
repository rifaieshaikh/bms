from dataclasses import dataclass


@dataclass(frozen=True)
class CustomerAccountName:
    customer_name: str
    phone_number: str = ""

    @property
    def formatted(self) -> str:
        if (self.phone_number or "").strip():
            return f"Customer - {self.customer_name} - {self.phone_number}"
        return f"Customer - {self.customer_name}"
