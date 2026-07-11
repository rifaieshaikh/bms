from typing import List, Optional, Protocol

from vaybooks.bms.domain.migration.entities import ImportMappingProfile


class ImportMappingProfileRepository(Protocol):
    def save(self, profile: ImportMappingProfile) -> ImportMappingProfile: ...

    def find_by_id(self, profile_id: str) -> Optional[ImportMappingProfile]: ...

    def find_by_entity_and_name(
        self, entity_type: str, name: str
    ) -> Optional[ImportMappingProfile]: ...

    def list_by_entity(self, entity_type: str) -> List[ImportMappingProfile]: ...

    def delete(self, profile_id: str) -> None: ...
