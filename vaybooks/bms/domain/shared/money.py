from dataclasses import dataclass

from vaybooks.bms.domain.shared.exceptions import ValidationError


@dataclass(frozen=True)
class Money:
    amount: float

    def __post_init__(self):
        if self.amount < 0:
            raise ValidationError("Amount cannot be negative")

    @classmethod
    def zero(cls) -> "Money":
        return cls(0.0)

    def __add__(self, other: "Money") -> "Money":
        return Money(self.amount + other.amount)

    def __sub__(self, other: "Money") -> "Money":
        return Money(self.amount - other.amount)

    def __mul__(self, factor: float) -> "Money":
        return Money(self.amount * factor)

    def __float__(self) -> float:
        return self.amount


def validate_non_negative(value: float, field_name: str) -> float:
    if value < 0:
        raise ValidationError(f"{field_name} cannot be negative")
    return value
