from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, List
from uuid import uuid4

from vaybooks.bms.domain.shared.date_utils import utc_now

# Activity catalogs an employee assignment can point at.
SOURCE_STORE = "store"
SOURCE_CUSTOMIZATION = "customization"
SOURCE_PROJECT = "project"
ACTIVITY_SOURCES = (SOURCE_STORE, SOURCE_CUSTOMIZATION, SOURCE_PROJECT)


@dataclass(frozen=True)
class WorkerActivityRef:
    """Source-qualified pointer to an activity catalog entry.

    ``source`` disambiguates ids across the store / customization / project
    catalogs so lookups and filters never mix catalogs.
    """

    activity_id: str
    source: str = SOURCE_CUSTOMIZATION


def normalize_activity_refs(values: Iterable) -> List[WorkerActivityRef]:
    """Coerce refs, dicts, or legacy plain ids into deduped WorkerActivityRefs.

    Plain string ids are treated as customization activities — the only
    catalog that existed before refs were source-qualified.
    """
    refs: List[WorkerActivityRef] = []
    seen: set[tuple[str, str]] = set()
    for value in values or []:
        if isinstance(value, WorkerActivityRef):
            ref = value
        elif isinstance(value, dict):
            ref = WorkerActivityRef(
                activity_id=str(value.get("activity_id") or "").strip(),
                source=str(value.get("source") or SOURCE_CUSTOMIZATION).strip(),
            )
        else:
            ref = WorkerActivityRef(activity_id=str(value or "").strip())
        if not ref.activity_id:
            continue
        source = ref.source if ref.source in ACTIVITY_SOURCES else SOURCE_CUSTOMIZATION
        if source != ref.source:
            ref = WorkerActivityRef(activity_id=ref.activity_id, source=source)
        key = (ref.source, ref.activity_id)
        if key in seen:
            continue
        seen.add(key)
        refs.append(ref)
    return refs


@dataclass
class Worker:
    worker_name: str
    activity_refs: List[WorkerActivityRef] = field(default_factory=list)
    is_active: bool = True
    default_hourly_rate: float = 0.0
    # Optional link to identity User for system login.
    linked_user_id: str = ""
    location_ids: List[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.activity_refs = normalize_activity_refs(self.activity_refs)

    @property
    def activity_ids(self) -> List[str]:
        """All assigned activity ids regardless of source (legacy shape)."""
        return [ref.activity_id for ref in self.activity_refs]

    def activity_ids_for_source(self, source: str) -> List[str]:
        return [
            ref.activity_id for ref in self.activity_refs if ref.source == source
        ]

    def has_activity(self, activity_id: str, source: str) -> bool:
        return any(
            ref.activity_id == activity_id and ref.source == source
            for ref in self.activity_refs
        )

    def update(
        self,
        *,
        worker_name: str,
        activity_refs: Iterable,
        is_active: bool,
        default_hourly_rate: float = 0.0,
        linked_user_id: str | None = None,
        location_ids: Iterable[str] | None = None,
    ) -> None:
        self.worker_name = (worker_name or "").strip()
        self.activity_refs = normalize_activity_refs(activity_refs)
        self.is_active = bool(is_active)
        self.default_hourly_rate = float(default_hourly_rate or 0.0)
        if linked_user_id is not None:
            self.linked_user_id = (linked_user_id or "").strip()
        if location_ids is not None:
            self.location_ids = [
                str(i).strip() for i in location_ids if str(i).strip()
            ]
        self.updated_at = utc_now()
