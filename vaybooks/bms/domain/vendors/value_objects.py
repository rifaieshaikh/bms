from dataclasses import dataclass


@dataclass(frozen=True)
class VendorAccountName:
    vendor_name: str
    phone_number: str

    @property
    def formatted(self) -> str:
        return f"Vendor - {self.vendor_name} - {self.phone_number}"
