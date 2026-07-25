from typing import List, Optional

from vaybooks.bms.domain.parties.segments.entities import PartySegment
from vaybooks.bms.domain.parties.segments.repository import PartySegmentRepository
from vaybooks.bms.domain.parties.segments.services import PartySegmentDomainService


class PartySegmentAppService:
    def __init__(self, segment_repo: PartySegmentRepository):
        self._segment_repo = segment_repo
        self._domain = PartySegmentDomainService(segment_repo)

    def create_segment(
        self,
        name: str,
        applies_to: Optional[List[str]] = None,
        is_active: bool = True,
    ) -> PartySegment:
        return self._domain.create(name, applies_to=applies_to, is_active=is_active)

    def update_segment(
        self,
        segment_id: str,
        *,
        name: Optional[str] = None,
        applies_to: Optional[List[str]] = None,
        is_active: Optional[bool] = None,
    ) -> PartySegment:
        return self._domain.update(
            segment_id,
            name=name,
            applies_to=applies_to,
            is_active=is_active,
        )

    def list_segments(self, active_only: bool = False) -> List[PartySegment]:
        return self._domain.list_all(active_only=active_only)

    def list_for_party(
        self, party_type: str, active_only: bool = True
    ) -> List[PartySegment]:
        return self._domain.list_for_party(party_type, active_only=active_only)

    def get_segment(self, segment_id: str) -> Optional[PartySegment]:
        return self._domain.get(segment_id)

    def delete_segment(self, segment_id: str) -> None:
        self._domain.delete(segment_id)

    def find_or_create(self, name: str, party_type: str) -> PartySegment:
        return self._domain.find_or_create(name, party_type)

    def names_for_ids(self, segment_ids: List[str]) -> List[str]:
        """Return segment names for the given ids, preserving order and skipping missing."""
        names: List[str] = []
        for sid in segment_ids or []:
            segment = self._segment_repo.find_by_id(sid)
            if segment:
                names.append(segment.name)
        return names
