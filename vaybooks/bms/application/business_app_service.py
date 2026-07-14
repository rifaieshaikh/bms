from typing import Optional

from vaybooks.bms.domain.business.entities import BUSINESS_PROFILE_ID, BusinessProfile
from vaybooks.bms.domain.business.repository import BusinessProfileRepository
from vaybooks.bms.domain.shared.enums import VendorRegistrationType
from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.domain.shared.india import (
    normalize_indian_phone,
    validate_gstin,
    validate_pan,
    validate_pincode,
    validate_state_code,
)


class BusinessAppService:
    def __init__(self, repo: BusinessProfileRepository):
        self._repo = repo

    def get_profile(self) -> BusinessProfile:
        profile = self._repo.get()
        if profile:
            return profile
        return BusinessProfile(id=BUSINESS_PROFILE_ID)

    def update_profile(
        self,
        *,
        legal_name: str = "",
        trade_name: str = "",
        address_line1: str = "",
        address_line2: str = "",
        city: str = "",
        state_code: str = "",
        pincode: str = "",
        country: str = "India",
        phone: str = "",
        email: str = "",
        gstin: str = "",
        pan: str = "",
        registration_type: VendorRegistrationType = VendorRegistrationType.UNREGISTERED,
    ) -> BusinessProfile:
        legal_name = legal_name.strip()
        trade_name = trade_name.strip()
        state_code = validate_state_code(state_code) if state_code else ""
        pin = validate_pan(pan) if (pan or "").strip() else ""
        gst = (gstin or "").strip().upper()
        if registration_type == VendorRegistrationType.REGISTERED:
            if not gst:
                raise ValidationError("GSTIN is required for registered businesses")
            if not state_code:
                raise ValidationError("State is required for registered businesses")
            gst = validate_gstin(gst, state_code=state_code, pan=pin or None)
        elif gst:
            gst = validate_gstin(gst, state_code=state_code or None, pan=pin or None)
        phone_norm = ""
        if (phone or "").strip():
            phone_norm = normalize_indian_phone(phone)
        pincode_norm = validate_pincode(pincode) if (pincode or "").strip() else ""

        profile = self.get_profile()
        profile.update(
            legal_name=legal_name,
            trade_name=trade_name,
            address_line1=address_line1.strip(),
            address_line2=address_line2.strip(),
            city=city.strip(),
            state_code=state_code,
            pincode=pincode_norm,
            country=(country or "India").strip() or "India",
            phone=phone_norm,
            email=email.strip(),
            gstin=gst,
            pan=pin,
            registration_type=registration_type,
        )
        return self._repo.save(profile)
