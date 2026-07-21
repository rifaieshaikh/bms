from __future__ import annotations

from typing import Dict, List, Optional, Set

from vaybooks.bms.domain.projects.entities import Project, ProjectActivity, ProjectTimeEntry
from vaybooks.bms.domain.shared.exceptions import ValidationError


class ProjectDomainService:
    MAX_DEPTH = 5

    def validate_activity_tree(self, project: Project) -> None:
        activities = project.activities
        by_id = {a.id: a for a in activities}
        if len(by_id) != len(activities):
            raise ValidationError("Duplicate activity IDs in project")

        for activity in activities:
            if activity.parent_activity_id:
                parent = by_id.get(activity.parent_activity_id)
                if not parent:
                    raise ValidationError(
                        f"Activity '{activity.name}' has unknown parent"
                    )
                depth = self._depth(activity.id, by_id)
                max_depth = project.max_activity_depth or self.MAX_DEPTH
                if depth > max_depth:
                    raise ValidationError(
                        f"Activity '{activity.name}' exceeds max depth {max_depth}"
                    )

        for activity in activities:
            if self._has_children(activity.id, activities):
                if activity.planned_revenue_amount > 0:
                    raise ValidationError(
                        f"Parent activity '{activity.name}' cannot have planned revenue"
                    )

    def _depth(self, activity_id: str, by_id: Dict[str, ProjectActivity]) -> int:
        depth = 1
        current = by_id.get(activity_id)
        while current and current.parent_activity_id:
            depth += 1
            current = by_id.get(current.parent_activity_id)
        return depth

    def _has_children(self, activity_id: str, activities: List[ProjectActivity]) -> bool:
        return any(a.parent_activity_id == activity_id for a in activities)

    def roll_up_planned_revenue(self, project: Project) -> Dict[str, float]:
        """Parent revenue = sum of direct children (leaf-only input)."""
        by_id = {a.id: a for a in project.activities}
        children: Dict[str, List[str]] = {}
        for a in project.activities:
            if a.parent_activity_id:
                children.setdefault(a.parent_activity_id, []).append(a.id)

        memo: Dict[str, float] = {}

        def revenue_for(act_id: str) -> float:
            if act_id in memo:
                return memo[act_id]
            child_ids = children.get(act_id, [])
            if not child_ids:
                memo[act_id] = by_id[act_id].planned_revenue_amount
            else:
                memo[act_id] = sum(revenue_for(cid) for cid in child_ids)
            return memo[act_id]

        return {a.id: revenue_for(a.id) for a in project.activities}

    def resolve_hourly_rate(
        self,
        *,
        entry_override: Optional[float],
        activity: Optional[ProjectActivity],
        worker_rate: float,
        project: Project,
    ) -> float:
        if entry_override is not None and entry_override > 0:
            return entry_override
        if activity and activity.default_hourly_rate > 0:
            return activity.default_hourly_rate
        if worker_rate > 0:
            return worker_rate
        if project.default_hourly_rate > 0:
            return project.default_hourly_rate
        return 0.0

    def compute_labour_cost(self, duration_minutes: int, hourly_rate: float) -> float:
        return round((duration_minutes / 60.0) * hourly_rate, 2)

    def validate_time_entry_rate(
        self,
        hourly_rate: float,
        zero_cost_override: bool,
    ) -> None:
        if hourly_rate <= 0 and not zero_cost_override:
            raise ValidationError(
                "Hourly rate must be greater than zero, or enable zero-cost override"
            )

    def build_time_entries(
        self,
        *,
        project: Project,
        activity_id: str,
        worker_rows: List[dict],
        work_date,
        notes: str,
        batch_id: str,
    ) -> List[ProjectTimeEntry]:
        activity = next((a for a in project.activities if a.id == activity_id), None)
        if not activity:
            raise ValidationError("Activity not found on project")

        entries: List[ProjectTimeEntry] = []
        for row in worker_rows:
            rate = self.resolve_hourly_rate(
                entry_override=row.get("hourly_rate"),
                activity=activity,
                worker_rate=float(row.get("worker_rate") or 0),
                project=project,
            )
            zero_override = bool(row.get("zero_cost_override"))
            self.validate_time_entry_rate(rate, zero_override)
            duration = int(row["duration_minutes"])
            cost = self.compute_labour_cost(duration, rate)
            entries.append(
                ProjectTimeEntry(
                    project_id=project.id,
                    activity_id=activity_id,
                    worker_id=row["worker_id"],
                    worker_name=row.get("worker_name", ""),
                    work_date=work_date,
                    duration_minutes=duration,
                    hourly_rate=rate,
                    labour_cost=cost,
                    notes=notes,
                    batch_id=batch_id,
                    zero_cost_override=zero_override,
                    wbs_node_id=(row.get("wbs_node_id") or getattr(activity, "wbs_node_id", "") or ""),
                    site_id=(row.get("site_id") or "").strip(),
                    boq_item_id=(row.get("boq_item_id") or "").strip(),
                    cost_category=(row.get("cost_category") or "Labour"),
                )
            )
        return entries

    def leaf_activity_ids(self, project: Project) -> Set[str]:
        parent_ids = {a.parent_activity_id for a in project.activities if a.parent_activity_id}
        return {a.id for a in project.activities if a.id not in parent_ids}
