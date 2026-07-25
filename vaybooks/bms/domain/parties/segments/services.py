from typing import List, Optional

from vaybooks.bms.domain.parties.segments.entities import (
    VALID_APPLIES_TO,
    PartySegment,
)
from vaybooks.bms.domain.parties.segments.repository import PartySegmentRepository
from vaybooks.bms.domain.shared.exceptions import ValidationError


class PartySegmentDomainService:
    def __init__(self, segment_repo: PartySegmentRepository):
        self._segment_repo = segment_repo

    def create(
        self,
        name: str,
        applies_to: Optional[List[str]] = None,
        is_active: bool = True,
    ) -> PartySegment:
        clean_name = (name or "").strip()
        if not clean_name:
            raise ValidationError("Segment name is required")
        applies = self._normalize_applies_to(applies_to)
        existing = self._segment_repo.find_by_name(clean_name)
        if existing:
            raise ValidationError(f"A segment named '{clean_name}' already exists")
        segment = PartySegment(
            name=clean_name,
            applies_to=applies,
            is_active=bool(is_active),
        )
        return self._segment_repo.save(segment)

    def update(
        self,
        segment_id: str,
        *,
        name: Optional[str] = None,
        applies_to: Optional[List[str]] = None,
        is_active: Optional[bool] = None,
    ) -> PartySegment:
        segment = self._segment_repo.find_by_id(segment_id)
        if not segment:
            raise ValidationError("Segment not found")
        kwargs = {}
        if name is not None:
            clean_name = name.strip()
            if not clean_name:
                raise ValidationError("Segment name is required")
            other = self._segment_repo.find_by_name(clean_name)
            if other and other.id != segment_id:
                raise ValidationError(f"A segment named '{clean_name}' already exists")
            kwargs["name"] = clean_name
        if applies_to is not None:
            kwargs["applies_to"] = self._normalize_applies_to(applies_to)
        if is_active is not None:
            kwargs["is_active"] = bool(is_active)
        segment.update(**kwargs)
        return self._segment_repo.save(segment)

    def list_all(self, active_only: bool = False) -> List[PartySegment]:
        return self._segment_repo.list_all(active_only=active_only)

    def list_for_party(
        self, party_type: str, active_only: bool = True
    ) -> List[PartySegment]:
        party = (party_type or "").strip().lower()
        if party not in VALID_APPLIES_TO:
            raise ValidationError(f"Invalid party type: {party_type}")
        return [
            s
            for s in self._segment_repo.list_all(active_only=active_only)
            if party in (s.applies_to or [])
        ]

    def get(self, segment_id: str) -> Optional[PartySegment]:
        return self._segment_repo.find_by_id(segment_id)

    def delete(self, segment_id: str) -> None:
        segment = self._segment_repo.find_by_id(segment_id)
        if not segment:
            raise ValidationError("Segment not found")
        self._segment_repo.delete(segment_id)

    def find_or_create(
        self, name: str, party_type: str
    ) -> PartySegment:
        """Resolve a segment by name for import; create if missing."""
        clean_name = (name or "").strip()
        if not clean_name:
            raise ValidationError("Segment name is required")
        party = (party_type or "").strip().lower()
        if party not in VALID_APPLIES_TO:
            raise ValidationError(f"Invalid party type: {party_type}")
        existing = self._segment_repo.find_by_name(clean_name)
        if existing:
            applies = list(existing.applies_to or [])
            if party not in applies:
                applies.append(party)
                existing.update(applies_to=applies)
                return self._segment_repo.save(existing)
            return existing
        return self.create(clean_name, applies_to=[party], is_active=True)

    @staticmethod
    def _normalize_applies_to(applies_to: Optional[List[str]]) -> List[str]:
        if not applies_to:
            return sorted(VALID_APPLIES_TO)
        cleaned = []
        for value in applies_to:
            v = (value or "").strip().lower()
            if v not in VALID_APPLIES_TO:
                raise ValidationError(f"Invalid applies_to value: {value}")
            if v not in cleaned:
                cleaned.append(v)
        if not cleaned:
            raise ValidationError("Segment must apply to at least one party type")
        return cleaned
