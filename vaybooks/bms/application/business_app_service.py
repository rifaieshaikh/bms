from typing import Optional

from vaybooks.bms.domain.business.entities import BUSINESS_PROFILE_ID, BusinessProfile
from vaybooks.bms.domain.business.repository import BusinessProfileRepository
from vaybooks.bms.domain.shared.enums import VendorRegistrationType


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
        legal_name: str = "",
        gstin: str = "",
        state_code: str = "",
        registration_type: VendorRegistrationType = VendorRegistrationType.UNREGISTERED,
    ) -> BusinessProfile:
        profile = self.get_profile()
        profile.update(
            legal_name=legal_name.strip(),
            gstin=gstin.strip().upper(),
            state_code=state_code.strip(),
            registration_type=registration_type,
        )
        return self._repo.save(profile)
