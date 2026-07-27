from dataclasses import dataclass


@dataclass(frozen=True)
class CustomerAccountName:
    customer_name: str
    phone_number: str = ""

    @property
    def formatted(self) -> str:
        name = (self.customer_name or "").strip() or "Unnamed"
        phone = (self.phone_number or "").strip()
        if phone:
            return f"Customer - {name} - {phone}"
        return f"Customer - {name}"
