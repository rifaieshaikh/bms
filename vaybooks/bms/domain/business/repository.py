from typing import Optional, Protocol

from vaybooks.bms.domain.business.entities import BusinessProfile


class BusinessProfileRepository(Protocol):
    def get(self) -> Optional[BusinessProfile]: ...

    def save(self, profile: BusinessProfile) -> BusinessProfile: ...
