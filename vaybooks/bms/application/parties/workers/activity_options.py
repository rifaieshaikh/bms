"""Module-aware activity options for the employee create/edit picker.

The employee picker aggregates up to three activity catalogs based on the
org's enabled modules:

- Store activities are always available (baseline for every business).
- Customization activities require the ``boutique`` module.
- Project activities require the ``projects`` module.
"""

from dataclasses import dataclass
from typing import Iterable, List

from vaybooks.bms.domain.entitlements.catalog import (
    MODULE_BOUTIQUE,
    MODULE_PROJECTS,
)
from vaybooks.bms.domain.parties.workers.entities import (
    SOURCE_CUSTOMIZATION,
    SOURCE_PROJECT,
    SOURCE_STORE,
    WorkerActivityRef,
)

SOURCE_LABELS = {
    SOURCE_STORE: "Store",
    SOURCE_CUSTOMIZATION: "Customization",
    SOURCE_PROJECT: "Project",
}


@dataclass(frozen=True)
class ActivityOption:
    activity_id: str
    activity_name: str
    source: str
    label: str
    is_active: bool = True

    @property
    def key(self) -> str:
        """Composite picker key; bare names collide across catalogs."""
        return f"{self.source}:{self.activity_id}"

    @property
    def ref(self) -> WorkerActivityRef:
        return WorkerActivityRef(activity_id=self.activity_id, source=self.source)


def refs_from_keys(keys: Iterable[str]) -> List[WorkerActivityRef]:
    """Convert composite ``source:id`` picker keys back to refs."""
    refs = []
    for key in keys or []:
        source, _, activity_id = str(key).partition(":")
        if source and activity_id:
            refs.append(WorkerActivityRef(activity_id=activity_id, source=source))
    return refs


class EmployeeActivityOptionsService:
    def __init__(
        self,
        plans_service,
        store_activity_service,
        customization_activity_service,
        project_activity_service,
    ):
        self._plans = plans_service
        self._catalogs = {
            SOURCE_STORE: store_activity_service,
            SOURCE_CUSTOMIZATION: customization_activity_service,
            SOURCE_PROJECT: project_activity_service,
        }

    def enabled_sources(self) -> List[str]:
        """Sources selectable for new assignments, per enabled modules."""
        modules = set(self._plans.get_org_entitlement().enabled_modules or [])
        sources = [SOURCE_STORE]
        if MODULE_BOUTIQUE in modules:
            sources.append(SOURCE_CUSTOMIZATION)
        if MODULE_PROJECTS in modules:
            sources.append(SOURCE_PROJECT)
        return sources

    def _catalog_options(
        self, source: str, active_only: bool
    ) -> List[ActivityOption]:
        service = self._catalogs.get(source)
        if service is None:
            return []
        options = []
        for activity in service.list_activities(active_only=active_only):
            options.append(
                ActivityOption(
                    activity_id=activity.id,
                    activity_name=activity.activity_name,
                    source=source,
                    label=f"{activity.activity_name} · {SOURCE_LABELS[source]}",
                    is_active=bool(getattr(activity, "is_active", True)),
                )
            )
        return options

    def list_options(self, active_only: bool = True) -> List[ActivityOption]:
        """Selectable options for the employee picker (module-filtered)."""
        options: List[ActivityOption] = []
        for source in self.enabled_sources():
            options.extend(self._catalog_options(source, active_only))
        return options

    def options_for_refs(self, refs: Iterable) -> List[ActivityOption]:
        """Resolve assigned refs for display, regardless of enabled modules.

        Refs whose catalog entry is inactive or whose module is disabled are
        kept (never silently stripped) and labelled accordingly; refs whose
        catalog entry no longer exists resolve to "Unknown activity".
        """
        enabled = set(self.enabled_sources())
        resolved = []
        for ref in refs or []:
            source = getattr(ref, "source", SOURCE_CUSTOMIZATION)
            activity_id = getattr(ref, "activity_id", "")
            service = self._catalogs.get(source)
            activity = service.get_activity(activity_id) if service else None
            source_label = SOURCE_LABELS.get(source, source)
            if activity is None:
                name = "Unknown activity"
                label = f"⚠️ Unknown activity · {source_label}"
                is_active = False
            else:
                name = activity.activity_name
                is_active = bool(getattr(activity, "is_active", True))
                label = f"{name} · {source_label}"
                if source not in enabled:
                    label += " (module disabled)"
                elif not is_active:
                    label += " (inactive)"
            resolved.append(
                ActivityOption(
                    activity_id=activity_id,
                    activity_name=name,
                    source=source,
                    label=label,
                    is_active=is_active,
                )
            )
        return resolved
