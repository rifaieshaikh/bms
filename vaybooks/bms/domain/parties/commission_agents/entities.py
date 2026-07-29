from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now
from vaybooks.bms.domain.shared.enums import PartyRegistrationType
from vaybooks.bms.domain.shared.india import format_address, state_name_for_code


@dataclass
class CommissionAgentInput:
    agent_name: str
    phone_number: str
    alternate_phone_number: Optional[str] = None
    email: str = ""
    contact_person: str = ""
    address_line1: str = ""
    address_line2: str = ""
    city: str = ""
    state_code: str = ""
    pincode: str = ""
    country: str = "India"
    gstin: str = ""
    pan: str = ""
    registration_type: PartyRegistrationType = PartyRegistrationType.UNREGISTERED
    msme_number: str = ""
    bank_account_holder: str = ""
    bank_account_number: str = ""
    bank_ifsc: str = ""
    bank_name: str = ""
    notes: str = ""
    default_commission_type: str = "percentage"
    default_commission_rate: float = 0.0
    segment_ids: List[str] = field(default_factory=list)
    source_customer_id: str = ""


@dataclass
class CommissionAgent:
    agent_name: str
    phone_number: str
    id: str = field(default_factory=lambda: uuid4().hex)
    alternate_phone_number: Optional[str] = None
    email: str = ""
    contact_person: str = ""
    address_line1: str = ""
    address_line2: str = ""
    city: str = ""
    state_code: str = ""
    pincode: str = ""
    country: str = "India"
    gstin: str = ""
    pan: str = ""
    registration_type: PartyRegistrationType = PartyRegistrationType.UNREGISTERED
    msme_number: str = ""
    bank_account_holder: str = ""
    bank_account_number: str = ""
    bank_ifsc: str = ""
    bank_name: str = ""
    notes: str = ""
    default_commission_type: str = "percentage"
    default_commission_rate: float = 0.0
    segment_ids: List[str] = field(default_factory=list)
    segment_names: List[str] = field(default_factory=list)
    source_customer_id: str = ""
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    @property
    def formatted_address(self) -> str:
        return format_address(
            address_line1=self.address_line1,
            address_line2=self.address_line2,
            city=self.city,
            state_code=self.state_code,
            pincode=self.pincode,
            country=self.country,
        )

    @property
    def state_name(self) -> str:
        return state_name_for_code(self.state_code)

    def update(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key) and value is not None:
                setattr(self, key, value)
        self.updated_at = utc_now()

    @classmethod
    def from_input(cls, agent_input: CommissionAgentInput) -> "CommissionAgent":
        return cls(
            agent_name=agent_input.agent_name.strip(),
            phone_number=agent_input.phone_number,
            alternate_phone_number=agent_input.alternate_phone_number,
            email=agent_input.email.strip(),
            contact_person=agent_input.contact_person.strip(),
            address_line1=agent_input.address_line1.strip(),
            address_line2=agent_input.address_line2.strip(),
            city=agent_input.city.strip(),
            state_code=agent_input.state_code,
            pincode=agent_input.pincode,
            country=agent_input.country.strip() or "India",
            gstin=agent_input.gstin,
            pan=agent_input.pan,
            registration_type=agent_input.registration_type,
            msme_number=agent_input.msme_number.strip(),
            bank_account_holder=agent_input.bank_account_holder.strip(),
            bank_account_number=agent_input.bank_account_number,
            bank_ifsc=agent_input.bank_ifsc,
            bank_name=agent_input.bank_name.strip(),
            notes=agent_input.notes,
            default_commission_type=(
                agent_input.default_commission_type or "percentage"
            ).strip().lower(),
            default_commission_rate=float(agent_input.default_commission_rate or 0),
            segment_ids=list(agent_input.segment_ids or []),
            source_customer_id=(agent_input.source_customer_id or "").strip(),
        )

    def apply_input(self, agent_input: CommissionAgentInput) -> None:
        self.update(
            agent_name=agent_input.agent_name.strip(),
            phone_number=agent_input.phone_number,
            alternate_phone_number=agent_input.alternate_phone_number,
            email=agent_input.email.strip(),
            contact_person=agent_input.contact_person.strip(),
            address_line1=agent_input.address_line1.strip(),
            address_line2=agent_input.address_line2.strip(),
            city=agent_input.city.strip(),
            state_code=agent_input.state_code,
            pincode=agent_input.pincode,
            country=agent_input.country.strip() or "India",
            gstin=agent_input.gstin,
            pan=agent_input.pan,
            registration_type=agent_input.registration_type,
            msme_number=agent_input.msme_number.strip(),
            bank_account_holder=agent_input.bank_account_holder.strip(),
            bank_account_number=agent_input.bank_account_number,
            bank_ifsc=agent_input.bank_ifsc,
            bank_name=agent_input.bank_name.strip(),
            notes=agent_input.notes,
            default_commission_type=(
                agent_input.default_commission_type or "percentage"
            ).strip().lower(),
            default_commission_rate=float(agent_input.default_commission_rate or 0),
            segment_ids=list(agent_input.segment_ids or []),
            source_customer_id=(
                agent_input.source_customer_id
                if agent_input.source_customer_id is not None
                else self.source_customer_id
            ),
        )
